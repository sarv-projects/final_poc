"""Slack OAuth onboarding flow using Nango."""

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import select

from app.core.database import get_db
from app.models.business import Business
from app.services.nango_service import nango_client

router = APIRouter()


async def _get_db():
    async for session in get_db():
        return session


@router.get("/connect/session")
async def create_nango_session(phone: str):
    """Start Slack OAuth flow for a business phone number."""
    # Normalize phone number
    clean_phone = "".join(filter(str.isdigit, phone))[-10:]
    connection_id = f"conn_{clean_phone}"

    try:
        session_data = await nango_client.create_session(connection_id)
        return {"connect_link": session_data.get("data", {}).get("connect_link")}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/callback/slack")
async def slack_oauth_callback(request: Request):
    """OAuth callback after Slack connection."""
    # Nango handles the actual OAuth; this is a dummy endpoint
    # The real integration happens via Nango webhook
    return HTMLResponse("<h1>Slack Connected! You can close this window.</h1>")


@router.get("/slack/channels")
async def list_slack_channels(phone: str):
    """List available Slack channels for a connected business."""
    db = await _get_db()
    result = await db.execute(select(Business).where(Business.phone_number == phone))
    business = result.scalar_one_or_none()

    if not business or not business.nango_connection_id:
        raise HTTPException(status_code=404, detail="Business not connected to Slack")

    channels = await nango_client.list_channels(str(business.nango_connection_id))
    return [{"id": c["id"], "name": c["name"]} for c in channels]
