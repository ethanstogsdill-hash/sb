from fastapi import APIRouter, HTTPException
from app.models import AgentUpdate, ScrapeStatus
from app import database as db

router = APIRouter()

_scrape_running = False


@router.get("")
async def list_agents():
    return await db.get_all_agents()


@router.patch("/{agent_id}")
async def update_agent(agent_id: int, body: AgentUpdate):
    await db.update_agent_profile(agent_id, real_name=body.real_name, telegram=body.telegram, excluded=body.excluded)
    return {"ok": True}


@router.post("/scrape")
async def trigger_scrape():
    global _scrape_running
    if _scrape_running:
        return {"status": "already_running"}

    _scrape_running = True
    try:
        from app.services.scraper import scrape_all
        from app.utils import compute_week_start
        data = await scrape_all()
        agents_data = data["agents"]
        wagers_data = data["wagers"]
        week_start = compute_week_start()
        count = await db.upsert_agents(agents_data, week_start=week_start)
        bet_count = await db.upsert_bets(wagers_data) if wagers_data else 0
        await db.log_scrape("agents", "success", f"Scraped {count} agents, {bet_count} bets", count)
        return {"status": "success", "count": count, "bet_count": bet_count}
    except Exception as e:
        await db.log_scrape("agents", "error", str(e))
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        _scrape_running = False


@router.get("/scrape-status")
async def scrape_status():
    last = await db.get_last_scrape("agents")
    if not last:
        return ScrapeStatus(status="never_run")
    return ScrapeStatus(
        status=last["status"],
        message=last["message"] or "",
        last_run=last["created_at"],
        records_affected=last["records_affected"],
    )
