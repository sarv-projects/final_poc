"""High-level call flow orchestration."""

from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.business import Business
from app.models.prompt_template import PromptTemplate
from app.services.prompt_builder import prompt_builder
from app.services.vapi_service import vapi_client


async def trigger_outbound_callback(
    session: AsyncSession,
    business: Business,
    customer_name: str,
    customer_phone: str,
    chat_summary: str,
    chat_history: Optional[list] = None,
) -> dict:
    """Initiate an outbound callback flow (O-1 or O-2)."""
    # Get shared prompt template
    result = await session.execute(select(PromptTemplate).limit(1))
    prompt_template = result.scalar_one_or_none()
    shared_prompt = (
        prompt_template.shared_system_prompt
        if prompt_template
        else "You are a helpful assistant."
    )

    # Build system prompt
    business_dict = {
        "display_name": business.display_name,
        "city": business.city,
        "hours": business.hours,
        "services": business.services,
        "fallback_number": business.fallback_number,
    }
    system_prompt = prompt_builder.build_system_prompt(
        shared_prompt, business_dict, is_outbound=True
    )

    # Append chat history if enabled
    if business.inject_chat_context and chat_history:
        formatted = "\n".join([f"{m['role']}: {m['content']}" for m in chat_history])
        system_prompt += f"\n\nCHAT HISTORY:\n{formatted}"

    # Build welcome message
    welcome_vars = {
        "customer_name": customer_name,
        "business_name": business.display_name,
        "chat_summary": chat_summary,
    }
    first_message = prompt_builder.render(
        business.outbound_welcome_template
        or "Hi {customer_name}, this is Roo from {business_name}! How can I help?",
        welcome_vars,
    )

    # Build assistant config
    assistant_config = {
        "model": {"provider": "openai", "model": "gpt-4o-mini"},
        "voice": {"provider": "11labs", "voiceId": business.voice_id},
        "firstMessage": first_message,
        "systemPrompt": system_prompt,
        "maxDurationSeconds": business.max_call_duration_minutes * 60,
        "serverMessages": ["transcript", "hang", "end-of-call-report"],
        "endCallFunctionEnabled": True,
    }

    # Add transfer tool if enabled
    if business.human_transfer_on_escalation:
        assistant_config["tools"] = [
            {
                "type": "transferCall",
                "destinations": [
                    {
                        "type": "sip",
                        "sipUri": f"sip:{business.fallback_number}@{settings.VOBIZ_SIP_DOMAIN}",
                    }
                ],
            }
        ]

    # Create call
    vapi_result = await vapi_client.create_call(
        assistant_config=assistant_config,
        customer_number=customer_phone,
        customer_name=customer_name,
    )

    # Create call log for analytics, whisper, transcript, post-call summary
    vapi_call_id = vapi_result.get("id")
    if vapi_call_id:
        from app.models.call_log import CallLog
        from app.services.slack_service import slack_service

        call_log = CallLog(
            business_id=business.id,
            call_type="outbound",
            vapi_call_id=vapi_call_id,
            customer_phone=customer_phone,
            customer_name=customer_name,
        )
        session.add(call_log)
        await session.commit()
        await session.refresh(call_log)

        # Fire Slack live-call notification for outbound (enables owner whisper/takeover)
        if (
            getattr(business, "nango_connection_id", None)
            and getattr(business, "slack_live_channel", None)
        ):
            try:
                slack_result = await slack_service.send_live_call_notification(
                    connection_id=str(business.nango_connection_id),
                    channel=str(business.slack_live_channel),
                    call_type="outbound",
                    call_log_id=str(call_log.id),
                    vapi_call_id=vapi_call_id,
                    business_name=str(business.display_name),
                    customer_phone=customer_phone,
                    customer_name=customer_name,
                )
                thread_ts = slack_result.get("ts") if isinstance(slack_result, dict) else None
                if thread_ts:
                    call_log.slack_live_thread_ts = thread_ts
                    await session.commit()
            except Exception as e:
                print(f"Outbound Slack notification failed (non-fatal): {e}")

    return vapi_result


async def handle_owner_check_result(
    customer_call_id: str,
    decision: str,
    business_fallback_number: str,
):
    """Handle owner's decision after verification."""
    if decision == "yes":
        # Transfer to owner
        destination = {
            "type": "sip",
            "sipUri": f"sip:{business_fallback_number}@{settings.VOBIZ_SIP_DOMAIN}",
        }
        await vapi_client.transfer_call(customer_call_id, destination)
    else:
        # Owner declined — send message to continue
        await vapi_client.send_message(
            customer_call_id,
            {
                "role": "system",
                "content": "The owner is currently unavailable. Say: 'I'm sorry, our team is busy right now. Can I help you with anything else, or would you like me to take a message?'",
            },
        )
