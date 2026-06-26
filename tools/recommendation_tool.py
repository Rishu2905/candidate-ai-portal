from groq import Groq
from config.settings import settings
from models.schemas import RecommendationResult
import json
import logging

logger = logging.getLogger(__name__)

client = Groq(api_key=settings.GROQ_API_KEY)

RECOMMENDATION_PROMPT = """
You are a senior technical recruiter evaluating a candidate for a role.

Candidate skills: {candidate_skills}
Candidate projects: {candidate_projects}
Required skills for role: {target_skills}

Evaluate the candidate and return ONLY valid JSON with no explanation, 
no markdown, no code blocks. Just raw JSON:

{{
    "match_percentage": <integer 0-100>,
    "strength": "<STRONG|MODERATE|WEAK>",
    "matching_skills": ["skill1", "skill2"],
    "missing_skills": ["skill3", "skill4"],
    "recommendation": "<one clear sentence summarising fit>"
}}

Scoring rules:
- match_percentage: percentage of required skills candidate has 
  (directly or via project experience)
- STRONG: match_percentage >= 75
- MODERATE: match_percentage >= 50
- WEAK: match_percentage < 50
- Count project tech_used as implicit skills
- Be objective, not generous
"""

async def recommendation_tool(
    candidate_skills: list[str],
    target_skills: list[str],
    candidate_projects: list[dict] = None
) -> dict:
    """
    Compares candidate skill set against a target skill set.
    Returns match percentage, strength, gaps.
    Reused for: JD comparison, market comparison, job ranking.
    temperature=0.1 — scoring must be consistent, not creative.
    """
    try:
        prompt = RECOMMENDATION_PROMPT.format(
            candidate_skills=candidate_skills,
            candidate_projects=candidate_projects or [],
            target_skills=target_skills
        )

        response = client.chat.completions.create(
            model=settings.GROQ_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,    # low — consistent scoring
            max_tokens=500
        )

        raw = response.choices[0].message.content.strip()

        # strip markdown fences if model wraps in ```json
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        raw = raw.strip()

        result = json.loads(raw)

        # validate via pydantic
        validated = RecommendationResult(
            match_percentage=result.get("match_percentage", 0),
            strength=result.get("strength", "WEAK"),
            matching_skills=result.get("matching_skills", []),
            missing_skills=result.get("missing_skills", []),
            recommendation=result.get("recommendation", "")
        )

        logger.info(
            f"Recommendation: {validated.match_percentage}% "
            f"({validated.strength})"
        )

        return validated.model_dump()

    except json.JSONDecodeError as e:
        logger.error(f"recommendation_tool JSON parse failed: {e}")
        return {
            "match_percentage": 0,
            "strength": "WEAK",
            "matching_skills": [],
            "missing_skills": target_skills,
            "recommendation": "Could not evaluate — parse error"
        }
    except Exception as e:
        logger.error(f"recommendation_tool failed: {e}")
        return {
            "match_percentage": 0,
            "strength": "WEAK",
            "matching_skills": [],
            "missing_skills": [],
            "recommendation": f"Evaluation failed: {str(e)}"
        }