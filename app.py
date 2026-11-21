import json, re, html, datetime, pandas as pd, streamlit as st
import db, agent as A, guardrails as g, jobs_seed, pdf_gen

st.set_page_config(page_title="Recruiter Agent", layout="wide")
db.init(); jobs_seed.seed()

st.markdown("""<style>
.block-container{padding-top:1.4rem;max-width:1320px}
.stTabs [data-baseweb="tab"]{font-weight:600;padding:8px 18px}
[data-testid="stMetric"]{border:1px solid #d0d0d0;border-radius:8px;padding:10px 14px;background:#fff}
[data-testid="stMetric"] *{color:#222 !important}
.card{border:1px solid #d0d0d0;border-left:4px solid var(--c,#555);border-radius:6px;padding:7px 10px;margin-bottom:7px;background:#fff;color:#222;font-size:13px}
.colh{font-weight:700;border-bottom:2px solid #888;margin-bottom:8px;padding-bottom:3px;font-size:13px}
.kcap{font-size:12.5px;opacity:.8;margin-top:-6px;margin-bottom:10px}
.bar{background:#e6e6e6;border-radius:4px;height:20px;margin:3px 0}.bar>div{background:#444;height:20px;border-radius:4px;color:#fff;font-size:12px;padding-left:8px;line-height:20px}
.notice{background:#fff;color:#111;border:1px solid #bbb;border-radius:4px;padding:22px 28px;font-family:Georgia,'Times New Roman',serif}
.notice h3{text-align:center;margin:0 0 6px;font-size:18px;color:#111}
.notice .meta{display:flex;justify-content:space-between;font-size:13px;font-weight:700;margin-top:8px}
.notice .sub{text-align:center;font-weight:700;font-size:15px;margin:8px 0}
.notice table{width:100%;border-collapse:collapse;margin-top:8px;font-size:13.5px}
.notice th,.notice td{border:1px solid #333;padding:6px 10px;text-align:left;vertical-align:top;color:#111}
.notice th{background:#f1f1f1}.notice td.k{width:34%}.notice td.sl{width:5%;text-align:center}.notice td.v{font-weight:700}
.notice .note{font-size:13px;margin-top:12px}.notice .note b.r{color:#c00000}
</style>""", unsafe_allow_html=True)

STAGE_COL = {"Sourced": "#8a94a8", "Shortlisted": "#0f9d9a", "Screened": "#2e8b57", "Tech": "#8e44ad", "HR": "#b8860b",
             "Offer Pending": "#e67e22", "Offered": "#c0392b", "Accepted": "#1e9e4a", "Declined": "#777", "Rejected": "#444"}
E = lambda x: html.escape(str(x))
NAME = lambda cid: A.POOL[cid]["name"]

def notice_html(jb):
    m = json.loads(jb.get("meta") or "{}"); must = ", ".join(json.loads(jb["must"])); nice = ", ".join(json.loads(jb["nice"]))
    rows = [("Name of Company", m["company"]), ("Eligible Course", m["course"]), ("Eligible Passing / Passed out Batch", m["batch"]),
            ("Eligible Branches", m["branches"]), ("Eligibility Criteria", m["criteria"]), ("Candidates Required", "All genders (equal opportunity)"),
            ("Job Offered / Employment Role", jb["title"]), ("Required Skills", must), ("Preferred Skills", nice),
            ("Duration of Internship / Probation", f"{m['months']} months, as per company norms or JD"),
            ("Stipend during Internship / Probation", f"On joining total pay (fixed pay) ₹{m['stipend_lpa']} LPA"),
            ("Salary Offered after Internship / Probation", f"On completion of {m['months']} months ₹{m['salary_lpa']} LPA"),
            ("Job / Internship Location", jb["location"]), ("Apply Link", m["apply_link"]), ("Last date to Apply", m["last_date"]), ("Mode of Campus / Internship", m["mode"])]
    body = "".join(f"<tr><td class='sl'>{i:02d}</td><td class='k'>{E(k)}</td><td class='v'>{E(v)}</td></tr>" for i, (k, v) in enumerate(rows, 1))
    return (f"<div class='notice'><h3>CAMPUS DRIVE NOTICE (2026) - {E(m['notice_no'][-2:])} - {E(m['company'])}</h3>"
            f"<div class='meta'><span>No.: {E(m['notice_no'])}</span><span>Date: {E(m['notice_date'])}</span></div>"
            f"<div class='sub'>{E(m['company'])} is organizing a drive for Internship-cum-Recruitment as per the description below:</div>"
            f"<table><tr><th>Sl.</th><th>PARTICULARS</th><th>COMPANY DETAILS</th></tr>{body}</table>"
            "<div class='note'><b>Applicants please note:</b> <b class='r'>Read the job description carefully and apply in accordance with the eligibility criteria.</b>"
            "<ol><li>Only eligible and unselected applicants can apply for this drive.</li><li>Applicants must submit consent at the apply link by the last date.</li>"
            "<li>Shortlisting is based on skills and experience only. Offers and rejections are released after human approval.</li>"
            "<li>Leaving the selection process midway may affect future opportunities.</li></ol></div></div>")

# ---------- current job: role -> company -> location / package ----------
with db.conn() as c: jobs = [dict(r) for r in c.execute("SELECT * FROM jobs ORDER BY id")]
roles = list(dict.fromkeys(j["title"] for j in jobs))
role = st.session_state.get("sel_role", roles[0]); role = role if role in roles else roles[0]
cjobs = [j for j in jobs if j["title"] == role]
jb = cjobs[min(st.session_state.get(f"sel_co_{role}", 0), len(cjobs) - 1)]; jid = jb["id"]; meta = json.loads(jb["meta"])
loc = st.session_state.get(f"loc_{jid}", jb["location"]); pkg = float(st.session_state.get(f"pkg_{jid}", jb["budget_lpa"]))
mv = dict(meta, location=loc, salary_lpa=pkg, stipend_lpa=round(pkg * 0.55, 1)); jbv = dict(jb, location=loc, budget_lpa=pkg, meta=json.dumps(mv))

st.title("Recruiter Agent")
st.sidebar.markdown("### Hiring cycle")
st.sidebar.write(f"**{jb['title']}**  \n{meta['company']}, {loc}")
if st.sidebar.button("Run hiring cycle", type="primary", use_container_width=True):
    A.update_job_terms(jid, loc, pkg)
    with st.spinner("Running hiring cycle..."): st.session_state["last_run"] = (jid, A.run_agent(jid))
    st.rerun()
lr = st.session_state.get("last_run")
if lr and lr[0] == jid:
    st.sidebar.success("Hiring cycle completed")
    st.sidebar.markdown("\n".join(f"- {l}" for l in lr[1].split("\n") if l.strip()))
st.sidebar.caption("AI mode: " + (f"LLM tool use ({A.provider()})" if A.llm_on() else "rule-based (no LLM configured)"))

tabs = st.tabs(["Brief & JD", "Pipeline", "Interviews & Offers", "Human Approvals", "KPIs & Audit"])

# ---------- Brief & JD ----------
with tabs[0]:
    c1, c2, c3, c4 = st.columns([2, 3, 2, 1.5])
    c1.selectbox("Job role", roles, key="sel_role")
    c2.selectbox("Company", range(len(cjobs)), key=f"sel_co_{role}",
                 format_func=lambda i: f"{json.loads(cjobs[i]['meta'])['company']}  |  {', '.join(json.loads(cjobs[i]['meta'])['locations'])}")
    locs = meta["locations"]
    c3.selectbox("Location", locs, index=locs.index(jb["location"]) if jb["location"] in locs else 0, key=f"loc_{jid}")
    c4.number_input("Package (LPA)", 1.0, 100.0, float(jb["budget_lpa"]), step=0.5, key=f"pkg_{jid}")
    st.caption("Company, location and package values are indicative. Choose them, check the notice, then confirm.")
    st.markdown(notice_html(jbv), unsafe_allow_html=True)
    sig = (jid, loc, pkg); st.write("")
    if st.button("Confirm notice", type="primary"): st.session_state["confirmed"] = sig
    if st.session_state.get("confirmed") == sig:
        st.success("Notice confirmed. Download the PDFs below.")
        slug = f"{meta['company']}-{jb['title']}".lower().replace(" ", "-").replace("/", "-").replace("&", "and")
        d1, d2 = st.columns(2)
        d1.download_button("Drive Notice (short PDF)", pdf_gen.notice_pdf(jbv), f"drive-notice-{slug}.pdf", "application/pdf", use_container_width=True)
        d2.download_button("Job Description (detailed PDF)", pdf_gen.detail_pdf(jbv), f"job-description-{slug}.pdf", "application/pdf", use_container_width=True)

# ---------- Pipeline ----------
with db.conn() as c: rows = [dict(r) for r in c.execute("SELECT * FROM pipeline WHERE job_id=? ORDER BY score DESC", (jid,))]
with tabs[1]:
    st.markdown(f"#### Candidate pipeline: {jb['title']} at {meta['company']}")
    if not rows: st.info("No candidates yet. Click 'Run hiring cycle' in the sidebar.")
    groups = [("Sourced",), ("Shortlisted",), ("Screened",), ("Tech", "HR"), ("Offer Pending", "Offered"), ("Accepted", "Declined", "Rejected")]
    for col, grp in zip(st.columns(len(groups)), groups):
        col.markdown(f"<div class='colh'>{' / '.join(grp)} ({len([r for r in rows if r['stage'] in grp])})</div>", unsafe_allow_html=True)
        for r in [r for r in rows if r["stage"] in grp]:
            col.markdown(f"<div class='card' style='--c:{STAGE_COL[r['stage']]}'><b>{E(NAME(r['cand_id']))}</b><br><small>Score {r['score']} · {r['stage']}</small></div>", unsafe_allow_html=True)
    if rows:
        st.dataframe(pd.DataFrame([{"Candidate": NAME(r["cand_id"]), "Stage": r["stage"], "Overall score": r["score"], **{k: v for k, v in zip(["Skills match (60)", "Preferred skills (15)", "Experience (25)"], json.loads(r["breakdown"]).values())},
                                   "Remarks": r["rationale"]} for r in rows]), hide_index=True, width="stretch")
        scr = [r for r in rows if r["screening"]]
        if scr:
            sel = st.selectbox("Screening call result for", [r["id"] for r in scr], format_func=lambda i: NAME(next(r["cand_id"] for r in scr if r["id"] == i)))
            r = next(x for x in scr if x["id"] == sel); p = A.POOL[r["cand_id"]]; ck = json.loads(r["screening"])["checks"]
            ok = lambda b: "Pass" if b else "Not aligned"
            st.dataframe(pd.DataFrame([
                {"Check": "Notice period", "Candidate": f"{p['notice_days']} days", "Requirement": f"Up to {jb['max_notice']} days", "Result": ok(ck["notice_period"])},
                {"Check": "Salary expectation", "Candidate": f"₹{p['expected_lpa']} LPA", "Requirement": f"Up to ₹{round(jb['budget_lpa'] * 1.15, 1)} LPA", "Result": ok(ck["expectation_within_band"])},
                {"Check": "Location", "Candidate": p["location"] + (" (open to relocate)" if p.get("relocate", True) else ""), "Requirement": jb["location"], "Result": ok(ck["location_fit"])}]),
                hide_index=True, width="stretch")

# ---------- Interviews & Offers ----------
with tabs[2]:
    with db.conn() as c:
        iv = [dict(r) for r in c.execute("SELECT i.*, p.cand_id FROM interviews i JOIN pipeline p ON p.id=i.pipe_id WHERE p.job_id=? ORDER BY i.id", (jid,))]
    st.markdown("#### Interview results")
    if not iv: st.caption("No interviews yet. Click 'Run hiring cycle' in the sidebar.")
    else:
        cnt = lambda k, v: len([i for i in iv if i["kind"] == k and i["result"] == v])
        for col, (lab, k, v) in zip(st.columns(4), [("Tech round: selected", "tech", "pass"), ("Tech round: not selected", "tech", "fail"), ("HR round: selected", "hr", "pass"), ("HR round: not selected", "hr", "fail")]):
            col.metric(lab, cnt(k, v))
        st.dataframe(pd.DataFrame([{"Candidate": NAME(i["cand_id"]), "Round": i["kind"].upper(), "Scheduled": i["start"],
                                    "Result": {"pass": "Selected", "fail": "Not selected"}.get(i["result"], "Pending"), "Panel feedback": i["note"] or ""} for i in iv]), hide_index=True, width="stretch")
    st.markdown("#### Offer tracker")
    off = [r for r in rows if r["stage"] in ("Offer Pending", "Offered", "Accepted", "Declined")]
    if not off: st.caption("No offers yet.")
    for r in off:
        with db.conn() as c: ap = c.execute("SELECT terms,status FROM approvals WHERE pipe_id=? AND kind='offer' AND status IN ('pending','approved') ORDER BY id DESC LIMIT 1", (r["id"],)).fetchone()
        ctc = json.loads(ap["terms"])["ctc_lpa"] if ap else "-"
        with st.container(border=True):
            x, y, z = st.columns([3, 2, 2]); x.write(f"**{NAME(r['cand_id'])}**"); y.write(f"Offer: ₹{ctc} LPA"); z.write({"Offer Pending": "Waiting for HR approval", "Offered": "Offer released"}.get(r["stage"], r["stage"]))
            if r["stage"] == "Offered":
                a, b, _ = st.columns([1.2, 1.2, 6])
                if a.button("Offer accepted", key=f"a{r['id']}"): A.candidate_response(r["id"], True); st.rerun()
                if b.button("Offer declined", key=f"d{r['id']}"): A.candidate_response(r["id"], False); st.rerun()
    op = [r for r in rows if r["stage"] in ("Offer Pending", "Offered")]
    if op:
        st.markdown("#### Negotiation")
        who = st.selectbox("Candidate", [r["id"] for r in op], format_func=lambda x: NAME(next(r["cand_id"] for r in op if r["id"] == x)))
        ask = st.number_input("Candidate's counter-ask (LPA)", 1.0, 100.0, float(jbv["budget_lpa"]) + 2)
        if st.button("Redraft offer"):
            res = A.draft_offer(who, ask); st.success(f"New offer drafted at ₹{res['terms']['ctc_lpa']} LPA. {res['terms']['negotiation_note']} It is waiting in Human Approvals.")

# ---------- Human Approvals ----------
with tabs[3]:
    st.markdown("#### Human checkpoint: every offer and every rejection is released only after your approval")
    reviewer = st.text_input("Reviewer name")
    with db.conn() as c:
        ap = [dict(r) for r in c.execute("SELECT a.*, p.cand_id FROM approvals a JOIN pipeline p ON p.id=a.pipe_id WHERE p.job_id=? AND a.status='pending' ORDER BY a.kind DESC, a.id", (jid,))]
    if not ap: st.success("Nothing pending.")
    for a in ap:
        t = json.loads(a["terms"])
        with st.expander(f"{'Offer letter' if a['kind'] == 'offer' else 'Rejection letter'}  |  {NAME(a['cand_id'])}"):
            st.text(a["draft"]); ctc = None
            if a["kind"] == "offer": ctc = st.number_input("Final CTC (LPA)", value=float(t["ctc_lpa"]), key=f"c{a['id']}"); st.caption(t["negotiation_note"])
            x, y, _ = st.columns([2, 1, 5])
            if x.button("Approve & send", key=f"ok{a['id']}", type="primary"):
                r = A.decide(a["id"], True, reviewer, ctc_lpa=ctc); st.error("Enter the reviewer name first.") if "error" in r else st.rerun()
            if y.button("Decline", key=f"no{a['id']}"):
                r = A.decide(a["id"], False, reviewer); st.error("Enter the reviewer name first.") if "error" in r else st.rerun()

# ---------- KPIs & Audit ----------
with tabs[4]:
    with db.conn() as c:
        iv = [dict(r) for r in c.execute("SELECT i.pipe_id FROM interviews i JOIN pipeline p ON p.id=i.pipe_id WHERE p.job_id=?", (jid,))]
    later = ("Shortlisted", "Screened", "Tech", "HR", "Offer Pending", "Offered", "Accepted", "Declined")
    sl = [r for r in rows if r["screening"] or r["stage"] in later]; scr_ok = [r for r in rows if r["screening"] and json.loads(r["screening"]).get("pass")]
    interviewed = {i["pipe_id"] for i in iv}; offered = [r for r in rows if r["stage"] in ("Offered", "Accepted", "Declined")]; acc = [r for r in rows if r["stage"] == "Accepted"]
    pct = lambda a, b: f"{a / b:.0%}" if b else "-"
    if acc:
        secs = sum(r["updated"] - r["created"] for r in acc) / len(acc); tth = f"{secs:.0f} sec" if secs < 60 else f"{secs / 60:.1f} min"
    else: tth = "-"
    st.markdown("#### Hiring KPIs")
    st.caption(f"For: {jb['title']} at {meta['company']}")
    k = st.columns(4)
    k[0].metric("Candidates sourced", len(rows)); k[0].markdown("<div class='kcap'>Profiles found and scored against this job.</div>", unsafe_allow_html=True)
    k[1].metric("Shortlist to interview", pct(len(interviewed), len(sl))); k[1].markdown(f"<div class='kcap'>{len(interviewed)} of {len(sl)} shortlisted candidates reached an interview.</div>", unsafe_allow_html=True)
    k[2].metric("Time to hire", tth); k[2].markdown("<div class='kcap'>Average time from sourcing to offer accepted. Shows '-' until an offer is accepted. Demo runs in minutes; real hiring takes days.</div>", unsafe_allow_html=True)
    k[3].metric("Offer acceptance rate", pct(len(acc), len(offered))); k[3].markdown(f"<div class='kcap'>{len(acc)} of {len(offered)} released offers accepted.</div>", unsafe_allow_html=True)
    st.markdown("#### Hiring funnel")
    fun = [("Sourced", len(rows)), ("Shortlisted", len(sl)), ("Cleared screening", len(scr_ok)), ("Interviewed", len(interviewed)), ("Offer released", len(offered)), ("Offer accepted", len(acc))]
    top = max(fun[0][1], 1)
    for lab, n in fun:
        a, b = st.columns([1, 5]); a.write(lab); b.markdown(f"<div class='bar'><div style='width:{max(n / top * 100, 4)}%'>{n}</div></div>", unsafe_allow_html=True)

    st.markdown("#### Emails sent")
    with db.conn() as c:
        ob = [dict(r) for r in c.execute("SELECT o.*, p.cand_id FROM outbox o JOIN pipeline p ON p.id=o.pipe_id WHERE p.job_id=? ORDER BY o.id DESC", (jid,))]
    if ob: st.dataframe(pd.DataFrame([{"Date and time": datetime.datetime.fromtimestamp(o["ts"]).strftime("%d %b, %I:%M %p"), "To": NAME(o["cand_id"]), "Subject": o["subject"], "Status": "Sent"} for o in ob]), hide_index=True, width="stretch")
    else: st.caption("No emails sent yet.")

    st.markdown("#### Activity log")
    st.caption("A record of every step taken by the agent, the interview panel and the HR team.")
    with db.conn() as c:
        allp = {r["id"]: r for r in c.execute("SELECT id, cand_id, job_id FROM pipeline")}; apr = {r["id"]: r["pipe_id"] for r in c.execute("SELECT id, pipe_id FROM approvals")}
        logs = [dict(r) for r in c.execute("SELECT * FROM audit ORDER BY id DESC LIMIT 1500")]
    def who(a): return ("Recruiter Agent" if a == "agent" else "HR Reviewer - " + a[6:] if a.startswith("human:") else "HR Team" if a == "human" else "Interview Panel" if a == "panel" else "Candidate" if a == "candidate" else "System")
    def describe(l):
        d = l["detail"] or ""; m = re.search(r"pipe=(\d+)", d); am = re.search(r"approval=(\d+)", d)
        pid = int(m.group(1)) if m else apr.get(int(am.group(1))) if am else None
        if pid is not None and (pid not in allp or allp[pid]["job_id"] != jid): return None
        if pid is None and l["action"] == "sourced" and f"job={jid} " not in d: return None
        nm = NAME(allp[pid]["cand_id"]) if pid is not None else ""; a = l["action"]
        if a == "sourced": n = re.search(r"new=(\d+)", d).group(1); return f"Searched the candidate pool and added {n} new matching candidates"
        if a == "stage_change": return f"{nm} moved to: {d.split('->')[1].strip()}"
        if a == "email_sent": return f"Email sent to {nm}: {d.split('subject=')[1]}"
        if a == "rejection_drafted": return f"Rejection letter drafted for {nm} (waiting for HR approval)"
        if a == "offer_drafted": ctc = re.search(r"ctc_lpa.: ([0-9.]+)", d).group(1); return f"Offer letter drafted for {nm} at ₹{ctc} LPA (waiting for HR approval)"
        if a == "offer_approved": return f"Offer letter approved and sent to {nm}"
        if a == "rejection_approved": return f"Rejection letter approved and sent to {nm}"
        if a in ("offer_declined", "rejection_declined"): return f"HR declined the {a.split('_')[0]} draft for {nm}"
        if a == "interview_result": p = d.split(); return f"{p[1].upper()} interview result for {nm}: {'Selected' if p[2] == 'pass' else 'Not selected'}"
        if a == "tool_call": return f"AI agent used tool: {d.split()[0]}"
        if a == "bias_block": return "A job description was blocked by the bias check"
        if a == "llm_error": return "AI service not reachable, rule-based steps were used"
        return a.replace("_", " ").capitalize()
    out = [(l, describe(l)) for l in logs]; out = [(l, t) for l, t in out if t][:200]
    if out: st.dataframe(pd.DataFrame([{"Time": datetime.datetime.fromtimestamp(l["ts"]).strftime("%d %b, %I:%M %p"), "Done by": who(l["actor"]), "Activity": t} for l, t in out]), hide_index=True, width="stretch")
    else: st.caption("No activity yet.")