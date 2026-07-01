from __future__ import annotations

from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class JDAnalysis(BaseModel):
    company: Optional[str] = None
    role_title: str = "Unknown Role"
    seniority: Optional[str] = None
    employment_type: Optional[str] = None
    location: Optional[str] = None
    jd_summary: str = ""
    must_have_skills: List[str] = Field(default_factory=list)
    nice_to_have_skills: List[str] = Field(default_factory=list)
    responsibilities: List[str] = Field(default_factory=list)
    keywords_for_ats: List[str] = Field(default_factory=list)
    domain_keywords: List[str] = Field(default_factory=list)
    soft_skills: List[str] = Field(default_factory=list)


class ProfileMatch(BaseModel):
    strong_matches: List[str] = Field(default_factory=list)
    partial_matches: List[str] = Field(default_factory=list)
    missing_skills: List[str] = Field(default_factory=list)
    selected_projects: List[str] = Field(default_factory=list)
    selected_experiences: List[str] = Field(default_factory=list)
    selected_keywords: List[str] = Field(default_factory=list)
    match_score: int = 0
    reasoning_summary: str = ""


class CVContent(BaseModel):
    headline: str = ""
    summary: str = ""
    skills: Dict[str, List[str]] = Field(default_factory=dict)
    experiences: List[Dict] = Field(default_factory=list)
    projects: List[Dict] = Field(default_factory=list)
    education: List[Dict] = Field(default_factory=list)
    ats_keywords_used: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


class CVReview(BaseModel):
    hallucination_risks: List[str] = Field(default_factory=list)
    missing_keywords: List[str] = Field(default_factory=list)
    weak_bullets: List[str] = Field(default_factory=list)
    latex_risks: List[str] = Field(default_factory=list)
    final_quality_score: int = 0
    recommendation: Literal["approve", "revise"] = "revise"
