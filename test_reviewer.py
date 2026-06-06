"""Offline sanity checks for the pure logic in reviewer.py (no API calls)."""
from reviewer import _extract_json, _normalize, _clamp_score

# 1. JSON wrapped in a markdown fence with prose around it
fenced = 'Here is your review:\n```json\n{"overall_score": 8}\n```\nHope it helps!'
assert _extract_json(fenced) == {"overall_score": 8}

# 2. JSON with leading/trailing prose, no fence
loose = 'Sure!\n{"overall_score": 5, "x": 1}\nDone.'
assert _extract_json(loose) == {"overall_score": 5, "x": 1}

# 3. Score clamping / coercion
assert _clamp_score(15) == 10.0
assert _clamp_score(-3) == 0.0
assert _clamp_score("7.5") == 7.5
assert _clamp_score(None) == 0.0
assert _clamp_score("garbage") == 0.0

# 4. Normalize fills missing fields and never crashes on junk
out = _normalize({})
assert out["overall_score"] == 0.0
assert set(out["dimensions"]) == {"readability", "structure", "maintainability"}
assert out["language"] == "Unknown"
assert out["issues"] == []

# 5. Unknown severity is bucketed (NOT dropped) and issues are sorted
messy = {
    "issues": [
        {"severity": "info", "description": "weird"},          # -> suggestion
        {"severity": "critical", "description": "bug"},         # stays critical
        {"severity": "warning", "line": "null", "description": "x"},  # line -> None
        "not-a-dict",                                           # skipped
    ]
}
norm = _normalize(messy)
sevs = [i["severity"] for i in norm["issues"]]
assert sevs == ["critical", "warning", "suggestion"], sevs  # sorted + bucketed
assert norm["issues"][1]["line"] is None                    # "null" cleaned
assert len(norm["issues"]) == 3                             # junk dropped, none lost

print("All offline tests passed ✅")
