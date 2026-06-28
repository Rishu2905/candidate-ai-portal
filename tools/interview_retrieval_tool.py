from db.postgres_client import fetchrow
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

async def interview_retrieval_tool(
    user_id: str,
    max_age_days: int = 20
) -> dict:
    """
    Retrieves most recent interview verdict for a candidate.
    Called by orchestrator BEFORE deciding to run mock_interview_tool.
    
    Returns:
    - recent verdict if interview exists within max_age_days
    - { "has_recent_interview": False } if no recent data
    """
    try:
        result = await fetchrow(
            """
            SELECT 
                v.verdict_id,
                v.score,
                v.verdict,
                v.overall_performance,
                v.strong_areas,
                v.weak_areas,
                v.recommendation,
                v.verdict_reason,
                v.created_at,
                i.job_title,
                i.completed_at
            FROM interview_verdicts v
            JOIN interviews i ON v.interview_id = i.interview_id
            WHERE v.user_id = $1
            AND i.status = 'COMPLETED'
            ORDER BY v.created_at DESC
            LIMIT 1
            """,
            user_id
        )

        if not result:
            return {
                "has_recent_interview": False,
                "message": "No interview history found for this candidate"
            }

        # check if interview is recent enough
        interview_date = result["created_at"]
        age_days = (datetime.utcnow() - interview_date).days

        if age_days > max_age_days:
            return {
                "has_recent_interview": False,
                "last_interview_date": interview_date.isoformat(),
                "age_days": age_days,
                "message": f"Last interview was {age_days} days ago — too old, run fresh interview"
            }

        # recent interview found — return verdict
        return {
            "has_recent_interview": True,
            "age_days": age_days,
            "score": result["score"],
            "verdict": result["verdict"],
            "overall_performance": result["overall_performance"],
            "strong_areas": result["strong_areas"],
            "weak_areas": result["weak_areas"],
            "recommendation": result["recommendation"],
            "verdict_reason": result["verdict_reason"],
            "job_title": result["job_title"],
            "interview_date": interview_date.isoformat(),
            "message": f"Recent interview found ({age_days} days ago) — using existing data"
        }

    except Exception as e:
        logger.error(f"interview_retrieval_tool failed: {e}")
        return {
            "has_recent_interview": False,
            "error": str(e)
        }