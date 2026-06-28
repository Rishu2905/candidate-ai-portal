from fastapi import APIRouter, Depends, BackgroundTasks
from security.jwt_verify import require_admin
from scheduler.market_tool_scheduler import refresh_market_jobs
import logging

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Admin"])


@router.post("/market-tool")
async def trigger_market_refresh(
    background_tasks: BackgroundTasks,
    admin=Depends(require_admin)
):
    """
    Manually triggers market job refresh.
    Admin only — role=ADMIN checked in require_admin dependency.
    Useful for forcing refresh without waiting for 2 week schedule.
    """
    background_tasks.add_task(refresh_market_jobs)
    logger.info(f"Market refresh manually triggered by admin: {admin['user_id']}")
    return {"message": "Market refresh triggered", "status": "PROCESSING"}