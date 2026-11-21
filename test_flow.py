"""Headless end-to-end test (no API key needed)."""
import os
os.environ["RECRUITER_DB"] = "test.db"
if os.path.exists("test.db"): os.remove("test.db")
import db, agent as A, jobs_seed; db.init(); jobs_seed.seed()
try: A.create_job("X", "Looking for a young male developer", ["python"], [], 1, 10, 30, "Remote"); assert 0
except ValueError as e: print("bias blocked:", e)
with db.conn() as c: print("jobs seeded:", c.execute("SELECT COUNT(*) FROM jobs").fetchone()[0])
jid = 1
print(A.run_agent(jid))
with db.conn() as c:
    pend = [dict(r) for r in c.execute("SELECT * FROM approvals WHERE status='pending'")]
    assert c.execute("SELECT COUNT(*) FROM outbox WHERE subject LIKE 'Offer%'").fetchone()[0] == 0  # nothing released without human
offers = [a for a in pend if a["kind"] == "offer"]; print("offer drafts:", len(offers), "rejection drafts:", len(pend) - len(offers))
assert A.decide(offers[0]["id"], True, "")["error"]              # needs a named reviewer
print(A.decide(offers[0]["id"], True, "HR Manager"))
A.candidate_response(offers[0]["pipe_id"], True); print(A.kpis(jid))