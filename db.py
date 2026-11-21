import sqlite3, os, time
from datetime import datetime, timedelta
DB = os.environ.get("RECRUITER_DB", "recruiter.db")

def conn():
    c = sqlite3.connect(DB); c.row_factory = sqlite3.Row; return c

def init():
    with conn() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS jobs(id INTEGER PRIMARY KEY, title TEXT, jd TEXT, must TEXT, nice TEXT,
            min_exp REAL, budget_lpa REAL, max_notice INT, location TEXT, created REAL, meta TEXT);
        CREATE TABLE IF NOT EXISTS pipeline(id INTEGER PRIMARY KEY, job_id INT, cand_id TEXT, stage TEXT, score REAL,
            breakdown TEXT, rationale TEXT, screening TEXT, created REAL, updated REAL, UNIQUE(job_id,cand_id));
        CREATE TABLE IF NOT EXISTS slots(id INTEGER PRIMARY KEY, interviewer TEXT, kind TEXT, start TEXT, booked_by INT);
        CREATE TABLE IF NOT EXISTS interviews(id INTEGER PRIMARY KEY, pipe_id INT, kind TEXT, start TEXT, result TEXT, note TEXT);
        CREATE TABLE IF NOT EXISTS approvals(id INTEGER PRIMARY KEY, pipe_id INT, kind TEXT, draft TEXT, terms TEXT,
            status TEXT, created REAL, decided REAL, reviewer TEXT, note TEXT);
        CREATE TABLE IF NOT EXISTS outbox(id INTEGER PRIMARY KEY, pipe_id INT, to_addr TEXT, subject TEXT, body TEXT, status TEXT, ts REAL);
        CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY, ts REAL, actor TEXT, action TEXT, detail TEXT);
        """)
        try: c.execute("ALTER TABLE jobs ADD COLUMN meta TEXT")  # old databases
        except sqlite3.OperationalError: pass
        if not c.execute("SELECT 1 FROM slots LIMIT 1").fetchone():
            d = datetime.now().replace(hour=10, minute=0, second=0, microsecond=0)
            n = 0
            while n < 10:
                d += timedelta(days=1)
                if d.weekday() >= 5: continue
                n += 1
                for h in (10, 11, 12, 14, 15, 16):
                    s = d.replace(hour=h).strftime("%Y-%m-%d %H:%M")
                    c.execute("INSERT INTO slots(interviewer,kind,start) VALUES('Tech Panel','tech',?)", (s,))
                    c.execute("INSERT INTO slots(interviewer,kind,start) VALUES('HR Lead','hr',?)", (s,))