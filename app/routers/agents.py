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
    await db.update_agent_real_name(agent_id, body.real_name)
    return {"ok": True}


@router.post("/scrape")
async def trigger_scrape():
    global _scrape_running
    if _scrape_running:
        return {"status": "already_running"}

    _scrape_running = True
    try:
        from app.services.scraper import scrape_agents
        agents_data = await scrape_agents()
        count = await db.upsert_agents(agents_data)
        await db.log_scrape("agents", "success", f"Scraped {count} agents", count)
        return {"status": "success", "count": count}
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
