from fastapi import APIRouter, Depends, HTTPException
from db.postgres_client import execute, fetchrow, fetch
from db.mongo_client import get_document_content
from tools.mock_interview_tool import mock_interview_tool
from security.jwt_verify import verify_token
from pydantic import BaseModel
from datetime import datetime
import uuid
import json
import logging
from bson import ObjectId
from db.mongo_client import mongo

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Mock Interview"])

class MessageRequest(BaseModel):
    content: str
# interview_router.py

class StartInterviewRequest(BaseModel):
    user_id: str
    doc_id: str    # ← added — Java sends this now required to store interview data imn sql
    mongo_id: str #<- required for accessing data from mongo


@router.post("/start")
async def start_interview(req: StartInterviewRequest):
    collection = get_document_content()
    
    # debug — print exactly what we received
    print(f"Received mongo_id: {req.mongo_id}")
    print(f"Received user_id: {req.user_id}")
    
    # debug — print all documents in collection
    from db.mongo_client import mongo
    db = mongo.resume_client["hr-dev"]
    collection=db["resumes"]
    try:
        from bson import ObjectId
        doc = await collection.find_one({"_id": ObjectId(req.mongo_id)})
        print(f"Query by ObjectId result: {doc}")
    except Exception as e:
        print(f"ObjectId conversion failed: {e}")
        doc = await collection.find_one({"_id": req.doc_id})
        print(f"Query by string result: {doc}")

    if not doc:
        raise HTTPException(
            status_code=404,
            detail="Resume not found."
        )
    skills = doc.get("skills", [])
    projects = doc.get("projects", [])
    experience = doc.get("experience", [])

    if not skills and not projects:
        raise HTTPException(
            status_code=400,
            detail="Resume has no skills or projects to interview on."
        )

    # create interview session in SQL
    interview_id = str(uuid.uuid4())
    await execute(
        """
        INSERT INTO interviews
        (interview_id, user_id, doc_id, job_title, status, created_at)
        VALUES ($1, $2, $3, $4, 'IN_PROGRESS', NOW())
        """,
        interview_id,
        req.user_id,
        req.doc_id,
        doc.get("jobTitle", "Software Engineer")
    )

    # sub-agent generates opening question
    response = await mock_interview_tool(
        skills=skills,
        projects=projects,
        experience=experience,
        conversation_history=[],
        candidate_message="START_INTERVIEW"
    )

    opening_question = response.get("message", "")

    # store opening question
    await execute(
        """
        INSERT INTO interview_chats
        (chat_id, interview_id, role, content, stored_at)
        VALUES ($1, $2, 'interviewer', $3, NOW())
        """,
        str(uuid.uuid4()),
        interview_id,
        opening_question
    )

    logger.info(
        f"Interview started — "
        f"interview_id: {interview_id}, "
        f"user_id: {req.user_id}, "
        f"doc_id: {req.doc_id}"
    )

    return {
        "interview_id": interview_id,
        "type": "question",
        "message": opening_question
    }

@router.post("/{interview_id}/message")
async def send_message(interview_id: str, req: MessageRequest):

    interview = await fetchrow(
        """
        SELECT
        i.interview_id,
        i.doc_id,
        i.user_id,
        i.status,
        i.job_title,
        d.mongo_id
        FROM interviews i
        JOIN documents d
        ON i.doc_id = d.document_id
        WHERE i.interview_id = $1
        """,
        interview_id
    )

    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found")

    if interview["status"] == "COMPLETED":
        raise HTTPException(status_code=400, detail="Interview already completed")

    # load history
    chat_rows = await fetch(
        """
        SELECT role, content FROM interview_chats
        WHERE interview_id = $1 ORDER BY stored_at ASC
        """,
        interview_id
    )

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

    # fetch doc directly by docId — stored in interviews table
    #collection = get_document_content()
    db = mongo.resume_client["hr-dev"]
    collection=db["resumes"]
    doc = await collection.find_one({"_id": ObjectId(interview["mongo_id"])
})

    response = await mock_interview_tool(
        skills=doc.get("skills", []) if doc else [],
        projects=doc.get("projects", []) if doc else [],
        experience=doc.get("experience", []) if doc else [],
        conversation_history=conversation_history,
        candidate_message=req.content
    )

    response_type = response.get("type")

    if response_type == "assessment":
        await _store_verdict(interview_id, interview["user_id"], response)
        await execute(
            "UPDATE interviews SET status='COMPLETED', completed_at=NOW() WHERE interview_id=$1",
            interview_id
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
            "suggested_topics_to_study": response.get("suggested_topics_to_study", [])
        }

    next_question = response.get("message", "")
    await execute(
        """
        INSERT INTO interview_chats
        (chat_id, interview_id, role, content, stored_at)
        VALUES ($1, $2, 'interviewer', $3, NOW())
        """,
        str(uuid.uuid4()), interview_id, next_question
    )

    return {
        "type": "question",
        "interview_id": interview_id,
        "message": next_question
    }
# comment out this methid before pushing to github
@router.get("/debug/collections")
async def debug_collections():
    """
    Temporary debug endpoint.
    Remove after fixing.
    """
    from db.mongo_client import mongo
    
    # list all databases on this cluster
    databases = await mongo.resume_client.list_database_names()
    db = mongo.resume_client["hr-dev"]

    collections = await db.list_collection_names()
    collection=db["resumes"]
    #document = await collections[0].find(0)
    documents = await collection.find_one({"_id":ObjectId("6a4204a8e2f5f340cf9b2574")})

    print("collections :",collections)
    print("collection data: ",documents)
    #print("collection data:",document)
    print("db list")
    print(databases)

    
    # list all collections in resumedata db
    collections = await mongo.resume_db.list_collection_names()
    print("collection list")
    print(collections)
    
    # count documents in resumes collection
    count = await mongo.resume_db["resumes"].count_documents({})
    
    # fetch first document raw
    first_doc = await mongo.resume_db["resumes"].find_one({})
    
    return {
        "databases_on_cluster": databases,
        "collections_in_resumedata": collections,
        "document_count_in_resumes": count,
        "first_document_id": str(first_doc["_id"]) if first_doc else None,
        "first_document_keys": list(first_doc.keys()) if first_doc else []
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