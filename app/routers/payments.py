from fastapi import APIRouter, HTTPException
from app.models import PaymentLink
from app import database as db

router = APIRouter()

_scan_running = False


@router.get("")
async def list_payments():
    return await db.get_all_payments()


@router.patch("/{payment_id}")
async def link_payment(payment_id: int, body: PaymentLink):
    await db.link_payment(payment_id, body.linked_agent_id, body.match_status)
    return {"ok": True}


@router.post("/scan")
async def trigger_scan():
    global _scan_running
    if _scan_running:
        return {"status": "already_running"}

    _scan_running = True
    try:
        from app.services.gmail_service import scan_emails
        emails = scan_emails()
        count = await db.insert_payments(emails)
        await db.log_scrape("gmail", "success", f"Found {len(emails)} emails, {count} new", count)
        return {"status": "success", "total": len(emails), "new": count}
    except Exception as e:
        await db.log_scrape("gmail", "error", str(e))
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        _scan_running = False
