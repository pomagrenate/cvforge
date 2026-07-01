# CV Forge

CV Forge is a local Streamlit workbench for generating tailored LaTeX CVs from job descriptions.

It stores one personal profile, analyzes pasted JDs with a local `llama.cpp` OpenAI-compatible server, matches the JD against your profile, renders a fixed Jinja2 LaTeX template, compiles it with Tectonic, and tracks applications in SQLite.

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Start a local model server:

```powershell
llama-server -m models/qwen2.5-3b-instruct-q4_k_m.gguf -c 4096 --host 127.0.0.1 --port 8080
```

Run the app:

```powershell
streamlit run app.py
```

## Workflow

1. Edit `data/profile_seed.json` in the Profile tab.
2. Paste a job description in Generate CV.
3. Analyze the JD.
4. Generate a tailored CV.
5. Review the match score, warnings, LaTeX, and PDF.
6. Track application status in Dashboard.
7. Search old jobs through SQLite FTS5 in Search.

## Local Outputs

Each generated CV writes:

```text
exports/YYYY-MM-DD_company_role/
  jd.txt
  jd_analysis.json
  profile_match.json
  cv_content.json
  review.json
  cv.tex
  cv.pdf
  notes.md
```

If `tectonic` is not installed, CV Forge still saves the LaTeX and JSON artifacts, then shows the compilation error in Streamlit.
