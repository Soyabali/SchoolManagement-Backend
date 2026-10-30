from fastapi import APIRouter
from sqlalchemy import text

from app.core.dependencies import DbSession

router = APIRouter()


@router.get("/health", summary="API and database health check")
def health(db: DbSession) -> dict[str, str]:
    db.execute(text("SELECT 1"))
    return {"status": "ok", "database": "connected"}
