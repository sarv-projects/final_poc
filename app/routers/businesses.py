"""CRUD endpoints for business (tenant) management."""

import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.business import Business
from app.schemas.business import BusinessCreate, BusinessResponse, BusinessUpdate

router = APIRouter()


@router.post("/", response_model=BusinessResponse, status_code=201)
async def create_business(
    business_data: BusinessCreate,
    db: AsyncSession = Depends(get_db),
):
    """Register a new business."""
    # Check if phone number already exists
    result = await db.execute(
        select(Business).where(Business.phone_number == business_data.phone_number)
    )
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Phone number already registered")

    business = Business(**business_data.model_dump())
    db.add(business)
    await db.commit()
    await db.refresh(business)
    return business


@router.get("/", response_model=List[BusinessResponse])
async def list_businesses(db: AsyncSession = Depends(get_db)):
    """List all registered businesses."""
    result = await db.execute(select(Business))
    return result.scalars().all()


@router.get("/lookup", response_model=Optional[BusinessResponse])
async def lookup_business_by_phone(phone: str, db: AsyncSession = Depends(get_db)):
    """Find business by phone number (used for inbound ANI lookup)."""
    result = await db.execute(select(Business).where(Business.phone_number == phone))
    return result.scalar_one_or_none()


@router.get("/{business_id}", response_model=BusinessResponse)
async def get_business(business_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Get a single business by ID."""
    result = await db.execute(select(Business).where(Business.id == business_id))
    business = result.scalar_one_or_none()
    if not business:
        raise HTTPException(status_code=404, detail="Business not found")
    return business


@router.put("/{business_id}", response_model=BusinessResponse)
async def update_business(
    business_id: uuid.UUID,
    update_data: BusinessUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update an existing business."""
    result = await db.execute(select(Business).where(Business.id == business_id))
    business = result.scalar_one_or_none()
    if not business:
        raise HTTPException(status_code=404, detail="Business not found")

    for key, value in update_data.model_dump(exclude_unset=True).items():
        setattr(business, key, value)

    await db.commit()
    await db.refresh(business)
    return business


@router.delete("/{business_id}", status_code=204)
async def delete_business(business_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Delete a business."""
    result = await db.execute(select(Business).where(Business.id == business_id))
    business = result.scalar_one_or_none()
    if not business:
        raise HTTPException(status_code=404, detail="Business not found")

    await db.delete(business)
    await db.commit()
    return None
