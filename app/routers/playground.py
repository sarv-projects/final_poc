"""Playground endpoints for testing calls and seeding demo data."""

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.business import Business
from app.models.prompt_template import PromptTemplate

router = APIRouter()

DEFAULT_SHARED_PROMPT = """You are {{agentName}}, a warm and professional voice assistant for {{businessName}} in {{city}}.
Business hours: {{hours}}.
Services offered: {{services}}.

Your goals:
- Understand the caller's inquiry (from chat context if outbound)
- Answer product/service questions clearly
- For pricing or urgent matters, offer to transfer to the owner
- Keep responses under 25 words — this is a voice call

If transferring: "Let me connect you with our team directly."
Then transfer to {{fallbackNumber}}.

Always confirm the caller's name and callback number before ending."""


@router.post("/seed")
async def seed_demo_data(db: AsyncSession = Depends(get_db)):
    """
    Seed a demo business and shared prompt for fresh installs.
    Idempotent — safe to call multiple times.
    Returns the business_id to construct the dashboard URL:
      http://localhost:8000/?business_id=<id>
    """
    result = await db.execute(
        select(Business).where(Business.phone_number == "+919901540581")
    )
    existing = result.scalar_one_or_none()
    if existing:
        return {
            "status": "already_seeded",
            "business_id": str(existing.id),
            "dashboard_url": f"http://localhost:8000/?business_id={existing.id}",
        }

    biz = Business(
        phone_number="+919901540581",
        display_name="Sweet Root – Toys & Memories",
        city="Bengaluru",
        hours="10 AM – 7 PM, Mon–Sat",
        services="Wooden toys, birthday parties, creative play sessions, memory quilts",
        fallback_number="+919901540581",
        voice_id="pMsXgVXv3BLzUgSXRplE",
        outbound_welcome_template=(
            "Hi {customer_name}, this is Roo calling from {business_name}! "
            "I was just speaking with you on our chat. How can I assist you today?"
        ),
        inbound_welcome_template=(
            "Thank you for calling {{businessName}}! I'm Roo, your AI assistant. "
            "How can I help you today?"
        ),
        callback_trigger_phrase="Would you like us to call you back for a more detailed discussion?",
    )
    db.add(biz)

    # Seed shared prompt only if none exists
    prompt_result = await db.execute(select(PromptTemplate).limit(1))
    if not prompt_result.scalar_one_or_none():
        db.add(PromptTemplate(shared_system_prompt=DEFAULT_SHARED_PROMPT))

    await db.commit()
    await db.refresh(biz)

    return {
        "status": "seeded",
        "business_id": str(biz.id),
        "dashboard_url": f"http://localhost:8000/?business_id={biz.id}",
    }


@router.post("/test-outbound")
async def test_outbound():
    """Simulate an outbound callback for testing."""
    return {"status": "ok", "message": "Outbound test triggered (stub)"}


@router.post("/test-inbound")
async def test_inbound():
    """Simulate an inbound call for testing."""
    return {"status": "ok", "message": "Inbound test triggered (stub)"}
