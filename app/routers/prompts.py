"""Shared system prompt management."""

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.prompt_template import PromptTemplate
from app.schemas.webhook import PromptUpdate

router = APIRouter()


@router.get("/shared")
async def get_shared_prompt(db: AsyncSession = Depends(get_db)):
    """Get the global shared system prompt template."""
    result = await db.execute(select(PromptTemplate).limit(1))
    template = result.scalar_one_or_none()
    if template:
        return {"prompt": template.shared_system_prompt}
    # Default prompt
    return {
        "prompt": """You are {{agentName}}, a warm and professional voice assistant for {{businessName}} in {{city}}.
Business hours: {{hours}}.
Services offered: {{services}}.
Keep responses under 25 words. If transferring: "Let me connect you with our team." """
    }


@router.put("/shared")
async def update_shared_prompt(
    update: PromptUpdate, db: AsyncSession = Depends(get_db)
):
    """Update the global shared system prompt template."""
    result = await db.execute(select(PromptTemplate).limit(1))
    template = result.scalar_one_or_none()

    if template:
        template.shared_system_prompt = update.prompt
    else:
        template = PromptTemplate(shared_system_prompt=update.prompt)
        db.add(template)

    await db.commit()
    return {"status": "updated"}
