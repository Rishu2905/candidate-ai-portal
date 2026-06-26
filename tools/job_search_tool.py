from db.postgres_client import fetch
from tools.recommendation_tool import recommendation_tool
from models.schemas import RankedJob
import logging

logger = logging.getLogger(__name__)

async def job_search_tool(
    job_title: str,
    candidate_skills: list[str],
    candidate_projects: list[dict] = None
) -> dict:
    """
    Queries market_jobs table filtered by job title and TTL.
    Ranks each result by calling recommendation_tool for match%.
    Returns top 10 sorted by match percentage descending.
    No live internet calls — purely DB read + LLM ranking.
    """
    try:
        rows = await fetch(
            """
            SELECT job_id, title, skills_required, 
                   source, apply_link, last_date
            FROM market_jobs
            WHERE title ILIKE $1 
            AND expires_at > NOW()
            LIMIT 20
            """,
            f"%{job_title}%"
        )

        if not rows:
            logger.warning(f"No jobs found in market_jobs for title: {job_title}")
            return {
                "jobs": [],
                "message": f"No jobs found for '{job_title}' in market data. "
                           f"Market data may not have been refreshed yet."
            }

        ranked = []
        for row in rows:
            skills_required = row["skills_required"]

            # handle both list and comma-separated string
            if isinstance(skills_required, str):
                skills_required = [s.strip() for s in skills_required.split(",")]

            # call recommendation_tool per job to get match%
            match = await recommendation_tool(
                candidate_skills=candidate_skills,
                target_skills=skills_required,
                candidate_projects=candidate_projects
            )

            job = RankedJob(
                job_id=str(row["job_id"]),
                title=row["title"],
                match_percentage=match.get("match_percentage", 0),
                missing_skills=match.get("missing_skills", []),
                apply_link=row["apply_link"] or "",
                source=row["source"] or "Unknown",
                last_date=str(row["last_date"]) if row["last_date"] else None
            )
            ranked.append(job)

        # sort by match% descending, take top 10
        ranked.sort(key=lambda x: x.match_percentage, reverse=True)
        top_jobs = ranked[:10]

        logger.info(
            f"Job search for '{job_title}': "
            f"{len(rows)} found, "
            f"top match: {top_jobs[0].match_percentage}% "
            f"({top_jobs[0].title})" if top_jobs else "no results"
        )

        return {
            "jobs": [job.model_dump() for job in top_jobs],
            "total_found": len(rows),
            "returned": len(top_jobs)
        }

    except Exception as e:
        logger.error(f"job_search_tool failed for title '{job_title}': {e}")
        return {
            "jobs": [],
            "error": str(e)
        }