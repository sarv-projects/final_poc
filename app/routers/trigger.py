"""Endpoint for triggering outbound callback."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.business import Business
from app.schemas.call import OutboundCallbackRequest
from app.services.call_orchestrator import trigger_outbound_callback

router = APIRouter()


@router.post("/outbound")
async def trigger_outbound(
    request: OutboundCallbackRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Trigger an outbound callback from chat widget.
    Flow O-1 or O-2 depending on business configuration.
    """
    # Lookup business
    result = await db.execute(
        select(Business).where(Business.id == request.business_id)
    )
    business = result.scalar_one_or_none()
    if not business:
        raise HTTPException(status_code=404, detail="Business not found")


    # SQLAlchemy Column[bool] cannot be used directly in conditionals
    if not bool(business.enable_voice_callbacks):
        raise HTTPException(
            status_code=400, detail="Voice callbacks disabled for this business"
        )


    # Initiate callback (pass db session as first argument)
    result = await trigger_outbound_callback(
        db,
        business=business,
        customer_name=request.customer_name,
        customer_phone=request.customer_phone,
        chat_summary=request.chat_summary,
        chat_history=request.chat_history,
    )

    return {"call_id": result.get("id"), "status": "initiated"}
