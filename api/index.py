import asyncio
from app.main import app
from app.database import async_session, init_db
from app.models import Admin
from sqlalchemy import select


async def _ensure_seed():
    try:
        await init_db()
        async with async_session() as db:
            r = await db.execute(select(Admin))
            if not r.scalars().first():
                from app.main import ensure_test_users
                await ensure_test_users()
    except Exception:
        import traceback
        traceback.print_exc()


asyncio.run(_ensure_seed())
