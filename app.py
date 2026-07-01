from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

from src import db, storage
from src.cv_reviewer import review_cv
from src.cv_writer import generate_cv_content
from src.jd_analyzer import analyze_jd
from src.latex_renderer import write_latex
from src.pdf_compiler import PDFCompilationError, compile_pdf
from src.profile_matcher import match_profile
from src.schemas import CVContent, CVReview, JDAnalysis, ProfileMatch


TEMPLATES = {
    "ATS one page": "ats_one_page.tex.j2",
    "ATS two page": "ats_two_page.tex.j2",
    "AI engineer": "ai_engineer.tex.j2",
}
STATUSES = ["draft", "applied", "rejected", "interview", "offer", "archived"]


def main() -> None:
    st.set_page_config(page_title="CV Forge", layout="wide")
    db.init_db()
    st.title("CV Forge")
    st.caption("Local JD-to-LaTeX CV workbench")

    profile_tab, generate_tab, dashboard_tab, search_tab = st.tabs(
        ["Profile", "Generate CV", "Dashboard", "Search"]
    )
    with profile_tab:
        profile_view()
    with generate_tab:
        generate_view()
    with dashboard_tab:
        dashboard_view()
    with search_tab:
        search_view()


def profile_view() -> None:
    st.subheader("Profile JSON")
    profile = storage.load_profile()
    uploaded = st.file_uploader("Import profile JSON", type=["json"])
    if uploaded:
        try:
            profile = json.loads(uploaded.read().decode("utf-8"))
            storage.save_profile(profile)
            st.success("Imported profile JSON.")
        except json.JSONDecodeError as exc:
            st.error(f"Invalid JSON: {exc}")

    profile_text = st.text_area("Edit profile", json.dumps(profile, indent=2), height=520)
    col_a, col_b = st.columns([1, 1])
    with col_a:
        if st.button("Save profile", type="primary"):
            try:
                storage.save_profile(json.loads(profile_text))
                st.success("Profile saved to data/profile_seed.json and SQLite.")
            except json.JSONDecodeError as exc:
                st.error(f"Invalid JSON: {exc}")
    with col_b:
        st.download_button(
            "Export profile JSON",
            data=profile_text,
            file_name="profile_seed.json",
            mime="application/json",
        )


def generate_view() -> None:
    st.subheader("Generate Tailored CV")
    company_hint = st.text_input("Company name", placeholder="Optional")
    role_hint = st.text_input("Role title", placeholder="Optional")
    template_label = st.selectbox("Template", list(TEMPLATES), index=0)
    jd_text = st.text_area("Job description", height=300)

    col_a, col_b = st.columns([1, 1])
    with col_a:
        analyze_clicked = st.button("Analyze JD")
    with col_b:
        generate_clicked = st.button("Generate CV", type="primary")

    if analyze_clicked and jd_text.strip():
        analysis = analyze_jd(jd_text)
        analysis = apply_hints(analysis, company_hint, role_hint)
        st.session_state["analysis"] = analysis

    analysis = st.session_state.get("analysis")
    if analysis:
        show_analysis(analysis)

    if generate_clicked:
        if not jd_text.strip():
            st.error("Paste a job description first.")
            return
        profile = storage.load_profile()
        analysis = apply_hints(analyze_jd(jd_text), company_hint, role_hint)
        match = match_profile(profile, analysis)
        cv_content = generate_cv_content(profile, analysis, match)
        review = review_cv(profile, analysis, cv_content)
        if review.recommendation == "revise":
            cv_content.warnings.append("Reviewer requested revision; one-pass automatic rewrite is not enabled yet.")

        result = save_generation(
            jd_text=jd_text,
            profile=profile,
            analysis=analysis,
            match=match,
            cv_content=cv_content,
            review=review,
            template_name=TEMPLATES[template_label],
        )
        st.session_state["last_result"] = result
        st.success(f"Generated application #{result['application_id']}.")

    result = st.session_state.get("last_result")
    if result:
        show_generation_result(result)


def apply_hints(analysis: JDAnalysis, company: str, role: str) -> JDAnalysis:
    if company.strip():
        analysis.company = company.strip()
    if role.strip():
        analysis.role_title = role.strip()
    return analysis


def show_analysis(analysis: JDAnalysis) -> None:
    st.markdown("#### JD Analysis")
    col_a, col_b, col_c = st.columns(3)
    col_a.metric("Company", analysis.company or "Unknown")
    col_b.metric("Role", analysis.role_title)
    col_c.metric("Seniority", analysis.seniority or "Unclear")
    st.write(analysis.jd_summary)
    st.write("Must-have skills:", ", ".join(analysis.must_have_skills) or "None extracted")
    st.write("Nice-to-have skills:", ", ".join(analysis.nice_to_have_skills) or "None extracted")
    with st.expander("Responsibilities"):
        st.write(analysis.responsibilities)
    with st.expander("ATS keywords"):
        st.write(analysis.keywords_for_ats)


def save_generation(
    jd_text: str,
    profile: dict,
    analysis: JDAnalysis,
    match: ProfileMatch,
    cv_content: CVContent,
    review: CVReview,
    template_name: str,
) -> dict:
    out_dir = storage.export_dir(analysis.company, analysis.role_title)
    latex_path = out_dir / "cv.tex"
    pdf_path = None
    notes_path = out_dir / "notes.md"

    (out_dir / "jd.txt").write_text(jd_text, encoding="utf-8")
    storage.write_json(out_dir / "jd_analysis.json", analysis)
    storage.write_json(out_dir / "profile_match.json", match)
    storage.write_json(out_dir / "cv_content.json", cv_content)
    storage.write_json(out_dir / "review.json", review)
    storage.write_notes(notes_path, analysis, match, "draft", datetime.now())
    write_latex(profile, cv_content, latex_path, template_name)

    compile_error = None
    try:
        pdf_path = compile_pdf(latex_path)
    except PDFCompilationError as exc:
        compile_error = str(exc)

    application_id = storage.persist_generation(
        jd_raw=jd_text,
        analysis=analysis,
        match=match,
        cv_content=cv_content,
        review=review,
        template_name=template_name,
        latex_path=latex_path,
        pdf_path=pdf_path,
        notes_path=notes_path,
    )
    return {
        "application_id": application_id,
        "analysis": analysis,
        "match": match,
        "cv_content": cv_content,
        "review": review,
        "latex_path": latex_path,
        "pdf_path": pdf_path,
        "notes_path": notes_path,
        "compile_error": compile_error,
    }


def show_generation_result(result: dict) -> None:
    match: ProfileMatch = result["match"]
    cv_content: CVContent = result["cv_content"]
    review: CVReview = result["review"]
    st.markdown("#### Result")
    col_a, col_b = st.columns(2)
    col_a.metric("Match score", match.match_score)
    col_b.metric("Review score", review.final_quality_score)
    st.write("Strong matches:", ", ".join(match.strong_matches) or "None")
    st.write("Partial matches:", ", ".join(match.partial_matches) or "None")
    st.write("Missing skills:", ", ".join(match.missing_skills) or "None")
    st.write("Selected projects:", ", ".join(match.selected_projects) or "None")
    if cv_content.warnings:
        st.warning("\n".join(cv_content.warnings))
    if review.hallucination_risks:
        st.error("Hallucination risks: " + ", ".join(review.hallucination_risks))
    if result["compile_error"]:
        st.error(result["compile_error"])
    if result["pdf_path"] and Path(result["pdf_path"]).exists():
        st.download_button(
            "Download PDF",
            data=Path(result["pdf_path"]).read_bytes(),
            file_name=Path(result["pdf_path"]).name,
            mime="application/pdf",
        )
    with st.expander("View LaTeX source"):
        st.code(Path(result["latex_path"]).read_text(encoding="utf-8"), language="latex")


def dashboard_view() -> None:
    st.subheader("Applications")
    records = db.rows(
        """
        SELECT
            ja.id,
            ja.created_at,
            ja.company,
            ja.role_title,
            ja.match_score,
            ja.status,
            cv.template_name,
            cv.pdf_path,
            cv.latex_path,
            cv.notes
        FROM job_applications ja
        LEFT JOIN cv_versions cv ON cv.job_application_id = ja.id
        ORDER BY ja.created_at DESC
        """
    )
    if not records:
        st.info("No applications yet.")
        return
    frame = pd.DataFrame([dict(row) for row in records])
    st.dataframe(frame, use_container_width=True, hide_index=True)
    selected_id = st.number_input("Application ID", min_value=1, step=1)
    new_status = st.selectbox("Status", STATUSES)
    if st.button("Update status"):
        db.update_application_status(int(selected_id), new_status)
        st.success("Status updated.")
        st.rerun()


def search_view() -> None:
    st.subheader("Search Old JDs")
    query = st.text_input("Search by skill, company, role, or JD keyword")
    if query:
        results = db.search_jobs(query)
        if results:
            st.dataframe(pd.DataFrame([dict(row) for row in results]), use_container_width=True, hide_index=True)
        else:
            st.info("No matches.")


if __name__ == "__main__":
    main()
