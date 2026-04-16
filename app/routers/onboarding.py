"""Slack OAuth onboarding flow using Nango."""

import hmac
import json
import uuid
from hashlib import sha256

import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse

from app.core.config import settings
from app.core import json_storage
from app.services.nango_service import nango_client

router = APIRouter()


def _normalize_phone(phone: str) -> str:
    return "".join(filter(str.isdigit, phone))[-10:]


def _connection_uuid_for_phone(phone: str) -> uuid.UUID:
    # Deterministic UUID keeps stable Nango connection IDs.
    return uuid.uuid5(uuid.NAMESPACE_DNS, f"superowl-nango-{_normalize_phone(phone)}")


async def _find_business_by_phone(phone: str):
    candidates = [phone, f"+91{_normalize_phone(phone)}", _normalize_phone(phone)]
    for candidate in candidates:
        business = await json_storage.get_business_by_phone(candidate)
        if business:
            return business
    return None


def _verify_nango_signature(raw_body: bytes, signature: str | None) -> bool:
    if not settings.NANGO_WEBHOOK_SECRET:
        return True
    if not signature:
        return False
    expected = hmac.new(
        settings.NANGO_WEBHOOK_SECRET.encode("utf-8"),
        raw_body,
        sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


@router.get("/connect/session")
async def create_nango_session(phone: str):
    """Start Slack OAuth flow for a business phone number."""
    business = await _find_business_by_phone(phone)
    if not business:
        # List all businesses for debugging
        all_biz = await json_storage.list_businesses()
        biz_phones = [b.get("phone_number") for b in all_biz]
        raise HTTPException(
            status_code=404,
            detail=f"Business not found for phone '{phone}'. Available phones: {biz_phones}"
        )

    connection_uuid = _connection_uuid_for_phone(phone)
    connection_id = str(connection_uuid)

    try:
        session_data = await nango_client.create_session(connection_id)
        # Persist only after Nango accepted the session request.
        business["nango_connection_id"] = connection_id
        await json_storage.update_business(business["id"], business)
        return {"connect_link": session_data.get("data", {}).get("connect_link")}
    except HTTPException:
        raise
    except httpx.HTTPStatusError as e:
        response_text = e.response.text if e.response is not None else ""
        if "resource_capped" in response_text:
            raise HTTPException(
                status_code=429,
                detail=(
                    "Nango has reached the connection limit for this workspace. "
                    "Free up an existing connection or upgrade the Nango plan, then retry."
                ),
            ) from e
        raise HTTPException(status_code=502, detail=f"Nango rejected the session request: {response_text or str(e)}") from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Nango session creation failed: {type(e).__name__}: {e}")


@router.get("/callback/slack")
async def slack_oauth_callback(request: Request):
    """OAuth callback after Slack connection."""
    # Nango handles the actual OAuth; this is a dummy endpoint
    # The real integration happens via Nango webhook
    return HTMLResponse("<h1>Slack Connected! You can close this window.</h1>")


@router.post("/webhook/slack")
async def nango_webhook(request: Request):
    """Handle Nango auth webhooks and finalize workspace metadata."""
    raw_body = await request.body()
    signature = request.headers.get("x-nango-signature")
    if not _verify_nango_signature(raw_body, signature):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    try:
        payload = json.loads(raw_body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    connection_id = (
        payload.get("connectionId")
        or payload.get("connection_id")
        or payload.get("connection", {}).get("id")
        or payload.get("data", {}).get("connectionId")
        or payload.get("data", {}).get("connection_id")
    )
    end_user_id = (
        payload.get("endUser", {}).get("id")
        or payload.get("end_user", {}).get("id")
        or payload.get("data", {}).get("endUser", {}).get("id")
        or payload.get("data", {}).get("end_user", {}).get("id")
    )

    candidate_id = connection_id or end_user_id
    if not candidate_id:
        return {"status": "ignored", "reason": "missing_connection_id"}

    try:
        connection_uuid = uuid.UUID(str(candidate_id))
    except ValueError:
        # Nango may send non-UUID connection IDs
        return {"status": "ignored", "reason": "connection_id_not_uuid"}

    # Find business by nango_connection_id
    businesses = await json_storage.list_businesses()
    business = None
    for b in businesses:
        if b.get("nango_connection_id") == str(connection_uuid):
            business = b
            break
    
    if not business:
        return {"status": "ignored", "reason": "business_not_found"}

    workspace = (
        payload.get("provider", {}).get("name")
        or payload.get("provider_config_key")
        or payload.get("data", {}).get("provider", {}).get("name")
        or business.get("slack_workspace")
        or "Slack"
    )

    # Persist workspace name to a stable key and keep backward compatibility
    business["slack_workspace"] = workspace
    business["slack_workspace_name"] = workspace

    # Try to fetch Nango connection details (may include access tokens/credentials)
    try:
        conn_info = await nango_client.get_connection(str(connection_uuid))
        data = {}
        if isinstance(conn_info, dict):
            # Nango responses might place tokens under 'data' or 'credentials'
            data = conn_info.get("data") or conn_info.get("credentials") or {}
        # Try common token field names
        token = (
            (data.get("access_token") if isinstance(data, dict) else None)
            or (data.get("oauth_token") if isinstance(data, dict) else None)
            or (data.get("token") if isinstance(data, dict) else None)
            or (data.get("credentials", {}).get("access_token") if isinstance(data.get("credentials"), dict) else None)
            or (data.get("oauth", {}).get("access_token") if isinstance(data.get("oauth"), dict) else None)
        )
        if token:
            business["slack_access_token"] = token
    except Exception:
        # Don't fail webhook if fetching connection details fails; it's best-effort.
        pass

    await json_storage.update_business(business["id"], business)
    return {"status": "ok", "business_id": str(business["id"]), "workspace": workspace}


@router.get("/slack/channels")
async def list_slack_channels(phone: str):
    """List available Slack channels for a connected business."""
    business = await _find_business_by_phone(phone)

    if not business or not business.get("nango_connection_id"):
        raise HTTPException(status_code=404, detail="Business not connected to Slack")

    try:
        channels = await nango_client.list_channels(str(business.get("nango_connection_id")))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Slack not fully connected: {e}")
    return [{"id": c["id"], "name": c["name"]} for c in channels]
