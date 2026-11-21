"""Guardrails: bias check, protected-field stripping, audit log, human sign-off gate."""
import re, time, json
import db

BIAS_PATTERNS = {
    "age": r"\b(young|youthful|energetic youngster|recent graduate only|under \d{2}|below \d{2} years|age (limit|between)|digital native)\b",
    "gender": r"\b(male only|female only|males? preferred|females? preferred|he/she must|ladies|gentlemen|manpower|salesman)\b",
    "marital/family": r"\b(unmarried|single only|married|no (kids|children)|family status)\b",
    "religion/caste": r"\b(hindu|muslim|christian|sikh|caste|religion)\b",
    "nationality/origin": r"\b(native speaker|local candidates only|from (a )?good (family|background))\b",
    "disability/appearance": r"\b(physically fit only|good looking|attractive|presentable appearance)\b",
}
PROTECTED_FIELDS = {"name", "gender", "age", "dob", "photo", "marital_status", "religion", "email", "phone"}


def check_text(text: str):
    """Return list of {category, match} flags found in a JD / rubric / reason."""
    flags = []
    for cat, pat in BIAS_PATTERNS.items():
        for m in re.finditer(pat, text or "", re.I):
            flags.append({"category": cat, "match": m.group(0)})
    return flags


def sanitize(profile: dict) -> dict:
    """Blind profile: only job-relevant fields ever reach scoring or the LLM."""
    return {k: v for k, v in profile.items() if k not in PROTECTED_FIELDS}


def audit(actor, action, detail=""):
    with db.conn() as c:
        c.execute("INSERT INTO audit(ts,actor,action,detail) VALUES(?,?,?,?)",
                  (time.time(), actor, action, detail if isinstance(detail, str) else json.dumps(detail)))


HUMAN_ONLY = {"offer", "rejection"}  # agent may only DRAFT these; release needs human approval
