from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from src import db
from src.schemas import CVContent, CVReview, JDAnalysis, ProfileMatch


PROFILE_PATH = Path("data/profile_seed.json")
EXPORTS_DIR = Path("exports")


DEFAULT_PROFILE = {
    "personal": {
        "name": "",
        "email": "",
        "phone": "",
        "location": "",
        "github": "",
        "linkedin": "",
        "website": "",
    },
    "target_roles": [
        "AI Engineer Intern",
        "Junior AI Engineer",
        "Junior Backend Developer",
        "Junior Full-stack Developer",
    ],
    "summary_facts": [],
    "skills": {
        "ai_llm": [],
        "backend": [],
        "frontend": [],
        "database_search": [],
        "devops": [],
    },
    "experiences": [],
    "projects": [],
    "education": [],
}


def load_profile() -> dict[str, Any]:
    PROFILE_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not PROFILE_PATH.exists():
        save_profile(DEFAULT_PROFILE)
    return json.loads(PROFILE_PATH.read_text(encoding="utf-8"))


def save_profile(profile: dict[str, Any]) -> None:
    PROFILE_PATH.parent.mkdir(parents=True, exist_ok=True)
    PROFILE_PATH.write_text(json.dumps(profile, indent=2), encoding="utf-8")
    db.init_db()
    db.upsert_profile(profile)


def safe_slug(value: str | None) -> str:
    value = (value or "unknown").lower()
    value = re.sub(r"[^a-z0-9]+", "_", value)
    return value.strip("_") or "unknown"


def export_dir(company: str | None, role: str | None) -> Path:
    date = datetime.now().strftime("%Y-%m-%d")
    path = EXPORTS_DIR / f"{date}_{safe_slug(company)}_{safe_slug(role)}"
    suffix = 2
    original = path
    while path.exists():
        path = Path(f"{original}_{suffix}")
        suffix += 1
    path.mkdir(parents=True, exist_ok=True)
    return path


def write_json(path: Path, data: Any) -> None:
    if hasattr(data, "model_dump"):
        data = data.model_dump()
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def write_notes(
    path: Path,
    analysis: JDAnalysis,
    match: ProfileMatch,
    status: str,
    created_at: datetime,
) -> None:
    path.write_text(
        "\n".join(
            [
                f"# {analysis.company or 'Unknown Company'} - {analysis.role_title}",
                "",
                f"Company: {analysis.company or ''}",
                f"Role: {analysis.role_title}",
                f"JD Summary: {analysis.jd_summary}",
                f"Strong Matches: {', '.join(match.strong_matches)}",
                f"Partial Matches: {', '.join(match.partial_matches)}",
                f"Missing Skills: {', '.join(match.missing_skills)}",
                f"Selected Projects: {', '.join(match.selected_projects)}",
                f"Application Status: {status}",
                f"Created At: {created_at.isoformat(timespec='seconds')}",
                "",
            ]
        ),
        encoding="utf-8",
    )


def persist_generation(
    jd_raw: str,
    analysis: JDAnalysis,
    match: ProfileMatch,
    cv_content: CVContent,
    review: CVReview,
    template_name: str,
    latex_path: Path,
    pdf_path: Path | None,
    notes_path: Path,
    status: str = "draft",
) -> int:
    db.init_db()
    with db.connect() as conn:
        cur = conn.execute(
            """
            INSERT INTO job_applications (
                company, role_title, jd_raw, jd_summary, jd_analysis_json, match_score,
                missing_skills_json, selected_projects_json, selected_skills_json, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                analysis.company,
                analysis.role_title,
                jd_raw,
                analysis.jd_summary,
                analysis.model_dump_json(indent=2),
                match.match_score,
                json.dumps(match.missing_skills),
                json.dumps(match.selected_projects),
                json.dumps(match.selected_keywords),
                status,
            ),
        )
        application_id = int(cur.lastrowid)
        conn.execute(
            """
            INSERT INTO cv_versions (
                job_application_id, version_name, template_name, cv_content_json, latex_path, pdf_path, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                application_id,
                "v1",
                template_name,
                cv_content.model_dump_json(indent=2),
                str(latex_path),
                str(pdf_path) if pdf_path else None,
                str(notes_path),
            ),
        )
        conn.commit()
    return application_id
