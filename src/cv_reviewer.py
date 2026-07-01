from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.llm_client import LLMClient, LLMError, to_json
from src.schemas import CVContent, CVReview, JDAnalysis


PROMPT_PATH = Path("prompts/cv_reviewer.md")
LATEX_RISK_CHARS = ["&", "%", "$", "#", "_", "{", "}", "~", "^", "\\"]


def review_cv(
    profile: dict[str, Any],
    analysis: JDAnalysis,
    content: CVContent,
    client: LLMClient | None = None,
) -> CVReview:
    prompt = (
        PROMPT_PATH.read_text(encoding="utf-8")
        .replace("{{USER_PROFILE_JSON}}", json.dumps(profile, indent=2))
        .replace("{{JD_ANALYSIS_JSON}}", to_json(analysis))
        .replace("{{CV_CONTENT_JSON}}", to_json(content))
    )
    client = client or LLMClient()
    try:
        return client.complete_json(prompt, CVReview)
    except LLMError:
        return fallback_review(analysis, content)


def fallback_review(analysis: JDAnalysis, content: CVContent) -> CVReview:
    text = to_json(content).lower()
    missing_keywords = [keyword for keyword in analysis.keywords_for_ats if keyword.lower() not in text]
    weak_bullets = [
        bullet
        for section in content.experiences + content.projects
        for bullet in section.get("bullets", [])
        if len(str(bullet).split()) < 5
    ][:8]
    latex_risks = [char for char in LATEX_RISK_CHARS if char in to_json(content)]
    score = max(50, 95 - len(missing_keywords) * 3 - len(weak_bullets) * 5)
    return CVReview(
        hallucination_risks=[],
        missing_keywords=missing_keywords[:10],
        weak_bullets=weak_bullets,
        latex_risks=latex_risks,
        final_quality_score=score,
        recommendation="approve" if score >= 75 else "revise",
    )
