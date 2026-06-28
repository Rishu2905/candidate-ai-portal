from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from models.schemas import AnalyseRequest, AnalyseResponse
from orchestrator.groq_orchestrator import orchestrator
from db.mongo_client import get_analysis_content
from security.jwt_verify import verify_token
import logging

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Analysis"])


@router.post("/analyse", response_model=AnalyseResponse)
async def analyse(
    req: AnalyseRequest,
    background_tasks: BackgroundTasks
):
    """
    Called by Java service layer after PDF upload.
    No auth header — internal service-to-service call.
    Fires orchestrator as background task, returns 202 immediately.
    Java doesn't wait for this — upload endpoint already returned to frontend.
    """
    logger.info(
        f"Analysis triggered — "
        f"doc_id: {req.doc_id}, "
        f"job_title: {req.job_title}"
    )

    background_tasks.add_task(
        orchestrator.run,
        req.doc_id,
        req.user_id,
        req.job_title
    )

    return AnalyseResponse(
        status="PROCESSING",
        doc_id=req.doc_id,
        message="Analysis started. Poll /ai/status/{doc_id} for results."
    )


@router.get("/status/{doc_id}")
async def get_status(
    doc_id: str,
    user=Depends(verify_token)
):
    """
    Frontend polls this after upload to check if analysis is ready.
    Returns PROCESSING until orchestrator finishes.
    Returns full result when COMPLETE.
    """
    collection = get_analysis_content()

    result = await collection.find_one(
        {"doc_id": doc_id, "user_id": user["user_id"]},
        {"_id": 0}  # exclude MongoDB internal _id from response
    )

    if not result:
        return {"status": "NOT_FOUND", "doc_id": doc_id}

    status = result.get("status", "PROCESSING")

    if status != "COMPLETE":
        return {"status": status, "doc_id": doc_id}

    return result


@router.get("/analysis/{doc_id}/jobs")
async def get_jobs(
    doc_id: str,
    user=Depends(verify_token)
):
    """
    Returns ranked job suggestions from completed analysis.
    Frontend uses this for the jobs tab on dashboard.
    """
    collection = get_analysis_content()

    result = await collection.find_one(
        {"doc_id": doc_id, "user_id": user["user_id"]},
        {"_id": 0, "suggested_jobs": 1, "status": 1}
    )

    if not result:
        raise HTTPException(status_code=404, detail="Analysis not found")

    if result.get("status") != "COMPLETE":
        raise HTTPException(
            status_code=202,
            detail="Analysis still processing"
        )

    return {
        "doc_id": doc_id,
        "jobs": result.get("suggested_jobs", [])
    }