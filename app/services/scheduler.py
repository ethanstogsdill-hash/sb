import asyncio
import logging

logger = logging.getLogger(__name__)

_tasks: list[asyncio.Task] = []


async def _scrape_loop():
    """Scrape agents every 15 minutes."""
    while True:
        await asyncio.sleep(15 * 60)
        try:
            from app.services.scraper import scrape_all
            from app.database import upsert_agents, upsert_bets, log_scrape
            from app.utils import compute_week_start
            data = await scrape_all()
            agents_data = data["agents"]
            wagers_data = data["wagers"]
            week_start = compute_week_start()
            count = await upsert_agents(agents_data, week_start=week_start)
            bet_count = await upsert_bets(wagers_data) if wagers_data else 0
            await log_scrape("agents", "success", f"Auto-scraped {count} agents, {bet_count} bets", count)
            logger.info(f"Auto-scrape: {count} agents, {bet_count} bets updated")
        except Exception as e:
            from app.database import log_scrape
            await log_scrape("agents", "error", f"Auto-scrape failed: {e}")
            logger.error(f"Auto-scrape failed: {e}")


async def _gmail_loop():
    """Scan Gmail every 10 minutes."""
    while True:
        await asyncio.sleep(10 * 60)
        try:
            from app.services.gmail_service import scan_emails, is_connected
            if not is_connected():
                continue
            from app.database import insert_payments, log_scrape
            emails = scan_emails()
            count = await insert_payments(emails)
            await log_scrape("gmail", "success", f"Auto-scan: {len(emails)} emails, {count} new", count)
            logger.info(f"Auto-scan: {count} new payments")
        except Exception as e:
            from app.database import log_scrape
            await log_scrape("gmail", "error", f"Auto-scan failed: {e}")
            logger.error(f"Auto-scan failed: {e}")


async def start_scheduler():
    """Start background loops."""
    _tasks.append(asyncio.create_task(_scrape_loop()))
    _tasks.append(asyncio.create_task(_gmail_loop()))
    logger.info("Scheduler started: scrape@15min, gmail@10min")


async def stop_scheduler():
    """Cancel background tasks."""
    for task in _tasks:
        task.cancel()
    _tasks.clear()
    logger.info("Scheduler stopped")
