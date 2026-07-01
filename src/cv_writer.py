from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.llm_client import LLMClient, LLMError, to_json
from src.profile_matcher import profile_skills
from src.schemas import CVContent, JDAnalysis, ProfileMatch


PROMPT_PATH = Path("prompts/cv_writer.md")


def generate_cv_content(
    profile: dict[str, Any],
    analysis: JDAnalysis,
    match: ProfileMatch,
    client: LLMClient | None = None,
) -> CVContent:
    prompt = (
        PROMPT_PATH.read_text(encoding="utf-8")
        .replace("{{USER_PROFILE_JSON}}", json.dumps(profile, indent=2))
        .replace("{{JD_ANALYSIS_JSON}}", to_json(analysis))
        .replace("{{PROFILE_MATCH_JSON}}", to_json(match))
    )
    client = client or LLMClient()
    try:
        content = client.complete_json(prompt, CVContent)
    except LLMError:
        content = fallback_cv_content(profile, analysis, match)
    return limit_cv_content(content)


def fallback_cv_content(profile: dict[str, Any], analysis: JDAnalysis, match: ProfileMatch) -> CVContent:
    personal = profile.get("personal", {})
    skills = profile.get("skills", {})
    summary_facts = profile.get("summary_facts", [])
    summary = " ".join(str(fact) for fact in summary_facts[:2]) or (
        f"{personal.get('name', 'Candidate')} with relevant technical skills for {analysis.role_title}."
    )
    experiences = []
    for item in profile.get("experiences", [])[:3]:
        experiences.append(
            {
                "role": item.get("role", ""),
                "company": item.get("company", ""),
                "date": " - ".join(filter(None, [item.get("start_date"), item.get("end_date")])) or item.get("date", ""),
                "bullets": (item.get("bullets") or item.get("bullets_json") or [])[:3],
            }
        )
    projects = []
    selected = set(match.selected_projects)
    source_projects = profile.get("projects", [])
    ordered_projects = [p for p in source_projects if p.get("name") in selected] + [p for p in source_projects if p.get("name") not in selected]
    for item in ordered_projects[:3]:
        projects.append(
            {
                "name": item.get("name", ""),
                "technologies": item.get("technologies", []),
                "bullets": (item.get("bullets") or [])[:3],
            }
        )
    return CVContent(
        headline=f"{analysis.role_title} | {', '.join(sorted(profile_skills(profile))[:4])}",
        summary=summary,
        skills={
            "AI & LLM": skills.get("ai_llm", []),
            "Backend": skills.get("backend", []),
            "Frontend": skills.get("frontend", []),
            "Database & Search": skills.get("database_search", []),
            "DevOps": skills.get("devops", []),
        },
        experiences=experiences,
        projects=projects,
        education=profile.get("education", []),
        ats_keywords_used=match.selected_keywords[:15],
        warnings=["Generated with rule-based fallback because the local LLM was unavailable."],
    )


def limit_cv_content(content: CVContent) -> CVContent:
    content.summary = " ".join(content.summary.split()[:80])
    content.experiences = [
        {**experience, "bullets": list(experience.get("bullets", []))[:3]} for experience in content.experiences[:3]
    ]
    content.projects = [{**project, "bullets": list(project.get("bullets", []))[:3]} for project in content.projects[:4]]
    return content
