from fastapi import APIRouter
from app.triggers.on_balance_reminder import process_upcoming_balances

router = APIRouter(prefix="/tasks", tags=["Automation"])

@router.get("/run-balance-reminders")
async def trigger_reminders():
    # This is what the cron job hits
    return process_upcoming_balances()