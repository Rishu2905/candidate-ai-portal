from db.postgres_client import fetch
from models.schemas import MarketDemand
import logging

logger = logging.getLogger(__name__)

async def market_data_tool(domain: str) -> dict:
    """
    Queries market_jobs table for a given job domain.
    Aggregates skills_required across all matching rows.
    Returns high demand skills (appear in >50% of postings)
    and full ranked skill frequency list.
    """
    try:
        rows = await fetch(
            """
            SELECT skills_required 
            FROM market_jobs
            WHERE title ILIKE $1 
            AND expires_at > NOW()
            """,
            f"%{domain}%"
        )

        if not rows:
            logger.warning(f"No market data found for domain: {domain}")
            return MarketDemand(
                domain=domain,
                total_jobs_analyzed=0,
                high_demand_skills=[],
                all_skills=[],
            ).model_dump() | {"message": f"No market data available for {domain}"}

        # aggregate skill frequency across all matching jobs
        skill_count: dict[str, int] = {}
        for row in rows:
            skills = row["skills_required"]
            # handle both list and comma-separated string
            if isinstance(skills, str):
                skills = [s.strip() for s in skills.split(",")]
            for skill in skills:
                if skill:
                    skill_count[skill] = skill_count.get(skill, 0) + 1

        total = len(rows)
        sorted_skills = sorted(
            skill_count.items(),
            key=lambda x: x[1],
            reverse=True
        )

        # skill appears in >50% of postings = high demand
        high_demand = [s for s, c in sorted_skills if c > total * 0.5]
        all_skills = [
            {"skill": s, "frequency": c, "percentage": round((c / total) * 100)}
            for s, c in sorted_skills[:20]
        ]

        result = MarketDemand(
            domain=domain,
            total_jobs_analyzed=total,
            high_demand_skills=high_demand,
            all_skills=all_skills
        )

        logger.info(
            f"Market data for '{domain}': "
            f"{total} jobs analyzed, "
            f"{len(high_demand)} high demand skills"
        )

        return result.model_dump()

    except Exception as e:
        logger.error(f"market_data_tool failed for domain '{domain}': {e}")
        return {
            "domain": domain,
            "total_jobs_analyzed": 0,
            "high_demand_skills": [],
            "all_skills": [],
            "error": str(e)
        }