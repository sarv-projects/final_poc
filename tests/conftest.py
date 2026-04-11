"""Pytest configuration and fixtures."""

import asyncio

import pytest
import pytest_asyncio

from app.core.database import Base, engine


@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    """Create and drop tables before each test."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
