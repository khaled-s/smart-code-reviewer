"""Claude-powered code review engine.

Exposes a single public function, ``review_code``, which sends source code to
Claude and returns a normalized, UI-ready dictionary. All model output is
validated and coerced so the UI never has to defend against malformed data.
"""

import os
import re
import json

import anthropic
from dotenv import load_dotenv

load_dotenv()

# Model is overridable via env so the app keeps working if the ID changes,
# without touching code.
MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")

# Guard against oversized input (cost, latency, and truncated responses).
MAX_CODE_CHARS = 60_000

VALID_SEVERITIES = ("critical", "warning", "suggestion")
VALID_CATEGORIES = ("readability", "structure", "maintainability")

SYSTEM_PROMPT = """You are an expert code reviewer specializing in readability, structure, and maintainability.

Analyze the provided code and return ONLY a JSON object with this exact structure — no markdown, no prose outside the JSON:

{
  "language": "detected language name",
  "overall_score": <number 0.0-10.0>,
  "summary": "2-3 sentence overview of overall code quality",
  "dimensions": {
    "readability": {
      "score": <number 0.0-10.0>,
      "summary": "assessment of naming conventions, comments, and code clarity"
    },
    "structure": {
      "score": <number 0.0-10.0>,
      "summary": "assessment of modularity, function design, and organization"
    },
    "maintainability": {
      "score": <number 0.0-10.0>,
      "summary": "assessment of DRY principles, error handling, and complexity"
    }
  },
  "issues": [
    {
      "severity": "critical|warning|suggestion",
      "line": "line number, range like 12-15, or null if file-wide",
      "category": "readability|structure|maintainability",
      "description": "concise description of the issue",
      "suggestion": "specific, actionable fix"
    }
  ],
  "positive": "one concrete strength — something done well that reviewers should preserve"
}

Severity definitions:
- critical: bugs, security flaws, or patterns that will cause failures in production
- warning: quality issues that should be addressed before the code is merged
- suggestion: improvements that would enhance long-term quality but are not blocking

Scoring rubric per dimension:
- 9-10: Excellent, nearly production-ready
- 7-8: Good, only minor issues
- 5-6: Adequate, several issues to address
- 3-4: Poor, significant rework needed
- 0-2: Critical issues, fundamental problems

The overall_score should weight the weakest dimension more heavily.

Return ONLY valid JSON. No markdown fences, no explanatory text outside the JSON object."""


class ReviewError(Exception):
    """A user-facing error with a message safe to show directly in the UI."""


def _clamp_score(value) -> float:
    """Coerce any model-supplied score into a float in [0.0, 10.0]."""
    try:
        return max(0.0, min(10.0, round(float(value), 1)))
    except (TypeError, ValueError):
        return 0.0


def _extract_json(text: str) -> dict:
    """Pull a JSON object out of the model response, tolerating stray prose
    or markdown fences. Raises json.JSONDecodeError if nothing parses."""
    text = (text or "").strip()

    # Prefer an explicit ```json ... ``` block if the model added one.
    fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.DOTALL)
    if fenced:
        return json.loads(fenced.group(1))

    # Otherwise take everything between the first '{' and the last '}'.
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return json.loads(text[start:end + 1])

    # Last resort: let json.loads raise a clean JSONDecodeError.
    return json.loads(text)


def _normalize(raw: dict) -> dict:
    """Coerce raw model output into a guaranteed, fully-populated shape so the
    UI can render it without defensive checks."""
    if not isinstance(raw, dict):
        raw = {}

    dims_in = raw.get("dimensions") or {}
    dimensions = {}
    for key in VALID_CATEGORIES:
        d = dims_in.get(key) or {}
        dimensions[key] = {
            "score": _clamp_score(d.get("score")),
            "summary": str(d.get("summary", "")).strip(),
        }

    issues = []
    for item in raw.get("issues") or []:
        if not isinstance(item, dict):
            continue

        severity = str(item.get("severity", "")).lower().strip()
        if severity not in VALID_SEVERITIES:
            severity = "suggestion"

        category = str(item.get("category", "")).lower().strip()
        if category not in VALID_CATEGORIES:
            category = "maintainability"

        line = item.get("line")
        if line in (None, "", "null", "N/A", "n/a"):
            line = None
        else:
            line = str(line).strip()

        issues.append({
            "severity": severity,
            "line": line,
            "category": category,
            "description": str(item.get("description", "")).strip(),
            "suggestion": str(item.get("suggestion", "")).strip(),
        })

    # Surface the most severe issues first.
    order = {"critical": 0, "warning": 1, "suggestion": 2}
    issues.sort(key=lambda i: order[i["severity"]])

    return {
        "language": str(raw.get("language", "") or "Unknown").strip() or "Unknown",
        "overall_score": _clamp_score(raw.get("overall_score")),
        "summary": str(raw.get("summary", "")).strip(),
        "dimensions": dimensions,
        "issues": issues,
        "positive": str(raw.get("positive", "")).strip(),
    }


def review_code(code: str, language: str = "auto") -> dict:
    """Review ``code`` with Claude and return a normalized result dict.

    Raises ReviewError with a user-friendly message on any expected failure
    (missing key, oversized input, API error, unparseable response).
    """
    if not code or not code.strip():
        raise ReviewError("Please provide some code to review.")

    if len(code) > MAX_CODE_CHARS:
        raise ReviewError(
            f"Code is too large ({len(code):,} characters). "
            f"Please limit input to {MAX_CODE_CHARS:,} characters."
        )

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key or api_key == "your_api_key_here":
        raise ReviewError(
            "ANTHROPIC_API_KEY is not configured. Add your key to the .env file "
            "(or Streamlit secrets) and restart the app."
        )

    client = anthropic.Anthropic(api_key=api_key)
    lang_hint = f"\nLanguage: {language}" if language and language != "auto" else ""

    try:
        message = client.messages.create(
            model=MODEL,
            max_tokens=4096,
            temperature=0.2,  # low temperature → consistent, repeatable reviews
            system=SYSTEM_PROMPT,
            messages=[{
                "role": "user",
                "content": f"Review this code:{lang_hint}\n\n```\n{code}\n```",
            }],
        )
    except anthropic.AuthenticationError:
        raise ReviewError("Invalid API key. Check ANTHROPIC_API_KEY in your .env file.")
    except anthropic.RateLimitError:
        raise ReviewError("Rate limit reached. Wait a moment and try again.")
    except anthropic.APIConnectionError:
        raise ReviewError("Could not reach the Anthropic API. Check your connection.")
    except anthropic.APIError as e:
        raise ReviewError(f"Anthropic API error: {e}")

    if not message.content:
        raise ReviewError("The model returned an empty response. Please try again.")

    raw_text = message.content[0].text

    try:
        parsed = _extract_json(raw_text)
    except json.JSONDecodeError:
        raise ReviewError(
            "Could not parse the review — the model did not return valid JSON. "
            "Please try again."
        )

    return _normalize(parsed)
