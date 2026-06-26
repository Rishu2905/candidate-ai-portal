from groq import Groq
from config.settings import settings
import json
import logging

logger = logging.getLogger(__name__)

client = Groq(api_key=settings.GROQ_API_KEY)

INTERVIEWER_SYSTEM_PROMPT = """
You are a senior technical interviewer conducting a stress-test interview 
of a software engineering candidate based on their resume.

Your goal is to deeply verify whether the candidate has actually built 
what they claim, understands their own decisions, and can defend their 
work under pressure.

Candidate profile:
Skills: {skills}
Projects: {projects}
Experience: {experience}

Interview rules:
1. Start by picking the most impressive project and asking them to walk 
   you through it at a high level.
2. Drill into technical decisions — "why did you choose X over Y?", 
   "what problems did you face?", "how did you solve them?"
3. Ask about edge cases, failure scenarios, scale considerations.
4. If an answer is vague, push back — "can you be more specific?", 
   "what exactly does that mean in your implementation?"
5. Cover at least 2 projects and key skills before concluding.
6. After sufficient questioning (minimum 6 exchanges), if the candidate 
   says they are done or you have enough data, produce a final assessment.

Final assessment format (return ONLY when interview is complete):
{{
    "type": "assessment",
    "overall_performance": "<STRONG|GOOD|AVERAGE|WEAK>",
    "score": <integer 0-100>,
    "strong_areas": ["area1", "area2"],
    "weak_areas": ["area1", "area2"],
    "projects_verified": ["project1", "project2"],
    "recommendation": "<2-3 sentence summary of candidate performance>",
    "suggested_topics_to_study": ["topic1", "topic2"]
}}

During the interview, respond naturally as an interviewer — no JSON, 
just conversational questions and follow-ups.
Only return the JSON assessment when the interview is complete.
"""

async def mock_interview_tool(
    skills: list[str],
    projects: list[dict],
    experience: list[dict],
    conversation_history: list[dict],
    candidate_message: str
) -> dict:
    """
    Sub-agent that conducts a technical stress-test interview.
    Unlike other tools, this is stateful — maintains conversation
    history across multiple turns.
    
    Returns either:
    - { "type": "question", "message": "interviewer's next question" }
    - { "type": "assessment", ...full performance report... }
    """
    try:
        system_prompt = INTERVIEWER_SYSTEM_PROMPT.format(
            skills=skills,
            projects=json.dumps(projects, indent=2),
            experience=json.dumps(experience, indent=2)
        )

        # build messages — system + full conversation history + new message
        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(conversation_history)
        messages.append({"role": "user", "content": candidate_message})

        response = client.chat.completions.create(
            model=settings.GROQ_MODEL,
            messages=messages,
            temperature=0.7,    # higher than recommendation_tool
                                # interviewer should feel dynamic, not robotic
            max_tokens=1000
        )

        reply = response.choices[0].message.content.strip()

        # check if interviewer returned final assessment JSON
        if reply.startswith("{") or "```json" in reply:
            # clean up markdown fences if present
            clean = reply
            if "```json" in clean:
                clean = clean.split("```json")[1].split("```")[0].strip()
            elif "```" in clean:
                clean = clean.split("```")[1].split("```")[0].strip()

            try:
                assessment = json.loads(clean)
                if assessment.get("type") == "assessment":
                    logger.info(
                        f"Mock interview complete — "
                        f"score: {assessment.get('score')}, "
                        f"performance: {assessment.get('overall_performance')}"
                    )
                    return assessment
            except json.JSONDecodeError:
                pass  # not JSON, treat as regular question

        # regular interview question/follow-up
        logger.info("Mock interview — next question sent")
        return {
            "type": "question",
            "message": reply
        }

    except Exception as e:
        logger.error(f"mock_interview_tool failed: {e}")
        return {
            "type": "error",
            "message": f"Interview session error: {str(e)}"
        }


async def start_interview(
    skills: list[str],
    projects: list[dict],
    experience: list[dict]
) -> dict:
    """
    Kicks off a fresh interview session.
    Call this first — returns the opening question.
    Caller is responsible for storing conversation history.
    """
    opening_message = (
        "I am ready for the interview. "
        "Please start with whichever project or skill you want to focus on."
    )

    return await mock_interview_tool(
        skills=skills,
        projects=projects,
        experience=experience,
        conversation_history=[],
        candidate_message=opening_message
    )