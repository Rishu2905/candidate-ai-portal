from pydantic import BaseModel
from typing import Optional
from uuid import UUID

# ── incoming from Java ──────────────────────────────────────────
class AnalyseRequest(BaseModel):
    doc_id: str
    user_id: str
    raw_text: str
    job_title: str

# ── tool output shapes ──────────────────────────────────────────
class ContactInfo(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    linkedin: Optional[str] = None

class Project(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    tech_used: Optional[list[str]] = []

class Experience(BaseModel):
    company: Optional[str] = None
    role: Optional[str] = None
    duration: Optional[str] = None
    description: Optional[str] = None

class Education(BaseModel):
    institution: Optional[str] = None
    degree: Optional[str] = None
    year: Optional[str] = None

class SkillProfile(BaseModel):
    skills: list[str] = []
    projects: list[Project] = []
    experience: list[Experience] = []
    education: list[Education] = []
    contact: Optional[ContactInfo] = None

class RecommendationResult(BaseModel):
    match_percentage: int
    strength: str                    # STRONG | MODERATE | WEAK
    matching_skills: list[str] = []
    missing_skills: list[str] = []
    recommendation: str

class RankedJob(BaseModel):
    job_id: str
    title: str
    match_percentage: int
    missing_skills: list[str] = []
    apply_link: str
    source: str
    last_date: Optional[str] = None

class MarketDemand(BaseModel):
    domain: str
    total_jobs_analyzed: int
    high_demand_skills: list[str] = []
    all_skills: list[dict] = []

# ── stored in MongoDB analysis_content ─────────────────────────
class AnalysisResult(BaseModel):
    doc_id: str
    user_id: str
    skill_profile: Optional[SkillProfile] = None
    market_demand: Optional[MarketDemand] = None
    recommendation: Optional[RecommendationResult] = None
    suggested_jobs: list[RankedJob] = []
    status: str = "PROCESSING"

# ── API responses ───────────────────────────────────────────────
class AnalyseResponse(BaseModel):
    status: str
    doc_id: str
    message: str

class StatusResponse(BaseModel):
    status: str
    doc_id: str
    result: Optional[AnalysisResult] = None