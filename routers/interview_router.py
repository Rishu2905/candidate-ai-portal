from fastapi import APIRouter, Depends, HTTPException
from db.postgres_client import execute, fetchrow, fetch
from db.mongo_client import get_document_content
from tools.mock_interview_tool import mock_interview_tool
from security.jwt_verify import verify_token
from pydantic import BaseModel
from datetime import datetime
import uuid
import logging

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Mock Interview"])


class MessageRequest(BaseModel):
    content: str


@router.post("/interview/start")
async def start_interview(
    doc_id: str,
    user=Depends(verify_token)
):
    """
    Candidate clicks "Take Mock Interview" button.
    Creates interview session, returns opening question.
    """
    user_id = user["user_id"]

    # fetch candidate profile from MongoDB
    collection = get_document_content()
    doc = await collection.find_one({"doc_id": doc_id})

    if not doc:
        raise HTTPException(
            status_code=404,
            detail="Resume not found. Upload resume first."
        )

    skills = doc.get("skills", [])
    projects = doc.get("projects", [])
    experience = doc.get("experience", [])

    if not skills and not projects:
        raise HTTPException(
            status_code=400,
            detail="Resume has no skills or projects to interview on."
        )

    # get job title from analysis if available
    job_title = doc.get("job_title", "Software Engineer")

    # create interview session in SQL
    interview_id = str(uuid.uuid4())
    await execute(
        """
        INSERT INTO interviews 
        (interview_id, user_id, doc_id, job_title, status, created_at)
        VALUES ($1, $2, $3, $4, 'IN_PROGRESS', NOW())
        """,
        interview_id, user_id, doc_id, job_title
    )

    # sub-agent generates opening question
    response = await mock_interview_tool(
        skills=skills,
        projects=projects,
        experience=experience,
        conversation_history=[],
        candidate_message="START_INTERVIEW"
    )

    # store interviewer opening question in chat history
    await execute(
        """
        INSERT INTO interview_chats
        (chat_id, interview_id, role, content, stored_at)
        VALUES ($1, $2, 'interviewer', $3, NOW())
        """,
        str(uuid.uuid4()), interview_id,
        response.get("message", "")
    )

    logger.info(f"Interview started — interview_id: {interview_id}")

    return {
        "interview_id": interview_id,
        "message": response.get("message"),
        "type": "question"
    }


@router.post("/interview/{interview_id}/message")
async def send_message(
    interview_id: str,
    req: MessageRequest,
    user=Depends(verify_token)
):
    """
    Candidate sends their answer.
    Loads full history, calls sub-agent, returns next question or verdict.
    """
    user_id = user["user_id"]

    # verify interview belongs to this user
    interview = await fetchrow(
        """
        SELECT i.interview_id, i.doc_id, i.status, i.job_title
        FROM interviews i
        WHERE i.interview_id = $1 AND i.user_id = $2
        """,
        interview_id, user_id
    )

    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found")

    if interview["status"] == "COMPLETED":
        raise HTTPException(status_code=400, detail="Interview already completed")

    # load full conversation history from SQL
    chat_rows = await fetch(
        """
        SELECT role, content FROM interview_chats
        WHERE interview_id = $1
        ORDER BY stored_at ASC
        """,
        interview_id
    )

    # build history in Groq message format
    conversation_history = [
        {
            "role": "assistant" if row["role"] == "interviewer" else "user",
            "content": row["content"]
        }
        for row in chat_rows
    ]

    # store candidate message
    await execute(
        """
        INSERT INTO interview_chats
        (chat_id, interview_id, role, content, stored_at)
        VALUES ($1, $2, 'candidate', $3, NOW())
        """,
        str(uuid.uuid4()), interview_id, req.content
    )

    # fetch candidate profile for sub-agent
    collection = get_document_content()
    doc = await collection.find_one({"doc_id": interview["doc_id"]})

    # call sub-agent with full history + new message
    response = await mock_interview_tool(
        skills=doc.get("skills", []),
        projects=doc.get("projects", []),
        experience=doc.get("experience", []),
        conversation_history=conversation_history,
        candidate_message=req.content
    )

    response_type = response.get("type")

    if response_type == "assessment":
        # interview complete — store verdict
        await _store_verdict(interview_id, user_id, response)

        # mark interview complete
        await execute(
            """
            UPDATE interviews
            SET status = 'COMPLETED', completed_at = NOW()
            WHERE interview_id = $1
            """,
            interview_id
        )

        logger.info(
            f"Interview completed — "
            f"interview_id: {interview_id}, "
            f"verdict: {response.get('verdict')}, "
            f"score: {response.get('score')}"
        )

        return {
            "type": "assessment",
            "interview_id": interview_id,
            "score": response.get("score"),
            "overall_performance": response.get("overall_performance"),
            "verdict": response.get("verdict"),
            "verdict_reason": response.get("verdict_reason"),
            "strong_areas": response.get("strong_areas", []),
            "weak_areas": response.get("weak_areas", []),
            "recommendation": response.get("recommendation"),
            "suggested_topics_to_study": response.get(
                "suggested_topics_to_study", []
            )
        }

    # regular question — store and return
    await execute(
        """
        INSERT INTO interview_chats
        (chat_id, interview_id, role, content, stored_at)
        VALUES ($1, $2, 'interviewer', $3, NOW())
        """,
        str(uuid.uuid4()), interview_id,
        response.get("message", "")
    )

    return {
        "type": "question",
        "interview_id": interview_id,
        "message": response.get("message")
    }


@router.get("/interview/{interview_id}/verdict")
async def get_verdict(
    interview_id: str,
    user=Depends(verify_token)
):
    """Returns stored verdict for a completed interview."""
    verdict = await fetchrow(
        """
        SELECT v.*, i.job_title, i.created_at as interview_date
        FROM interview_verdicts v
        JOIN interviews i ON v.interview_id = i.interview_id
        WHERE v.interview_id = $1 AND v.user_id = $2
        """,
        interview_id, user["user_id"]
    )

    if not verdict:
        raise HTTPException(status_code=404, detail="Verdict not found")

    return dict(verdict)


@router.get("/interviews/history")
async def get_interview_history(user=Depends(verify_token)):
    """
    Returns all interview attempts for a candidate.
    Used for tracking improvement over time.
    """
    rows = await fetch(
        """
        SELECT 
            i.interview_id,
            i.job_title,
            i.status,
            i.created_at,
            i.completed_at,
            v.score,
            v.verdict,
            v.overall_performance
        FROM interviews i
        LEFT JOIN interview_verdicts v ON i.interview_id = v.interview_id
        WHERE i.user_id = $1
        ORDER BY i.created_at DESC
        """,
        user["user_id"]
    )

    return {
        "total_interviews": len(rows),
        "interviews": [dict(row) for row in rows]
    }
@router.get("/interview/{interview_id}")
async def get_interview_state(
    interview_id: str,
    user=Depends(verify_token)
):
    """
    User comes back after 2 days.
    Frontend calls this to check interview state.
    Returns last question so user knows where they left off.
    """
    interview = await fetchrow(
        "SELECT * FROM interviews WHERE interview_id = $1 AND user_id = $2",
        interview_id, user["user_id"]
    )

    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found")

    # get last interviewer message — resume from here
    last_question = await fetchrow(
        """
        SELECT content, stored_at FROM interview_chats
        WHERE interview_id = $1 AND role = 'interviewer'
        ORDER BY stored_at DESC
        LIMIT 1
        """,
        interview_id
    )

    # count exchanges so far
    total_messages = await fetchrow(
        "SELECT COUNT(*) as count FROM interview_chats WHERE interview_id = $1",
        interview_id
    )

    return {
        "interview_id": interview_id,
        "status": interview["status"],
        "job_title": interview["job_title"],
        "started_at": interview["created_at"],
        "last_question": last_question["content"] if last_question else None,
        "last_activity": last_question["stored_at"] if last_question else None,
        "total_exchanges": total_messages["count"]
    }


async def _store_verdict(
    interview_id: str,
    user_id: str,
    assessment: dict
):
    """Stores sub-agent verdict in interview_verdicts table."""
    import json
    await execute(
        """
        INSERT INTO interview_verdicts
        (verdict_id, interview_id, user_id, strong_areas, weak_areas,
         verdict, verdict_reason, recommendation, score, 
         overall_performance, created_at)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, NOW())
        """,
        str(uuid.uuid4()),
        interview_id,
        user_id,
        json.dumps(assessment.get("strong_areas", [])),
        json.dumps(assessment.get("weak_areas", [])),
        assessment.get("verdict", "NEEDS_IMPROVEMENT"),
        assessment.get("verdict_reason", ""),
        assessment.get("recommendation", ""),
        assessment.get("score", 0),
        assessment.get("overall_performance", "AVERAGE")
    )