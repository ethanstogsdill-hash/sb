from fastapi import APIRouter, HTTPException
from app import database as db

router = APIRouter()


@router.get("")
async def list_bets(sport: str = None, result: str = None,
                    player_id: str = None, limit: int = 500, offset: int = 0):
    return await db.get_all_bets(sport=sport, result=result,
                                 player_id=player_id, limit=limit, offset=offset)


@router.get("/stats")
async def bet_stats():
    return await db.get_bet_stats()


@router.get("/sports")
async def bet_sports():
    return await db.get_bet_sports()


@router.get("/test-telegram")
async def test_telegram():
    from app.services.telegram import send_message
    ok = await send_message("✅ <b>Sportsbook Dashboard</b>\nTelegram bot is connected and working!")
    if not ok:
        raise HTTPException(status_code=400, detail="Telegram not configured or send failed. Check TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in .env")
    return {"status": "sent", "message": "Check your Telegram!"}
