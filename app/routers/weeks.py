from fastapi import APIRouter
from app.models import PaymentUpdate
from app import database as db

router = APIRouter()


@router.get("")
async def list_weeks():
    return await db.get_available_weeks()


@router.get("/{week_start}")
async def get_week(week_start: str):
    return await db.get_weekly_snapshots(week_start)


@router.get("/{week_start}/summary")
async def get_week_summary(week_start: str):
    return await db.get_weekly_summary(week_start)


@router.patch("/snapshots/{snapshot_id}/payment")
async def update_snapshot_payment(snapshot_id: int, body: PaymentUpdate):
    await db.update_payment(snapshot_id, body.amount_paid)
    return {"ok": True}
