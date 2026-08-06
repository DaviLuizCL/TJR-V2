import asyncio

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app import models  # noqa: F401  garante que os models sao registrados no metadata
from app.core.config import settings
from app.db.base import Base
from app.db.session import get_db
from app.main import app


async def _criar_tabelas_async() -> None:
    engine = create_async_engine(settings.test_database_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()


async def _dropar_tabelas_async() -> None:
    engine = create_async_engine(settings.test_database_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture(scope="session", autouse=True)
def _criar_tabelas():
    asyncio.run(_criar_tabelas_async())
    yield
    asyncio.run(_dropar_tabelas_async())


@pytest.fixture
async def db_session():
    engine = create_async_engine(settings.test_database_url)
    session_local = async_sessionmaker(bind=engine, expire_on_commit=False)
    async with session_local() as session:
        yield session
        await session.rollback()
    await engine.dispose()


@pytest.fixture
async def client(db_session):
    async def _get_db_override():
        yield db_session

    app.dependency_overrides[get_db] = _get_db_override
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()
