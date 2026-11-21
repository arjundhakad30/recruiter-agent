"""16 roles x 6 well-known companies = 96 job notices. seed() runs once when the jobs table is empty."""
import datetime, json

CRITERIA = "60% or above in Class 10 and Class 12, 6.0 CGPA or above in graduation, no active backlogs"
TECH = "Computer Science, Information Technology, Electronics & Communication, Electrical"
# title, must, nice, min_exp, base_salary_LPA, months, branches, responsibilities
ROLES = [
 ("Backend Engineer", ["python", "sql", "rest api"], ["docker", "aws", "fastapi"], 2, 12, 12, TECH,
  ["Design and build REST APIs and backend services", "Write and optimise SQL queries and data models", "Test, deploy and monitor services in production", "Review code and document system design"]),
 ("Frontend Developer", ["javascript", "react", "html", "css"], ["typescript", "tailwind", "redux"], 1, 9, 12, TECH,
  ["Build responsive user interfaces with React", "Convert designs into clean, accessible components", "Integrate frontend screens with backend APIs", "Fix browser issues and improve page speed"]),
 ("Full-Stack Developer", ["javascript", "node", "sql", "react"], ["docker", "mongodb", "typescript"], 2, 11, 12, TECH,
  ["Build features across the user interface and server", "Design APIs and database tables", "Write tests and fix production issues", "Work with product and design teams on releases"]),
 ("Data Analyst", ["sql", "excel", "python", "power bi"], ["tableau", "statistics", "pandas"], 1, 8, 12, TECH + ", Mechanical, Chemical",
  ["Clean and analyse business data using SQL and Python", "Build dashboards and regular reports", "Find trends and explain them to business teams", "Check data quality and document metrics"]),
 ("Data Scientist", ["python", "machine learning", "statistics", "sql"], ["tensorflow", "nlp", "pandas"], 2, 14, 12, TECH,
  ["Build and validate machine learning models", "Run experiments and measure results", "Prepare features and datasets from raw data", "Present findings to technical and business teams"]),
 ("ML Engineer", ["python", "pytorch", "machine learning", "deep learning"], ["mlops", "docker", "aws"], 2, 16, 12, TECH,
  ["Train, tune and evaluate deep learning models", "Package models into reliable services", "Monitor model quality after release", "Work with data scientists on research ideas"]),
 ("DevOps Engineer", ["linux", "docker", "ci/cd", "kubernetes"], ["terraform", "aws", "jenkins"], 2, 12, 12, TECH,
  ["Build and maintain CI/CD pipelines", "Run containers on Kubernetes clusters", "Automate infrastructure and monitoring", "Respond to incidents and improve reliability"]),
 ("QA Automation Engineer", ["selenium", "java", "testing", "sql"], ["cypress", "jenkins", "api testing"], 1, 7.5, 12, TECH,
  ["Write automated test scripts for web applications", "Design test cases and report defects clearly", "Validate data using SQL queries", "Run regression suites in CI pipelines"]),
 ("Android Developer", ["kotlin", "android", "java", "rest api"], ["jetpack compose", "firebase", "sqlite"], 1, 9.5, 12, TECH,
  ["Build and maintain Android app features in Kotlin", "Connect the app with backend REST APIs", "Fix crashes and improve app performance", "Publish releases with the mobile team"]),
 ("Cloud Engineer", ["aws", "linux", "networking", "python"], ["terraform", "azure", "docker"], 2, 12, 12, TECH,
  ["Set up and manage cloud infrastructure", "Automate routine cloud tasks with Python", "Keep networks, access and costs under control", "Support teams migrating applications to the cloud"]),
 ("Cybersecurity Analyst", ["networking", "linux", "security", "siem"], ["python", "penetration testing", "wireshark"], 1, 10, 12, TECH,
  ["Monitor alerts in the SIEM and investigate incidents", "Find and report security weaknesses", "Check systems and networks against security policies", "Write incident reports and recommend fixes"]),
 ("Embedded Systems Engineer", ["c", "c++", "microcontrollers", "rtos"], ["embedded linux", "python", "iot"], 1, 8.5, 12, "Electronics & Communication, Electrical, Instrumentation",
  ["Write firmware in C/C++ for microcontrollers", "Bring up and debug hardware boards", "Work with RTOS tasks, timers and interrupts", "Test devices and document results"]),
 ("UI/UX Designer", ["figma", "wireframing", "user research", "prototyping"], ["adobe xd", "html", "css"], 1, 7, 12, "Any branch",
  ["Create wireframes and clickable prototypes in Figma", "Run user research and usability tests", "Turn feedback into better screens", "Hand over clear design files to developers"]),
 ("Business Analyst", ["sql", "excel", "requirements gathering", "documentation"], ["power bi", "jira", "agile"], 1, 8, 12, "Any branch",
  ["Gather and document business requirements", "Analyse data with SQL and Excel", "Coordinate between business and technical teams", "Track tasks and progress in Jira"]),
 ("Associate Product Manager", ["product strategy", "roadmapping", "analytics", "communication"], ["sql", "jira", "user research"], 1, 12, 12, "Any branch",
  ["Help define the product roadmap", "Study user data to decide what to build", "Write clear requirements for engineering teams", "Track launches and report results"]),
 ("Technical Support Engineer", ["troubleshooting", "linux", "sql", "networking"], ["scripting", "ticketing", "python"], 0, 6.5, 6, TECH + ", Mechanical, Chemical",
  ["Resolve customer technical issues through tickets and calls", "Check logs and databases to find root causes", "Escalate complex problems with clear notes", "Write help articles for common problems"]),
]

TIER = {1.3: ["Google", "Microsoft", "Amazon", "Amazon Web Services", "Adobe", "NVIDIA", "Qualcomm", "Flipkart", "PhonePe", "Walmart Global Tech",
              "American Express", "Mastercard", "Palo Alto Networks", "Cisco", "Oracle", "Intel", "Texas Instruments"],
        1.1: ["Zoho", "Swiggy", "Zomato", "Paytm", "Samsung R&D", "Red Hat", "SAP Labs", "IBM", "Freshworks", "MakeMyTrip", "Reliance Jio",
              "Fractal Analytics", "Tiger Analytics", "Deloitte", "EY", "KPMG", "PwC", "ZS Associates", "Tata Elxsi", "L&T Technology Services",
              "Bosch", "Quick Heal", "Mu Sigma"],
        0.95: ["Infosys", "TCS", "Wipro", "Tech Mahindra", "HCLTech", "Cognizant", "Capgemini", "Accenture", "LTIMindtree", "Concentrix", "Genpact"]}
MULT = {c: m for m, cs in TIER.items() for c in cs}
LOCS = {"Infosys": ["Bengaluru", "Pune", "Hyderabad", "Chennai"], "TCS": ["Mumbai", "Pune", "Chennai", "Hyderabad"], "Wipro": ["Bengaluru", "Hyderabad", "Pune", "Noida"],
        "Tech Mahindra": ["Pune", "Hyderabad", "Noida", "Bengaluru"], "HCLTech": ["Noida", "Chennai", "Bengaluru"], "Cognizant": ["Chennai", "Pune", "Kolkata", "Hyderabad"],
        "Capgemini": ["Mumbai", "Pune", "Bengaluru", "Noida"], "Accenture": ["Bengaluru", "Pune", "Gurugram", "Hyderabad"], "LTIMindtree": ["Mumbai", "Pune", "Bengaluru"],
        "Concentrix": ["Gurugram", "Noida", "Bengaluru"], "Genpact": ["Gurugram", "Noida", "Jaipur", "Hyderabad"], "Zoho": ["Chennai"], "Flipkart": ["Bengaluru"],
        "Paytm": ["Noida"], "Swiggy": ["Bengaluru"], "Zomato": ["Gurugram"], "MakeMyTrip": ["Gurugram"], "PhonePe": ["Bengaluru"], "Freshworks": ["Chennai"],
        "Amazon": ["Bengaluru", "Hyderabad", "Chennai"], "Microsoft": ["Hyderabad", "Bengaluru", "Noida"], "Adobe": ["Noida", "Bengaluru"],
        "Google": ["Bengaluru", "Hyderabad", "Gurugram"], "Deloitte": ["Hyderabad", "Bengaluru", "Mumbai", "Gurugram"], "EY": ["Gurugram", "Bengaluru", "Kolkata"],
        "KPMG": ["Gurugram", "Bengaluru", "Mumbai"], "PwC": ["Kolkata", "Bengaluru", "Gurugram"], "Mu Sigma": ["Bengaluru"], "Fractal Analytics": ["Mumbai", "Bengaluru"],
        "ZS Associates": ["Pune", "Gurugram"], "Walmart Global Tech": ["Bengaluru", "Chennai"], "American Express": ["Gurugram", "Bengaluru"], "Mastercard": ["Pune", "Gurugram"],
        "Tiger Analytics": ["Chennai", "Bengaluru"], "NVIDIA": ["Pune", "Bengaluru"], "Qualcomm": ["Hyderabad", "Bengaluru"], "Intel": ["Bengaluru"],
        "Samsung R&D": ["Bengaluru", "Noida"], "IBM": ["Bengaluru", "Pune", "Hyderabad"], "Cisco": ["Bengaluru"], "Red Hat": ["Pune", "Bengaluru"],
        "Oracle": ["Bengaluru", "Hyderabad"], "SAP Labs": ["Bengaluru", "Pune"], "Amazon Web Services": ["Bengaluru", "Hyderabad"], "Palo Alto Networks": ["Bengaluru"],
        "Quick Heal": ["Pune"], "Reliance Jio": ["Mumbai", "Navi Mumbai"], "Bosch": ["Bengaluru", "Coimbatore"], "Texas Instruments": ["Bengaluru"],
        "Tata Elxsi": ["Bengaluru", "Pune"], "L&T Technology Services": ["Bengaluru", "Vadodara"]}
COMPANIES = {
 "Backend Engineer": ["Infosys", "TCS", "Wipro", "Zoho", "Flipkart", "Paytm"],
 "Frontend Developer": ["Accenture", "Cognizant", "HCLTech", "Capgemini", "Swiggy", "MakeMyTrip"],
 "Full-Stack Developer": ["Amazon", "Microsoft", "Adobe", "Zomato", "PhonePe", "Freshworks"],
 "Data Analyst": ["Deloitte", "EY", "KPMG", "Mu Sigma", "Fractal Analytics", "ZS Associates"],
 "Data Scientist": ["Walmart Global Tech", "American Express", "Mastercard", "Fractal Analytics", "Tiger Analytics", "Mu Sigma"],
 "ML Engineer": ["NVIDIA", "Qualcomm", "Intel", "Samsung R&D", "Adobe", "Amazon"],
 "DevOps Engineer": ["IBM", "Cisco", "Red Hat", "Oracle", "SAP Labs", "HCLTech"],
 "QA Automation Engineer": ["Infosys", "Wipro", "Tech Mahindra", "Cognizant", "Capgemini", "LTIMindtree"],
 "Android Developer": ["Paytm", "PhonePe", "Swiggy", "Zomato", "Samsung R&D", "Reliance Jio"],
 "Cloud Engineer": ["Amazon Web Services", "Microsoft", "Google", "Oracle", "IBM", "Accenture"],
 "Cybersecurity Analyst": ["Palo Alto Networks", "Cisco", "Quick Heal", "Deloitte", "PwC", "IBM"],
 "Embedded Systems Engineer": ["Bosch", "Texas Instruments", "Qualcomm", "Samsung R&D", "Tata Elxsi", "L&T Technology Services"],
 "UI/UX Designer": ["Flipkart", "Swiggy", "Zomato", "Adobe", "Zoho", "Paytm"],
 "Business Analyst": ["Deloitte", "EY", "KPMG", "PwC", "Accenture", "Genpact"],
 "Associate Product Manager": ["Flipkart", "Amazon", "Swiggy", "Zomato", "PhonePe", "Google"],
 "Technical Support Engineer": ["Tech Mahindra", "Wipro", "HCLTech", "Concentrix", "Genpact", "Cognizant"],
}

def jd_for(company, title, must, nice, min_exp, location, resp):
    return (f"# {title} - {company}\n\n## About the role\n{company} is hiring a {title} for its {location} team. "
            f"The role starts as an internship-cum-recruitment programme.\n\n## Responsibilities\n" + "\n".join(f"- {r}" for r in resp) +
            f"\n\n## Requirements\n- {min_exp}+ years of relevant experience (internships and projects count)\n- Skills: {', '.join(must)}\n\n"
            f"## Nice to have\n- {', '.join(nice)}\n\n## Equal opportunity\nAll qualified applicants are considered on skills and merit only.")

def make_meta(n, company, title, locations, location, branches, stipend, salary, months, resp=(), last_date=None, apply_link=None,
              course="B.Tech", batch="2027", criteria=CRITERIA, mode="Offline (campus) / Online interview"):
    today = datetime.date.today()
    slug = f"{company}-{title}".lower().replace(" ", "-").replace("&", "and").replace("/", "-")
    return dict(notice_no=f"F(39)/2026/{n:02d}", notice_date=today.strftime("%d.%m.%Y"), company=company, course=course, batch=batch,
                branches=branches, criteria=criteria, role=title, months=months, stipend_lpa=stipend, salary_lpa=salary, location=location,
                locations=list(locations), resp=list(resp), apply_link=apply_link or f"https://forms.example.com/{slug}",
                last_date=last_date or (today + datetime.timedelta(days=5)).strftime("%d %b %Y") + ", 04:00 PM", mode=mode)

def seed():
    import agent as A, db
    with db.conn() as c:
        row = c.execute("SELECT meta FROM jobs LIMIT 1").fetchone()
        if row and "locations" in json.loads(row["meta"] or "{}"): return  # already up to date
        if row:  # old database from an earlier version: reset job-related data and reseed
            for t in ("jobs", "pipeline", "interviews", "approvals", "outbox", "audit"): c.execute(f"DELETE FROM {t}")
            c.execute("UPDATE slots SET booked_by=NULL")
    n = 0
    for title, must, nice, exp, base, mo, br, resp in ROLES:
        for co in COMPANIES[title]:
            n += 1; locs = LOCS[co]; pkg = round(base * MULT[co] * 2) / 2
            A.create_job(title, jd_for(co, title, must, nice, exp, locs[0], resp), must, nice, exp, pkg, 60, locs[0],
                         meta=make_meta(n, co, title, locs, locs[0], br, round(pkg * 0.55, 1), pkg, mo, resp), audit=False)