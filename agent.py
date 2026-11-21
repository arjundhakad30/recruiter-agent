"""Recruiter Agent core: tools, deterministic pipeline, Claude tool-use loop, human-approval gate."""
import json, os, time, hashlib, urllib.request
import db, guardrails as g

POOL = {c["id"]: c for c in json.load(open(os.path.join(os.path.dirname(__file__), "data", "candidates.json")))}
STAGES = ["Sourced", "Shortlisted", "Screened", "Tech", "HR", "Offer Pending", "Offered", "Accepted", "Declined", "Rejected"]
MODEL = os.environ.get("CLAUDE_MODEL", "claude-sonnet-5-5")
SYSTEM = ("You are a Recruiter Agent. Use tools to run the hiring cycle. Judge candidates only on job-relevant "
          "evidence; never use or infer age, gender, religion, marital status, ethnicity or nationality. "
          "You can only DRAFT offers and rejections; a human approves them.")

# ---------- LLM helper (optional) ----------
def _client():
    if not os.environ.get("ANTHROPIC_API_KEY"): return None
    try:
        import anthropic; return anthropic.Anthropic()
    except Exception: return None

def provider():
    """anthropic (paid key) | oai (any OpenAI-compatible endpoint: Ollama, Groq free, Gemini free) | None (demo)."""
    if _client(): return "anthropic"
    if os.environ.get("LLM_BASE_URL"): return "oai"
    return None

def llm_on(): return provider() is not None

def _oai(messages, tools=None, max_tokens=800):
    body = {"model": os.environ.get("LLM_MODEL", "llama3.1"), "messages": messages, "max_tokens": max_tokens}
    if tools:
        body["tools"] = [{"type": "function", "function": {"name": t["name"], "description": t["description"],
                          "parameters": t["input_schema"]}} for t in tools]
    req = urllib.request.Request(os.environ["LLM_BASE_URL"].rstrip("/") + "/chat/completions", json.dumps(body).encode(),
                                 {"Content-Type": "application/json", "Authorization": "Bearer " + os.environ.get("LLM_API_KEY", "ollama")})
    return json.load(urllib.request.urlopen(req, timeout=180))["choices"][0]["message"]

def llm(prompt, max_tokens=800):
    if provider() == "oai":
        try: return _oai([{"role": "system", "content": SYSTEM}, {"role": "user", "content": prompt}], max_tokens=max_tokens).get("content")
        except Exception as e: g.audit("system", "llm_error", str(e)); return None
    c = _client()
    if not c: return None
    try:
        r = c.messages.create(model=MODEL, max_tokens=max_tokens, system=SYSTEM,
                              messages=[{"role": "user", "content": prompt}])
        return "".join(b.text for b in r.content if b.type == "text")
    except Exception as e:
        g.audit("system", "llm_error", str(e)); return None

# ---------- helpers ----------
def _now(): return time.time()
def _j(x): return json.dumps(x)
def job(job_id):
    with db.conn() as c: return dict(c.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone())
def _pipe(pid):
    with db.conn() as c: return dict(c.execute("SELECT * FROM pipeline WHERE id=?", (pid,)).fetchone())
def set_stage(pid, stage, actor="agent"):
    with db.conn() as c: c.execute("UPDATE pipeline SET stage=?, updated=? WHERE id=?", (stage, _now(), pid))
    g.audit(actor, "stage_change", f"pipe={pid} -> {stage}")
def send_email(pid, subject, body):
    p = _pipe(pid)
    with db.conn() as c:
        c.execute("INSERT INTO outbox(pipe_id,to_addr,subject,body,status,ts) VALUES(?,?,?,?,?,?)",
                  (pid, POOL[p["cand_id"]]["email"], subject, body, "sent (simulated)", _now()))
    g.audit("agent", "email_sent", f"pipe={pid} subject={subject}")

# ---------- 1. BRIEF: JD + rubric ----------
def draft_jd(title, must, nice, min_exp, location):
    out = llm(f"Write a concise, inclusive job description for '{title}' in {location}. Must-have: {', '.join(must)}. "
              f"Nice-to-have: {', '.join(nice)}. Min experience {min_exp} years. Sections: About, Responsibilities, "
              f"Requirements, Nice to have. No age, gender or other protected-attribute language.")
    if out: return out
    return (f"# {title}\n\n**Location:** {location}\n\n## About the role\nJoin our team as {title} and build reliable products.\n\n"
            f"## Requirements\n- {min_exp}+ years of relevant experience\n" + "\n".join(f"- {m}" for m in must) +
            "\n\n## Nice to have\n" + "\n".join(f"- {n}" for n in nice) +
            "\n\nWe welcome applicants of all backgrounds.")

def create_job(title, jd, must, nice, min_exp, budget_lpa, max_notice, location, meta=None, audit=True):
    flags = g.check_text(jd + " " + " ".join(must + nice) + " " + json.dumps(meta or {}))
    if flags:
        g.audit("agent", "bias_block", _j(flags))
        raise ValueError("Biased criteria found: " + ", ".join(f"{f['match']} ({f['category']})" for f in flags))
    with db.conn() as c:
        cur = c.execute("INSERT INTO jobs(title,jd,must,nice,min_exp,budget_lpa,max_notice,location,created,meta) VALUES(?,?,?,?,?,?,?,?,?,?)",
                        (title, jd, _j(must), _j(nice), min_exp, budget_lpa, max_notice, location, _now(), _j(meta or {})))
    if audit: g.audit("human", "job_created", title)
    return cur.lastrowid

def update_job_terms(job_id, location, package):
    """Apply the location and package chosen on the notice page."""
    jb = job(job_id); m = json.loads(jb["meta"] or "{}")
    m.update(location=location, salary_lpa=package, stipend_lpa=round(package * 0.55, 1))
    with db.conn() as c: c.execute("UPDATE jobs SET location=?, budget_lpa=?, meta=? WHERE id=?", (location, package, _j(m), job_id))

def search_string(jb):
    must = " AND ".join(f'"{m}"' for m in json.loads(jb["must"]))
    nice = " OR ".join(f'"{n}"' for n in json.loads(jb["nice"]))
    return f'({must})' + (f' AND ({nice})' if nice else '') + f' AND "{jb["location"]}"'

# ---------- 2. SOURCE + scan against JD ----------
def score_profile(profile, jb):
    p = g.sanitize(profile)
    sk = {s.lower() for s in p["skills"]}  # evidence = listed skills only, exact match
    must, nice = json.loads(jb["must"]), json.loads(jb["nice"])
    mh = [m for m in must if m.lower() in sk]; nh = [n for n in nice if n.lower() in sk]
    a = 60 * len(mh) / max(len(must), 1)
    b = 15 * len(nh) / max(len(nice), 1) if nice else 15
    c = 25 * min(p["years"] / jb["min_exp"], 1) if jb["min_exp"] else 25
    why = f"Must-have {len(mh)}/{len(must)} (missing: {', '.join(set(must)-set(mh)) or 'none'}); nice-to-have {len(nh)}/{len(nice)}; {p['years']}y vs {jb['min_exp']}y required."
    return round(a + b + c, 1), {"must": round(a, 1), "nice": round(b, 1), "experience": round(c, 1)}, why

def source_and_score(job_id):
    jb = job(job_id); n = 0
    for cid, prof in POOL.items():
        s, br, why = score_profile(prof, jb)
        if s < 50: continue  # not relevant enough to enter the pipeline
        with db.conn() as c:
            cur = c.execute("INSERT OR IGNORE INTO pipeline(job_id,cand_id,stage,score,breakdown,rationale,created,updated) VALUES(?,?,?,?,?,?,?,?)",
                            (job_id, cid, "Sourced", s, _j(br), why, _now(), _now()))
            n += cur.rowcount
    g.audit("agent", "sourced", f"job={job_id} new={n} string={search_string(jb)}"); return {"sourced": n}

# ---------- 3. SHORTLIST + screening ----------
def shortlist(job_id, top_n=5, min_score=60):
    with db.conn() as c:
        rows = c.execute("SELECT * FROM pipeline WHERE job_id=? AND stage='Sourced' ORDER BY score DESC", (job_id,)).fetchall()
    sl = 0
    for r in rows:
        if sl < top_n and r["score"] >= min_score:
            set_stage(r["id"], "Shortlisted"); sl += 1
        elif r["score"] < min_score:
            draft_rejection(r["id"], "Profile does not match the role's must-have skills and experience closely enough.")
        # qualified but beyond top_n stay in Sourced as a waitlist (never auto-rejected)
    return {"shortlisted": sl}

def run_screening(job_id):
    jb = job(job_id); res = {"passed": 0, "flagged": 0}
    with db.conn() as c:
        rows = c.execute("SELECT * FROM pipeline WHERE job_id=? AND stage='Shortlisted'", (job_id,)).fetchall()
    for r in rows:
        p = POOL[r["cand_id"]]
        checks = {"notice_period": p["notice_days"] <= jb["max_notice"],
                  "expectation_within_band": p["expected_lpa"] <= jb["budget_lpa"] * 1.15,
                  "location_fit": jb["location"].lower() == "remote" or p.get("relocate", True) or p["location"].lower() == jb["location"].lower()}
        answers = {"notice_days": p["notice_days"], "expected_lpa": p["expected_lpa"], "location": p["location"]}
        ok = all(checks.values())
        with db.conn() as c:
            c.execute("UPDATE pipeline SET screening=? WHERE id=?", (_j({"answers": answers, "checks": checks, "pass": ok}), r["id"]))
        if ok: set_stage(r["id"], "Screened"); res["passed"] += 1
        else:
            label = {"notice_period": "notice period", "expectation_within_band": "salary expectation", "location_fit": "location"}
            fails = ", ".join(label[k] for k, v in checks.items() if not v)
            draft_rejection(r["id"], f"On the screening call we could not align on {fails}."); res["flagged"] += 1
    return res

# ---------- 4. INTERVIEWS ----------
def schedule_interview(pid, kind):
    with db.conn() as c:
        s = c.execute("SELECT * FROM slots WHERE kind=? AND booked_by IS NULL ORDER BY start LIMIT 1", (kind,)).fetchone()
        if not s: return {"error": "no free slot"}
        c.execute("UPDATE slots SET booked_by=? WHERE id=?", (pid, s["id"]))
        c.execute("INSERT INTO interviews(pipe_id,kind,start) VALUES(?,?,?)", (pid, kind, s["start"]))
    set_stage(pid, "Tech" if kind == "tech" else "HR")
    send_email(pid, f"Interview invitation: {kind.upper()} round",
               f"Hello,\n\nYour {kind.upper()} round is scheduled for {s['start']} with {s['interviewer']}.\n\nRegards,\nRecruiting Team")
    return {"scheduled": s["start"]}

def schedule_all_screened(job_id):
    with db.conn() as c:
        ids = [r["id"] for r in c.execute("SELECT id FROM pipeline WHERE job_id=? AND stage='Screened'", (job_id,))]
    return [schedule_interview(i, "tech") for i in ids]

def record_result(pid, kind, passed, note=""):
    with db.conn() as c:
        c.execute("UPDATE interviews SET result=?, note=? WHERE pipe_id=? AND kind=?", ("pass" if passed else "fail", note, pid, kind))
    g.audit("panel", "interview_result", f"pipe={pid} {kind} {'pass' if passed else 'fail'}")
    if not passed: return draft_rejection(pid, note or f"We are not progressing after the {kind.upper()} round.")
    return schedule_interview(pid, "hr") if kind == "tech" else draft_offer(pid)

# ---------- 5. OFFER / REJECTION: draft only, human releases ----------
def _pending(pid, kind):
    with db.conn() as c:
        return c.execute("SELECT id FROM approvals WHERE pipe_id=? AND kind=? AND status='pending'", (pid, kind)).fetchone()

def draft_rejection(pid, reason):
    flags = g.check_text(reason)
    if flags: reason = "Not selected based on role requirements."
    if _pending(pid, "rejection"): return {"approval": "already pending"}
    p = _pipe(pid); jb = job(p["job_id"]); co = json.loads(jb["meta"] or "{}").get("company", "our company")
    body = (f"Dear {POOL[p['cand_id']]['name']},\n\nThank you for your time and your interest in the {jb['title']} position at {co}. "
            f"After careful review, we will not be moving forward with your application. {reason}\n\n"
            f"We will keep your profile for future roles.\n\nRegards,\nRecruiting Team")
    with db.conn() as c:
        cur = c.execute("INSERT INTO approvals(pipe_id,kind,draft,terms,status,created) VALUES(?,?,?,?,?,?)",
                        (pid, "rejection", body, _j({"reason": reason}), "pending", _now()))
    g.audit("agent", "rejection_drafted", f"pipe={pid} (awaiting human sign-off)"); return {"approval_id": cur.lastrowid, "status": "pending human sign-off"}

def draft_offer(pid, ask_lpa=None):
    p = _pipe(pid); jb = job(p["job_id"]); cand = POOL[p["cand_id"]]
    ask = ask_lpa or cand["expected_lpa"]; ceiling = round(jb["budget_lpa"] * 1.05, 1)
    ctc = min(ask, ceiling)
    note = "Matches the ask." if ctc == ask else f"Ask {ask} LPA exceeds ceiling; countered at {ctc} LPA."
    terms = {"ctc_lpa": ctc, "joining_days": cand["notice_days"], "negotiation_note": note}
    with db.conn() as c:
        c.execute("UPDATE approvals SET status='superseded' WHERE pipe_id=? AND kind='offer' AND status='pending'", (pid,))
        body = (f"Dear {cand['name']},\n\nWe are pleased to offer you the position of {jb['title']} at {json.loads(jb['meta'] or '{}').get('company', 'our company')} ({jb['location']}).\n"
                f"Annual CTC: INR {ctc} LPA\nExpected joining: within {cand['notice_days']} days\n\nPlease reply to accept.\n\nRegards,\nRecruiting Team")
        cur = c.execute("INSERT INTO approvals(pipe_id,kind,draft,terms,status,created) VALUES(?,?,?,?,?,?)",
                        (pid, "offer", body, _j(terms), "pending", _now()))
    set_stage(pid, "Offer Pending"); g.audit("agent", "offer_drafted", f"pipe={pid} terms={terms} (awaiting human sign-off)")
    return {"approval_id": cur.lastrowid, "terms": terms, "status": "pending human sign-off"}

def decide(approval_id, approve, reviewer, note="", ctc_lpa=None):
    """Human checkpoint: the ONLY path that releases an offer or sends a rejection."""
    with db.conn() as c: a = dict(c.execute("SELECT * FROM approvals WHERE id=?", (approval_id,)).fetchone())
    if a["status"] != "pending" or not reviewer.strip(): return {"error": "needs pending item and named reviewer"}
    pid, terms = a["pipe_id"], json.loads(a["terms"]); draft = a["draft"]
    if a["kind"] == "offer" and approve and ctc_lpa and ctc_lpa != terms["ctc_lpa"]:
        draft = draft.replace(f"INR {terms['ctc_lpa']} LPA", f"INR {ctc_lpa} LPA"); terms["ctc_lpa"] = ctc_lpa
    with db.conn() as c:
        c.execute("UPDATE approvals SET status=?, decided=?, reviewer=?, note=?, draft=?, terms=? WHERE id=?",
                  ("approved" if approve else "declined", _now(), reviewer, note, draft, _j(terms), approval_id))
    g.audit("human:" + reviewer, f"{a['kind']}_{'approved' if approve else 'declined'}", f"approval={approval_id} {note}")
    if approve:
        send_email(pid, "Offer letter" if a["kind"] == "offer" else "Update on your application", draft)
        set_stage(pid, "Offered" if a["kind"] == "offer" else "Rejected", actor="human:" + reviewer)
    elif a["kind"] == "offer": set_stage(pid, "HR", actor="human:" + reviewer)
    return {"ok": True}

def candidate_response(pid, accepted):
    set_stage(pid, "Accepted" if accepted else "Declined", actor="candidate")

# ---------- Interview rounds (panel outcomes decided by score + round performance, varies by candidate) ----------
def _panel_pass(pid, kind):
    p = _pipe(pid); h = int(hashlib.md5(f"{p['cand_id']}{p['job_id']}{kind}".encode()).hexdigest(), 16) % 100
    return p["score"] * 0.6 + h * 0.4 >= (62 if kind == "tech" else 55)

NOTES = {"tech": ("Cleared the technical round.", "Our technical panel felt the depth required for this role was not yet shown."),
         "hr": ("Cleared the HR round.", "After the HR round, we found another candidate closer to the role expectations.")}

def run_interviews(job_id):
    res = {"tech_pass": 0, "tech_fail": 0, "hr_pass": 0, "hr_fail": 0}
    with db.conn() as c: ids = [r["id"] for r in c.execute("SELECT id FROM pipeline WHERE job_id=? AND stage='Tech'", (job_id,))]
    for pid in ids:
        ok = _panel_pass(pid, "tech"); record_result(pid, "tech", ok, NOTES["tech"][0 if ok else 1]); res["tech_pass" if ok else "tech_fail"] += 1
        if ok and _pipe(pid)["stage"] == "HR":
            ok2 = _panel_pass(pid, "hr"); record_result(pid, "hr", ok2, NOTES["hr"][0 if ok2 else 1]); res["hr_pass" if ok2 else "hr_fail"] += 1
    return res

# ---------- KPIs ----------
def kpis(job_id):
    with db.conn() as c:
        rows = [dict(r) for r in c.execute("SELECT * FROM pipeline WHERE job_id=?", (job_id,))]
        interviewed = {r["pipe_id"] for r in c.execute("SELECT pipe_id FROM interviews")}
    ids = {r["id"] for r in rows}
    shortlisted = [r for r in rows if r["stage"] != "Sourced" and r["stage"] != "Rejected" or r["id"] in interviewed]
    sl = len([r for r in rows if r["screening"] or r["stage"] not in ("Sourced", "Rejected")])
    offered = [r for r in rows if r["stage"] in ("Offered", "Accepted", "Declined")]
    acc = [r for r in rows if r["stage"] == "Accepted"]
    tth = sum(r["updated"] - r["created"] for r in acc) / len(acc) if acc else None
    return {"Candidates sourced": len(rows),
            "Shortlist-to-interview": f"{len(ids & interviewed)}/{sl}" if sl else "n/a",
            "Time to hire (avg)": f"{tth/60:.1f} min (demo clock)" if tth is not None else "n/a",
            "Offer acceptance": f"{len(acc)}/{len(offered)}" if offered else "n/a"}

# ---------- Claude tool-use loop (offer/rejection RELEASE is not a tool) ----------
TOOLS = [
    {"name": "source_and_score", "description": "Search candidate pool and score every profile against the JD.", "input_schema": {"type": "object", "properties": {}}},
    {"name": "shortlist", "description": "Shortlist top candidates; the rest get rejection DRAFTS pending human sign-off.", "input_schema": {"type": "object", "properties": {"top_n": {"type": "integer"}, "min_score": {"type": "number"}}}},
    {"name": "run_screening", "description": "Run first-round screening checks (notice, expectation, location) on shortlisted candidates.", "input_schema": {"type": "object", "properties": {}}},
    {"name": "schedule_screened", "description": "Book Tech interviews for all screened candidates using the interview calendar.", "input_schema": {"type": "object", "properties": {}}},
    {"name": "run_interviews", "description": "Run Tech and HR interview rounds for scheduled candidates; passed candidates get offer drafts, others get rejection drafts (human approves both).", "input_schema": {"type": "object", "properties": {}}},
    {"name": "draft_offer", "description": "Draft or renegotiate an offer (human must approve). Optional candidate ask in LPA.", "input_schema": {"type": "object", "properties": {"pipe_id": {"type": "integer"}, "ask_lpa": {"type": "number"}}, "required": ["pipe_id"]}},
    {"name": "pipeline_status", "description": "Return current pipeline: id, blind candidate id, stage, score.", "input_schema": {"type": "object", "properties": {}}},
]

def pipeline_status(job_id):
    with db.conn() as c:
        return [{"pipe_id": r["id"], "cand": r["cand_id"], "stage": r["stage"], "score": r["score"]} for r in c.execute("SELECT * FROM pipeline WHERE job_id=? ORDER BY score DESC", (job_id,))]

def _impl(job_id):
    return {"source_and_score": lambda i: source_and_score(job_id), "shortlist": lambda i: shortlist(job_id, i.get("top_n", 5), i.get("min_score", 60)),
            "run_screening": lambda i: run_screening(job_id), "schedule_screened": lambda i: schedule_all_screened(job_id),
            "run_interviews": lambda i: run_interviews(job_id), "draft_offer": lambda i: draft_offer(i["pipe_id"], i.get("ask_lpa")), "pipeline_status": lambda i: pipeline_status(job_id)}

def _run_agent_oai(job_id, instruction):
    impl = _impl(job_id); jb = job(job_id)
    msgs = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": f"Job: {jb['title']}\nJD:\n{jb['jd']}\n\nTask: {instruction}"}]
    for _ in range(10):
        m = _oai(msgs, TOOLS, 1500); msgs.append(m)
        calls = m.get("tool_calls")
        if not calls: return m.get("content") or ""
        for tc in calls:
            name = tc["function"]["name"]; a = tc["function"].get("arguments") or "{}"
            args = json.loads(a) if isinstance(a, str) else a
            g.audit("agent", "tool_call", f"{name} {json.dumps(args)}")
            try: out = impl[name](args)
            except Exception as e: out = {"error": str(e)}
            msgs.append({"role": "tool", "tool_call_id": tc.get("id", name), "content": json.dumps(out)})
    return "Stopped after max steps."

DEFAULT_INSTRUCTION = ("Run the full hiring cycle: source and score candidates, shortlist, run screening, schedule Tech interviews, then run the interviews. "
                       "Offers and rejections stay as drafts for human approval.")

def cycle_summary(job_id):
    with db.conn() as c:
        rows = [dict(r) for r in c.execute("SELECT * FROM pipeline WHERE job_id=?", (job_id,))]
        iv = [dict(r) for r in c.execute("SELECT i.* FROM interviews i JOIN pipeline p ON p.id=i.pipe_id WHERE p.job_id=?", (job_id,))]
        pend = [r["kind"] for r in c.execute("SELECT a.kind FROM approvals a JOIN pipeline p ON p.id=a.pipe_id WHERE p.job_id=? AND a.status='pending'", (job_id,))]
    sc = [r for r in rows if r["screening"]]; ok = [r for r in sc if json.loads(r["screening"]).get("pass")]
    t = [i["result"] for i in iv if i["kind"] == "tech" and i["result"]]; h = [i["result"] for i in iv if i["kind"] == "hr" and i["result"]]
    return "\n".join([f"Candidates found: {len(rows)}", f"Shortlisted: {len(sc)}  |  Cleared screening: {len(ok)}",
                      f"Tech round: {t.count('pass')} selected, {t.count('fail')} not selected",
                      f"HR round: {h.count('pass')} selected, {h.count('fail')} not selected",
                      f"Waiting for your approval: {pend.count('offer')} offers, {pend.count('rejection')} rejections"])

def run_agent(job_id, instruction=DEFAULT_INSTRUCTION):
    """Runs the whole cycle (LLM tool use if configured, otherwise rule-based) and returns a plain-language summary."""
    note = ""
    if provider() is not None:
        try: note = _run_llm(job_id, instruction)
        except Exception as e: g.audit("system", "llm_error", str(e))
    if not pipeline_status(job_id):  # no LLM, or it did nothing: run the fixed steps
        source_and_score(job_id); shortlist(job_id); run_screening(job_id)
    schedule_all_screened(job_id); run_interviews(job_id)  # idempotent: only acts on candidates still waiting
    return cycle_summary(job_id) + (f"\n{note.strip()}" if note and note.strip() else "")

def _run_llm(job_id, instruction):
    if provider() == "oai": return _run_agent_oai(job_id, instruction)
    cl = _client()
    impl = _impl(job_id)
    jb = job(job_id)
    msgs = [{"role": "user", "content": f"Job: {jb['title']}\nJD:\n{jb['jd']}\n\nTask: {instruction}"}]
    for _ in range(10):
        r = cl.messages.create(model=MODEL, max_tokens=1500, system=SYSTEM, tools=TOOLS, messages=msgs)
        msgs.append({"role": "assistant", "content": r.content})
        if r.stop_reason != "tool_use": return "".join(b.text for b in r.content if b.type == "text")
        results = []
        for b in r.content:
            if b.type == "tool_use":
                g.audit("agent", "tool_call", f"{b.name} {json.dumps(b.input)}")
                try: out = impl[b.name](b.input)
                except Exception as e: out = {"error": str(e)}
                results.append({"type": "tool_result", "tool_use_id": b.id, "content": json.dumps(out)})
        msgs.append({"role": "user", "content": results})
    return "Stopped after max steps."