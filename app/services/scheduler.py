import asyncio
import logging

logger = logging.getLogger(__name__)

_tasks: list[asyncio.Task] = []


async def _scrape_loop():
    """Scrape agents every 15 minutes."""
    while True:
        await asyncio.sleep(15 * 60)
        try:
            from app.services.scraper import scrape_agents
            from app.database import upsert_agents, log_scrape
            from app.utils import compute_week_start
            agents = await scrape_agents()
            week_start = compute_week_start()
            count = await upsert_agents(agents, week_start=week_start)
            await log_scrape("agents", "success", f"Auto-scraped {count} agents", count)
            logger.info(f"Auto-scrape: {count} agents updated")
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
