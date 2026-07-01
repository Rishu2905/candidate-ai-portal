from groq import Groq
from config.settings import settings
from db.mongo_client import get_analysis_content
from db.mongo_client import get_candidate_memory
from db.postgres_client import execute
from tools.skill_extraction_tool import skill_extraction_tool
from tools.recommendation_tool import recommendation_tool
from tools.job_search_tool import job_search_tool
from tools.market_data_tool import market_data_tool
from tools.mock_interview_tool import mock_interview_tool
from tools.interview_retrieval_tool import interview_retrieval_tool
from db.mongo_client import mongo
from datetime import datetime
import json
import logging

logger = logging.getLogger(__name__)

# ── tool registry ─────────────────────────────────────────────────────────────
# maps tool name string → actual async function
# when LLM says "call skill_extraction_tool"
# backend looks up TOOL_REGISTRY["skill_extraction_tool"] and executes it
TOOL_REGISTRY = {
    "skill_extraction_tool":     skill_extraction_tool,
    "recommendation_tool":       recommendation_tool,
    "job_search_tool":           job_search_tool,
    "market_data_tool":          market_data_tool,
    "interview_retrieval_tool":  interview_retrieval_tool,
    "mock_interview_tool":       mock_interview_tool,
}

# ── tool definitions ──────────────────────────────────────────────────────────
# these are the function schemas Groq reads
# LLM reads "description" to decide WHEN to call each tool
# LLM reads "parameters" to know WHAT arguments to pass
# this is your control layer — description wording directly affects LLM behaviour
TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "skill_extraction_tool",
            "description": """ALWAYS call this first, before any other tool.
            Reads candidate resume data from MongoDB using doc_id.
            Returns structured profile: skills list, projects, experience, education.
            If skills list is empty — stop pipeline and return error.
            Everything downstream depends on this output.""",
            "parameters": {
                "type": "object",
                "properties": {
                    "doc_id": {
                        "type": "string",
                        "description": "Document ID of uploaded resume"
                    }
                },
                "required": ["doc_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "market_data_tool",
            "description": """Call second, after skill_extraction_tool.
            Fetches aggregated skill demand data for candidate's target job domain.
            Returns high demand skills and frequency analysis from market data.
            Use job_title as the domain parameter.""",
            "parameters": {
                "type": "object",
                "properties": {
                    "domain": {
                        "type": "string",
                        "description": "Job domain e.g. Backend Developer, Data Analyst"
                    }
                },
                "required": ["domain"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "recommendation_tool",
            "description": """Call third, after market_data_tool.
            Compares candidate skills against market demand.
            Returns match_percentage, strength (STRONG/MODERATE/WEAK),
            matching skills, and missing skills.
            Use high_demand_skills from market_data_tool as target_skills.
            The strength value determines whether interview tools are needed.""",
            "parameters": {
                "type": "object",
                "properties": {
                    "candidate_skills": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Skills from skill_extraction_tool"
                    },
                    "target_skills": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "High demand skills from market_data_tool"
                    },
                    "candidate_projects": {
                        "type": "array",
                        "items": {"type": "object"},
                        "description": "Projects from skill_extraction_tool"
                    }
                },
                "required": ["candidate_skills", "target_skills"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "job_search_tool",
            "description": """Call fourth, after recommendation_tool.
            Searches pre-stored market jobs and ranks by match percentage.
            Returns top 10 jobs with apply links.
            Always call this regardless of candidate strength — 
            every candidate needs job suggestions.""",
            "parameters": {
                "type": "object",
                "properties": {
                    "job_title": {
                        "type": "string",
                        "description": "Target job title to search for"
                    },
                    "candidate_skills": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Candidate skills for ranking"
                    },
                    "candidate_projects": {
                        "type": "array",
                        "items": {"type": "object"},
                        "description": "Candidate projects for ranking"
                    }
                },
                "required": ["job_title", "candidate_skills"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "interview_retrieval_tool",
            "description": """Call this ONLY when recommendation_tool returns
            strength=WEAK or match_percentage < 50.
            Checks if candidate completed an interview recently (within 20 days).

            Decision logic after calling:
            - has_recent_interview = True  → use that verdict, skip mock_interview_tool
            - has_recent_interview = False → proceed to call mock_interview_tool

            NEVER call mock_interview_tool without calling this first.
            NEVER call this if candidate is STRONG or MODERATE.""",
            "parameters": {
                "type": "object",
                "properties": {
                    "user_id": {
                        "type": "string",
                        "description": "Candidate user ID"
                    },
                    "max_age_days": {
                        "type": "integer",
                        "description": "Max age of interview data in days. Default 20."
                    }
                },
                "required": ["user_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "mock_interview_tool",
            "description": """Call ONLY when:
            1. recommendation_tool returned WEAK or match_percentage < 50, AND
            2. interview_retrieval_tool returned has_recent_interview = False

            Delegates to an interviewer sub-agent that autonomously simulates
            a technical stress-test interview using candidate's projects and skills.
            Sub-agent conducts full interview internally and returns assessment.

            Use to determine:
            - Genuine skill gaps → candidate needs to learn more
            - Content delivery problem → candidate knows but can't communicate it

            Pass conversation_history as [] and 
            candidate_message as 'START_AUTONOMOUS_INTERVIEW'.""",
            "parameters": {
                "type": "object",
                "properties": {
                    "skills": {
                        "type": "array",
                        "items": {"type": "string"}
                    },
                    "projects": {
                        "type": "array",
                        "items": {"type": "object"}
                    },
                    "experience": {
                        "type": "array",
                        "items": {"type": "object"}
                    },
                    "conversation_history": {
                        "type": "array",
                        "items": {"type": "object"},
                        "description": "Pass empty list [] for autonomous simulation"
                    },
                    "candidate_message": {
                        "type": "string",
                        "description": "Pass 'START_AUTONOMOUS_INTERVIEW'"
                    }
                },
                "required": [
                    "skills", "projects", "experience",
                    "conversation_history", "candidate_message"
                ]
            }
        }
    }
]

# ── system prompt ─────────────────────────────────────────────────────────────
ORCHESTRATOR_SYSTEM_PROMPT = """
You are an AI career coach analysing a software engineering candidate's resume.
Target role: {job_title}
Document ID: {doc_id}
Candidate ID: {user_id}

CANDIDATE HISTORY (from previous sessions):
{candidate_memory}

Use candidate history to:
- Compare current analysis against previous match scores
- Flag persistent skill gaps (same gaps appearing across analyses)
- Acknowledge improvement if match_percentage increased since last analysis
- Reference interview performance when making final recommendations
- If first time analysis, state this clearly

REQUIRED SEQUENCE — follow this exact order:
1. skill_extraction_tool(doc_id)
   → If skills is empty: stop, return error "Resume not yet parsed"

2. market_data_tool(domain=job_title)
   → Get market skill demand for target role

3. recommendation_tool(candidate_skills, target_skills=high_demand_skills)
   → Compare candidate against market
   → Note the strength value — drives next decision

4. job_search_tool(job_title, candidate_skills)
   → Always call, every candidate needs job suggestions

CONDITIONAL — only when step 3 returns WEAK or match_percentage < 50:

5. interview_retrieval_tool(user_id)
   → Check for recent interview data
   → If has_recent_interview = True: use existing verdict, go to step 7
   → If has_recent_interview = False: proceed to step 6

6. mock_interview_tool (only if step 5 returned has_recent_interview = False)
   → Pass conversation_history=[], candidate_message='START_AUTONOMOUS_INTERVIEW'
   → Sub-agent runs full interview simulation autonomously
   → Returns assessment with score, verdict, weak/strong areas

7. Done — all tools complete

RULES:
- Never call the same tool twice
- Never call mock_interview_tool without calling interview_retrieval_tool first
- Never call interview tools if candidate is STRONG or MODERATE
- Always complete steps 1-4 regardless of strength
- You are conducting a real technical interview.
- Never coach the candidate during the interview.
- Never give suggestions about something can be done better
- Never reveal the correct answer.
- Never provide hints that solve the question.
- Never teach concepts during the interview.
- If the candidate says "I don't know", acknowledge it politely and move to another question.
- If the candidate asks for the answer, politely refuse and continue the interview.
- Your role is to evaluate, not educate.
- Save feedback and explanations for the final assessment after the interview ends.
"""


class GroqOrchestrator:
    """
    The manager. Runs the ReAct loop.

    What it does:
    1. Fetches candidate long term memory from MongoDB
    2. Builds initial messages list with system prompt + memory injected
    3. Sends messages to Groq
    4. Reads response — did LLM request a tool?
    5. If yes: looks up tool in TOOL_REGISTRY, executes it, appends result to messages
    6. Sends updated messages back to Groq
    7. Repeats until Groq says stop (finish_reason = "stop")
    8. Stores all tool results in MongoDB analysis_content
    9. Updates candidate_memory with latest state
    10. Updates document status in PostgreSQL

    What it does NOT do:
    - Does not execute tool logic itself
    - Does not decide which tool to call (LLM decides)
    - Does not know what tools return (passes results straight back to LLM)
    """

    def __init__(self):
        self.client = Groq(api_key=settings.GROQ_API_KEY)
        self.model = settings.GROQ_MODEL

    async def run(
        self,
        doc_id: str,
        user_id: str,
        job_title: str
    ) -> dict:
        logger.info(
            f"Orchestrator started — "
            f"doc_id: {doc_id}, "
            f"user_id: {user_id}, "
            f"job_title: {job_title}"
        )

        # mark as processing immediately so frontend knows it started
        await self._update_analysis_status(doc_id, user_id, "PROCESSING")

        # ── step 1: fetch long term memory ───────────────────────────────────
        # this is how LLM knows candidate's previous state
        # injected into system prompt before first message
        candidate_memory = await self._get_candidate_memory(user_id)
        memory_str = (
            json.dumps(candidate_memory, indent=2, default=str)
            if candidate_memory
            else "No previous history — this is the candidate's first analysis."
        )

        # ── step 2: build initial messages ───────────────────────────────────
        # system prompt contains: role, instructions, candidate history
        # user message triggers the pipeline
        messages = [
            {
                "role": "system",
                "content": ORCHESTRATOR_SYSTEM_PROMPT.format(
                    job_title=job_title,
                    doc_id=doc_id,
                    user_id=user_id,
                    candidate_memory=memory_str
                )
            },
            {
                "role": "user",
                "content": (
                    f"Run complete career analysis pipeline. "
                    f"doc_id: {doc_id}, "
                    f"user_id: {user_id}, "
                    f"target role: {job_title}."
                )
            }
        ]

        tool_results = {}
        tool_call_count = 0
        max_tool_calls = 12  # safety ceiling — 6 tools, some may retry

        try:
            # ── step 3: ReAct loop ────────────────────────────────────────────
            while tool_call_count < max_tool_calls:

                # send full messages list to Groq
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    tools=TOOL_DEFINITIONS,
                    tool_choice="auto",
                    temperature=0.2,
                    max_tokens=2000
                )

                msg = response.choices[0].message
                finish_reason = response.choices[0].finish_reason

                logger.info(f"Groq response — finish_reason: {finish_reason}")

                # ── finish_reason = "stop" means LLM is done ─────────────────
                # no more tool calls — exit loop
                if finish_reason == "stop" or not msg.tool_calls:
                    logger.info(
                        f"Orchestrator loop complete — "
                        f"{tool_call_count} tools called"
                    )
                    break

                # ── finish_reason = "tool_calls" means LLM wants a tool ──────
                # append assistant message (with tool_calls) to history
                # Groq requires this to be in messages before tool results
                messages.append({
                    "role": "assistant",
                    "content": msg.content,
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments
                            }
                        }
                        for tc in msg.tool_calls
                    ]
                })

                # ── dispatch each tool call ───────────────────────────────────
                for tool_call in msg.tool_calls:
                    fn_name = tool_call.function.name
                    tool_call_count += 1

                    logger.info(
                        f"Tool call #{tool_call_count}: {fn_name} "
                        f"(id: {tool_call.id})"
                    )

                    # parse arguments — comes as JSON string, must parse
                    try:
                        fn_args = json.loads(tool_call.function.arguments)
                    except json.JSONDecodeError as e:
                        logger.error(f"Failed to parse args for {fn_name}: {e}")
                        fn_args = {}

                    # look up tool in registry
                    fn = TOOL_REGISTRY.get(fn_name)

                    if fn:
                        try:
                            # execute tool
                            result = await fn(**fn_args)
                            logger.info(f"Tool {fn_name} completed successfully")
                        except Exception as e:
                            logger.error(f"Tool {fn_name} raised exception: {e}")
                            result = {"error": str(e), "tool": fn_name}
                    else:
                        logger.warning(f"Unknown tool requested: {fn_name}")
                        result = {"error": f"Unknown tool: {fn_name}"}

                    # store result for final assembly
                    tool_results[fn_name] = result

                    # append tool result to messages
                    # tool_call_id MUST match the id from the tool_call above
                    # Groq uses this to match result → request
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": json.dumps(result, default=str)
                    })

            # ── step 4: store results ─────────────────────────────────────────
            await self._store_results(doc_id, user_id, job_title, tool_results)

            # ── step 5: update long term memory ──────────────────────────────
            await self._update_candidate_memory(user_id, job_title, tool_results)

            # ── step 6: update document status in SQL ────────────────────────
            await self._update_document_status(doc_id, "COMPLETE")

            logger.info(f"Orchestrator complete for doc_id: {doc_id}")
            return {"status": "COMPLETE", "doc_id": doc_id}

        except Exception as e:
            logger.error(f"Orchestrator failed for doc_id {doc_id}: {e}")
            await self._update_analysis_status(doc_id, user_id, "FAILED")
            await self._update_document_status(doc_id, "FAILED")
            return {"status": "FAILED", "doc_id": doc_id, "error": str(e)}

    # ── storage helpers ───────────────────────────────────────────────────────

    async def _get_candidate_memory(self, user_id: str) -> dict:
        """
        Fetches candidate's long term memory from MongoDB.
        Returns empty dict if first time — orchestrator handles gracefully.
        """
        try:
            collection = get_candidate_memory()
            memory = await collection.find_one(
                {"user_id": user_id},
                {"_id": 0}
            )
            return memory or {}
        except Exception as e:
            logger.error(f"Failed to fetch candidate memory: {e}")
            return {}

    async def _store_results(
        self,
        doc_id: str,
        user_id: str,
        job_title: str,
        tool_results: dict
    ):
        """
        Assembles all tool outputs into one document.
        Upserts into MongoDB analysis_content.
        This is the permanent record of this analysis run.
        """
        skill_profile  = tool_results.get("skill_extraction_tool", {})
        market_demand  = tool_results.get("market_data_tool", {})
        recommendation = tool_results.get("recommendation_tool", {})
        job_search     = tool_results.get("job_search_tool", {})
        interview_data = tool_results.get("interview_retrieval_tool", None)
        mock_interview = tool_results.get("mock_interview_tool", None)

        document = {
            "doc_id":        doc_id,
            "user_id":       user_id,
            "job_title":     job_title,
            "skill_profile": skill_profile,
            "market_demand": market_demand,
            "recommendation": recommendation,
            "suggested_jobs": job_search.get("jobs", []),
            "interview_data": interview_data,
            "mock_interview_assessment": mock_interview,
            "status":     "COMPLETE",
            "updated_at": datetime.utcnow().isoformat()
        }

        collection = get_analysis_content()
        await collection.update_one(
            {"doc_id": doc_id},
            {"$set": document},
            upsert=True
        )

    async def _update_candidate_memory(
        self,
        user_id: str,
        job_title: str,
        tool_results: dict
    ):
        """
        Updates candidate's long term memory after every analysis.
        $set  → overwrites current state with latest
        $push → appends to history array (never loses old data)

        This is what the LLM reads on next launch to understand
        where the candidate was before.
        """
        try:
            recommendation = tool_results.get("recommendation_tool", {})
            skill_profile  = tool_results.get("skill_extraction_tool", {})
            market_demand  = tool_results.get("market_data_tool", {})
            mock_interview = tool_results.get("mock_interview_tool", {})
            interview_data = tool_results.get("interview_retrieval_tool", {})

            # determine interview summary for memory
            # use mock_interview if ran, else use retrieved verdict if found
            interview_summary = None
            if mock_interview and mock_interview.get("type") == "assessment":
                interview_summary = {
                    "score":               mock_interview.get("score"),
                    "verdict":             mock_interview.get("verdict"),
                    "overall_performance": mock_interview.get("overall_performance"),
                    "weak_areas":          mock_interview.get("weak_areas", []),
                    "strong_areas":        mock_interview.get("strong_areas", []),
                    "date":                datetime.utcnow().isoformat(),
                    "source":              "autonomous_simulation"
                }
            elif interview_data and interview_data.get("has_recent_interview"):
                interview_summary = {
                    "score":               interview_data.get("score"),
                    "verdict":             interview_data.get("verdict"),
                    "overall_performance": interview_data.get("overall_performance"),
                    "weak_areas":          interview_data.get("weak_areas", []),
                    "strong_areas":        interview_data.get("strong_areas", []),
                    "date":                interview_data.get("interview_date"),
                    "source":              "candidate_initiated"
                }

            # current state — always overwritten with latest
            current_state = {
                "user_id":                  user_id,
                "target_role":              job_title,
                "latest_skills":            skill_profile.get("skills", []),
                "latest_skill_gaps":        recommendation.get("missing_skills", []),
                "latest_match_percentage":  recommendation.get("match_percentage"),
                "latest_strength":          recommendation.get("strength"),
                "market_high_demand_skills": market_demand.get("high_demand_skills", []),
                "last_analysed_at":         datetime.utcnow().isoformat()
            }

            if interview_summary:
                current_state["latest_interview"] = interview_summary

            # history snapshot — one entry per analysis, never deleted
            history_entry = {
                "date":             datetime.utcnow().isoformat(),
                "job_title":        job_title,
                "match_percentage": recommendation.get("match_percentage"),
                "strength":         recommendation.get("strength"),
                "skill_gaps":       recommendation.get("missing_skills", []),
                "interview_score":  interview_summary.get("score") if interview_summary else None
            }

            collection = get_candidate_memory()
            await collection.update_one(
                {"user_id": user_id},
                {
                    "$set":  current_state,
                    "$push": {"analysis_history": history_entry}
                },
                upsert=True
            )

            logger.info(f"Candidate memory updated for user_id: {user_id}")

        except Exception as e:
            # non-critical — don't fail the whole pipeline if memory update fails
            logger.error(f"Failed to update candidate memory: {e}")

    async def _update_analysis_status(
        self,
        doc_id: str,
        user_id: str,
        status: str
    ):
        """Updates status in MongoDB — lets frontend poll progress."""
        try:
            collection = get_analysis_content()
            await collection.update_one(
                {"doc_id": doc_id},
                {"$set": {
                    "doc_id":     doc_id,
                    "user_id":    user_id,
                    "status":     status,
                    "updated_at": datetime.utcnow().isoformat()
                }},
                upsert=True
            )
        except Exception as e:
            logger.error(f"Failed to update analysis status: {e}")

    async def _update_document_status(self, doc_id: str, status: str):
        """Updates document status in PostgreSQL documents table."""
        try:
            await execute(
                """
                UPDATE documents
                SET status = $1, updated_at = NOW()
                WHERE doc_id = $2
                """,
                status, doc_id
            )
        except Exception as e:
            logger.error(f"Failed to update document status in SQL: {e}")


# single instance — imported by routers
orchestrator = GroqOrchestrator()