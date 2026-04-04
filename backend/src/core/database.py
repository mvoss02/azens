from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from src.core.config import settings as settings_db

# Engine: One connection pool for whole application
engine = create_async_engine(settings_db.database_url, echo=settings_db.debug)

# Session factory: Stamps out sessions for each request
SessionLocal = async_sessionmaker(
    bind=engine,
    expire_on_commit=False # object stays usable after commit to DB
)

# Base: Every model (DB table) inherits from this:
class Base(DeclarativeBase):
    pass

# Dependency: FastAPI calls this each time to give a route a session
async def get_db():
    async with SessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
