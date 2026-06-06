# 🔍 Smart Code Reviewer

An AI assistant that reviews code for **readability**, **structure**, and **maintainability** — before it reaches a human reviewer.

Paste a snippet or upload a file, and the app returns a structured review: an overall score, three dimension scores, issues ranked by severity (with line references and concrete fixes), and one thing the code does well.

![Python](https://img.shields.io/badge/Python-3.10+-blue) ![Streamlit](https://img.shields.io/badge/Built%20with-Streamlit-FF4B4B) ![Claude](https://img.shields.io/badge/Powered%20by-Claude-D97757)

## Features

- **Three-dimension scoring** — Readability, Structure, Maintainability, each 0–10 with a written rationale
- **Severity-ranked issues** — 🔴 critical / 🟡 warning / 🔵 suggestion, each with a line reference and an actionable fix
- **Positive highlight** — surfaces a strength worth preserving, not just problems
- **Paste or upload** — supports 16 languages, with optional manual language override
- **Exportable** — download the review as a Markdown report or raw JSON
- **Robust by design** — all model output is validated and normalized; the UI never crashes on malformed responses

## Quick start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Add your API key
cp .env.example .env        # then edit .env and paste your Anthropic key

# 3. Run
streamlit run app.py
```

The app opens at `http://localhost:8501`.

## Deploy a public link (Streamlit Community Cloud)

1. Push this repo to GitHub (`.env` is git-ignored, so your key stays private).
2. Go to [share.streamlit.io](https://share.streamlit.io) and connect the repo.
3. In **App settings → Secrets**, add:
   ```toml
   ANTHROPIC_API_KEY = "sk-ant-..."
   ```
4. Deploy — you'll get a public URL to share.

## How it works

```
┌──────────────┐     ┌──────────────────────┐     ┌────────────────────┐
│  app.py      │────▶│  reviewer.py         │────▶│  Claude API        │
│  Streamlit   │     │  prompt + validation │     │  structured review │
│  UI          │◀────│  normalize() output  │◀────│  (JSON)            │
└──────────────┘     └──────────────────────┘     └────────────────────┘
```

- **`reviewer.py`** holds a carefully designed system prompt that enforces a strict JSON schema and a scoring rubric. Every response is parsed defensively (`_extract_json`) and coerced into a guaranteed shape (`_normalize`) — scores are clamped to 0–10, unknown severities are bucketed rather than dropped, and issues are sorted most-severe-first.
- **`app.py`** is a pure presentation layer: it renders scores, issues, and the export controls, and translates any `ReviewError` into a friendly message.
- **`test_reviewer.py`** covers the parsing and normalization logic offline (no API key required): `python test_reviewer.py`.

## Project structure

| File | Purpose |
|------|---------|
| `app.py` | Streamlit UI |
| `reviewer.py` | Claude integration, prompt, response validation |
| `test_reviewer.py` | Offline tests for the parsing/normalization logic |
| `requirements.txt` | Dependencies |
| `.env.example` | Environment template |

## Summary

Smart Code Reviewer is an AI-powered web app built with Python, Streamlit, and the Claude API. It accepts code via paste or file upload and performs a structured review across three quality dimensions: Readability, Structure, and Maintainability. Each dimension receives a 0–10 score backed by a tailored system prompt that enforces consistent, schema-bound output. Issues are ranked by severity with line references and fix suggestions, and a positive highlight preserves what the developer did well. Model output is fully validated and normalized, so the interface stays robust against malformed responses. The tool surfaces actionable feedback before human review, reducing review cycles and improving code quality.
