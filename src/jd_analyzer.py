from __future__ import annotations

import re
from pathlib import Path

from src.llm_client import LLMClient, LLMError
from src.schemas import JDAnalysis


PROMPT_PATH = Path("prompts/jd_analyzer.md")


COMMON_SKILLS = [
    "Python",
    "JavaScript",
    "TypeScript",
    "React",
    "Node.js",
    "NestJS",
    "FastAPI",
    "Django",
    "SQL",
    "PostgreSQL",
    "SQLite",
    "Docker",
    "Git",
    "REST",
    "GraphQL",
    "LLM",
    "RAG",
    "Machine Learning",
    "PyTorch",
    "TensorFlow",
    "AWS",
    "GCP",
    "Azure",
]


def clean_jd(text: str) -> str:
    return re.sub(r"\n{3,}", "\n\n", text.strip())


def analyze_jd(jd_text: str, client: LLMClient | None = None) -> JDAnalysis:
    jd_text = clean_jd(jd_text)
    prompt = PROMPT_PATH.read_text(encoding="utf-8").replace("{{JD_TEXT}}", jd_text)
    client = client or LLMClient()
    try:
        return client.complete_json(prompt, JDAnalysis)
    except LLMError:
        return fallback_analysis(jd_text)


def fallback_analysis(jd_text: str) -> JDAnalysis:
    lines = [line.strip() for line in jd_text.splitlines() if line.strip()]
    role_title = next((line for line in lines[:8] if len(line) < 90), "Unknown Role")
    found_skills = [skill for skill in COMMON_SKILLS if re.search(rf"\b{re.escape(skill)}\b", jd_text, re.I)]
    responsibilities = [
        line.lstrip("-* ")
        for line in lines
        if re.search(r"\b(build|develop|design|implement|maintain|collaborate|deploy|integrate)\b", line, re.I)
    ][:8]
    return JDAnalysis(
        role_title=role_title,
        jd_summary="Fallback summary: local LLM was unavailable, so this analysis was extracted with simple rules.",
        must_have_skills=found_skills[:8],
        nice_to_have_skills=found_skills[8:14],
        responsibilities=responsibilities,
        keywords_for_ats=found_skills,
        domain_keywords=[],
        soft_skills=[],
    )
