from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from src.llm_client import LLMClient, LLMError, to_json
from src.schemas import JDAnalysis, ProfileMatch


PROMPT_PATH = Path("prompts/profile_matcher.md")

SKILL_ALIASES = {
    "js": "JavaScript",
    "javascript": "JavaScript",
    "node": "Node.js",
    "nodejs": "Node.js",
    "node.js": "Node.js",
    "nest": "NestJS",
    "nestjs": "NestJS",
    "reactjs": "React",
    "react": "React",
    "llm": "LLM",
    "rag": "RAG",
    "retrieval augmented generation": "RAG",
    "postgres": "PostgreSQL",
    "postgresql": "PostgreSQL",
    "sqlite": "SQLite",
    "docker": "Docker",
}


def normalize_skill(skill: str) -> str:
    key = re.sub(r"\s+", " ", skill.strip().lower())
    return SKILL_ALIASES.get(key, skill.strip())


def profile_skills(profile: dict[str, Any]) -> set[str]:
    skills: set[str] = set()
    for values in profile.get("skills", {}).values():
        for value in values:
            skills.add(normalize_skill(str(value)))
    return skills


def text_contains_skill(text: str, skill: str) -> bool:
    return normalize_skill(skill).lower() in text.lower()


def select_named_items(items: list[dict[str, Any]], keywords: list[str]) -> list[str]:
    selected: list[str] = []
    for item in items:
        blob = json.dumps(item, ensure_ascii=False).lower()
        if any(keyword.lower() in blob for keyword in keywords):
            selected.append(str(item.get("name") or item.get("role") or item.get("company") or "Untitled"))
    return selected[:4]


def rule_based_match(profile: dict[str, Any], analysis: JDAnalysis) -> ProfileMatch:
    known = profile_skills(profile)
    known_lower = {skill.lower(): skill for skill in known}
    must = [normalize_skill(skill) for skill in analysis.must_have_skills]
    nice = [normalize_skill(skill) for skill in analysis.nice_to_have_skills]

    strong = [skill for skill in must if skill.lower() in known_lower]
    partial = [
        skill
        for skill in must + nice
        if skill not in strong and any(skill.lower() in known_skill.lower() or known_skill.lower() in skill.lower() for known_skill in known)
    ]
    missing = [skill for skill in must if skill not in strong and skill not in partial]
    all_keywords = list(dict.fromkeys(analysis.keywords_for_ats + analysis.domain_keywords + must + nice))
    selected_projects = select_named_items(profile.get("projects", []), all_keywords)
    selected_experiences = select_named_items(profile.get("experiences", []), all_keywords)

    must_score = (len(strong) + len(partial) * 0.5) / max(1, len(must)) * 70
    nice_matches = [skill for skill in nice if skill.lower() in known_lower or skill in partial]
    nice_score = len(nice_matches) / max(1, len(nice)) * 20 if nice else 0
    project_score = 10 if selected_projects else 0
    score = int(min(100, round(must_score + nice_score + project_score)))

    return ProfileMatch(
        strong_matches=list(dict.fromkeys(strong)),
        partial_matches=list(dict.fromkeys(partial)),
        missing_skills=list(dict.fromkeys(missing)),
        selected_projects=selected_projects,
        selected_experiences=selected_experiences,
        selected_keywords=all_keywords[:20],
        match_score=score,
        reasoning_summary="Rule-based score from profile skills, JD requirements, and project relevance.",
    )


def match_profile(profile: dict[str, Any], analysis: JDAnalysis, client: LLMClient | None = None) -> ProfileMatch:
    rules = rule_based_match(profile, analysis)
    prompt = (
        PROMPT_PATH.read_text(encoding="utf-8")
        .replace("{{USER_PROFILE_JSON}}", json.dumps(profile, indent=2))
        .replace("{{JD_ANALYSIS_JSON}}", to_json(analysis))
    )
    client = client or LLMClient()
    try:
        llm_match = client.complete_json(prompt, ProfileMatch)
        llm_match.match_score = rules.match_score
        llm_match.missing_skills = rules.missing_skills or llm_match.missing_skills
        llm_match.selected_keywords = list(dict.fromkeys(llm_match.selected_keywords + rules.selected_keywords))[:20]
        return llm_match
    except LLMError:
        return rules
