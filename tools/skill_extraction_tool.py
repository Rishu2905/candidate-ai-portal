from db.mongo_client import get_document_content
from models.schemas import SkillProfile, ContactInfo, Project, Experience, Education
import logging

logger = logging.getLogger(__name__)

async def skill_extraction_tool(doc_id: str) -> dict:
    """
    Step 1 in every orchestrator run.
    Reads parsed resume data from MongoDB document_content collection.
    Returns structured candidate profile.
    Everything downstream depends on this being clean.
    """
    try:
        collection = get_document_content()
        content = await collection.find_one({"doc_id": doc_id})

        if not content:
            logger.warning(f"No document found in MongoDB for doc_id: {doc_id}")
            return {
                "error": f"No document found for doc_id: {doc_id}",
                "skills": [],
                "projects": [],
                "experience": [],
                "education": []
            }

        # build contact info
        contact_data = content.get("contact", {})
        contact = ContactInfo(
            name=contact_data.get("name"),
            email=contact_data.get("email"),
            phone=contact_data.get("phone"),
            linkedin=contact_data.get("linkedin")
        )

        # build projects list
        projects = [
            Project(
                name=p.get("name"),
                description=p.get("description"),
                tech_used=p.get("tech_used", [])
            )
            for p in content.get("projects", [])
        ]

        # build experience list
        experience = [
            Experience(
                company=e.get("company"),
                role=e.get("role"),
                duration=e.get("duration"),
                description=e.get("description")
            )
            for e in content.get("experience", [])
        ]

        # build education list
        education = [
            Education(
                institution=ed.get("institution"),
                degree=ed.get("degree"),
                year=ed.get("year")
            )
            for ed in content.get("education", [])
        ]

        profile = SkillProfile(
            skills=content.get("skills", []),
            projects=projects,
            experience=experience,
            education=education,
            contact=contact
        )

        logger.info(
            f"Skill extraction complete for doc_id: {doc_id} "
            f"— {len(profile.skills)} skills, "
            f"{len(profile.projects)} projects"
        )

        return profile.model_dump()

    except Exception as e:
        logger.error(f"skill_extraction_tool failed for doc_id {doc_id}: {e}")
        return {
            "error": str(e),
            "skills": [],
            "projects": [],
            "experience": [],
            "education": []
        }