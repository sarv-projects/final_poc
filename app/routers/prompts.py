"""Shared system prompt management."""

from fastapi import APIRouter

from app.core import json_storage
from app.schemas.webhook import PromptUpdate

router = APIRouter()


@router.get("/shared")
async def get_shared_prompt():
    """Get the global shared system prompt template."""
    templates = await json_storage.list_prompt_templates()
    if templates and len(templates) > 0:
        template = templates[0]
        if isinstance(template, dict):
            return {"prompt": template.get("shared_system_prompt", "")}
        elif hasattr(template, "shared_system_prompt"):
            return {"prompt": template.shared_system_prompt}
    # Default prompt
    return {
        "prompt": """You are {{agentName}}, a warm, friendly, and professional voice assistant for {{businessName}} in {{city}}.

Speak naturally and calmly. Keep responses short, clear, and human.

Your goals:
- Understand the caller's request
- Answer product, service, pricing, and booking questions clearly.
-If caller needs the owner by escalation,or urgent ,then offer a transfer immediately.
- If the caller needs the owner or the issue is urgent, offer a transfer
- Confirm the caller's name and callback number before ending the call

If transferring: "Let me connect you with our team directly."
Then transfer to {{fallbackNumber}}."""
    }


@router.put("/shared")
async def update_shared_prompt(update: PromptUpdate):
    """Update the global shared system prompt template."""
    templates = await json_storage.list_prompt_templates()
    if templates and len(templates) > 0:
        template = templates[0]
        template["shared_system_prompt"] = update.prompt
        await json_storage.update_prompt_template(template.get("id"), template)
    else:
        # Create new template
        await json_storage.create_prompt_template({
            "name": "default",
            "shared_system_prompt": update.prompt,
        })
    return {"status": "updated"}
