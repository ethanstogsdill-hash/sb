from fastapi import APIRouter
from app import database as db

router = APIRouter()


@router.get("/summary")
async def summary():
    return await db.get_dashboard_summary()
