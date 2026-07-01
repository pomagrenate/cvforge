from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any


DB_PATH = Path("data/cvtool.sqlite")


def connect(db_path: Path = DB_PATH) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(conn: sqlite3.Connection | None = None) -> None:
    own_conn = conn is None
    conn = conn or connect()
    try:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS profile (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                name TEXT,
                email TEXT,
                phone TEXT,
                location TEXT,
                github TEXT,
                linkedin TEXT,
                website TEXT,
                target_title TEXT,
                raw_json TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS skills (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT,
                name TEXT NOT NULL,
                level TEXT,
                evidence TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS experiences (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company TEXT,
                role TEXT,
                start_date TEXT,
                end_date TEXT,
                description TEXT,
                bullets_json TEXT,
                technologies_json TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                short_description TEXT,
                long_description TEXT,
                role TEXT,
                technologies_json TEXT,
                bullets_json TEXT,
                impact_json TEXT,
                links_json TEXT,
                priority INTEGER DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS job_applications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company TEXT,
                role_title TEXT,
                jd_raw TEXT NOT NULL,
                jd_summary TEXT,
                jd_analysis_json TEXT,
                match_score INTEGER,
                missing_skills_json TEXT,
                selected_projects_json TEXT,
                selected_skills_json TEXT,
                status TEXT DEFAULT 'draft',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS cv_versions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_application_id INTEGER NOT NULL REFERENCES job_applications(id) ON DELETE CASCADE,
                version_name TEXT,
                template_name TEXT,
                cv_content_json TEXT,
                latex_path TEXT,
                pdf_path TEXT,
                notes TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE VIRTUAL TABLE IF NOT EXISTS job_search USING fts5(
                company,
                role_title,
                jd_raw,
                jd_summary,
                content='job_applications',
                content_rowid='id'
            );

            CREATE TRIGGER IF NOT EXISTS job_applications_ai AFTER INSERT ON job_applications BEGIN
                INSERT INTO job_search(rowid, company, role_title, jd_raw, jd_summary)
                VALUES (new.id, new.company, new.role_title, new.jd_raw, new.jd_summary);
            END;

            CREATE TRIGGER IF NOT EXISTS job_applications_ad AFTER DELETE ON job_applications BEGIN
                INSERT INTO job_search(job_search, rowid, company, role_title, jd_raw, jd_summary)
                VALUES ('delete', old.id, old.company, old.role_title, old.jd_raw, old.jd_summary);
            END;

            CREATE TRIGGER IF NOT EXISTS job_applications_au AFTER UPDATE ON job_applications BEGIN
                INSERT INTO job_search(job_search, rowid, company, role_title, jd_raw, jd_summary)
                VALUES ('delete', old.id, old.company, old.role_title, old.jd_raw, old.jd_summary);
                INSERT INTO job_search(rowid, company, role_title, jd_raw, jd_summary)
                VALUES (new.id, new.company, new.role_title, new.jd_raw, new.jd_summary);
            END;
            """
        )
        conn.commit()
    finally:
        if own_conn:
            conn.close()


def upsert_profile(profile: dict[str, Any], conn: sqlite3.Connection | None = None) -> None:
    own_conn = conn is None
    conn = conn or connect()
    personal = profile.get("personal", {})
    try:
        conn.execute(
            """
            INSERT INTO profile (
                id, name, email, phone, location, github, linkedin, website, target_title, raw_json
            ) VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                name=excluded.name,
                email=excluded.email,
                phone=excluded.phone,
                location=excluded.location,
                github=excluded.github,
                linkedin=excluded.linkedin,
                website=excluded.website,
                target_title=excluded.target_title,
                raw_json=excluded.raw_json,
                updated_at=CURRENT_TIMESTAMP
            """,
            (
                personal.get("name"),
                personal.get("email"),
                personal.get("phone"),
                personal.get("location"),
                personal.get("github"),
                personal.get("linkedin"),
                personal.get("website"),
                (profile.get("target_roles") or [""])[0],
                json.dumps(profile, indent=2),
            ),
        )
        conn.commit()
    finally:
        if own_conn:
            conn.close()


def rows(query: str, params: tuple[Any, ...] = ()) -> list[sqlite3.Row]:
    with connect() as conn:
        return conn.execute(query, params).fetchall()


def update_application_status(application_id: int, status: str) -> None:
    with connect() as conn:
        conn.execute(
            "UPDATE job_applications SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (status, application_id),
        )
        conn.commit()


def search_jobs(query: str) -> list[sqlite3.Row]:
    if not query.strip():
        return []
    with connect() as conn:
        return conn.execute(
            """
            SELECT ja.id, ja.created_at, ja.company, ja.role_title, ja.jd_summary, ja.match_score, ja.status
            FROM job_search
            JOIN job_applications ja ON ja.id = job_search.rowid
            WHERE job_search MATCH ?
            ORDER BY bm25(job_search)
            LIMIT 50
            """,
            (query,),
        ).fetchall()
