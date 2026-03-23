from fastapi import APIRouter
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
