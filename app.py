from flask import Flask, render_template, request, redirect, session, send_from_directory
from flask_wtf.csrf import CSRFProtect
from dotenv import load_dotenv
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename
import sqlite3
import os
import re
import smtplib
import uuid
from email.message import EmailMessage
from datetime import datetime
from pathlib import Path

try:
    from pypdf import PdfReader
except ImportError:
    PdfReader = None

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")
IS_PRODUCTION = os.environ.get("APP_ENV") == "production"
DB_PATH = Path(os.environ.get("DATABASE_PATH", BASE_DIR / "hr_analyzer.db"))
UPLOAD_FOLDER = Path(os.environ.get("UPLOAD_FOLDER", BASE_DIR / "uploads"))

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY") or (None if IS_PRODUCTION else "local-development-only-change-this")
if not app.secret_key:
    raise RuntimeError("Set the SECRET_KEY environment variable before starting in production.")
app.config["UPLOAD_FOLDER"] = str(UPLOAD_FOLDER)
app.config["MAX_CONTENT_LENGTH"] = 8 * 1024 * 1024
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = IS_PRODUCTION
app.config["APP_ENV"] = "production" if IS_PRODUCTION else "development"

DB_PATH.parent.mkdir(parents=True, exist_ok=True)
UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)
CSRFProtect(app)

HR_USERNAME = os.environ.get("HR_USERNAME", "admin" if not IS_PRODUCTION else "")
HR_PASSWORD = os.environ.get("HR_PASSWORD", "admin123" if not IS_PRODUCTION else "")

SKILL_KEYWORDS = {
    "python": 18,
    "flask": 15,
    "django": 14,
    "sql": 14,
    "mysql": 12,
    "postgresql": 12,
    "javascript": 12,
    "html": 10,
    "css": 10,
    "react": 14,
    "machine learning": 18,
    "deep learning": 18,
    "data analysis": 16,
    "pandas": 14,
    "numpy": 14,
    "tableau": 13,
    "power bi": 13,
    "aws": 12,
    "azure": 12,
    "docker": 10,
    "api": 12,
    "rest": 10,
    "git": 9,
    "java": 12,
    "c++": 10,
    "problem solving": 10,
    "communication": 8,
    "teamwork": 8,
    "data structures": 12,
    "statistics": 10,
    "excel": 8,
    "automation": 10,
}


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def create_database():
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS candidates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            email TEXT,
            phone TEXT,
            password TEXT,
            resume TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS applications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            candidate_id INTEGER,
            job TEXT,
            score INTEGER,
            status TEXT,
            applied_date TEXT
        )
    """)

    conn.commit()
    conn.close()

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/candidate/register", methods=["GET", "POST"])
def candidate_register():
    if request.method == "POST":
        name = request.form["name"]
        email = request.form["email"]
        phone = request.form["phone"]
        password = request.form["password"]

        conn = get_db()
        conn.execute("""
            INSERT INTO candidates (name, email, phone, password)
            VALUES (?, ?, ?, ?)
        """, (name, email, phone, generate_password_hash(password)))
        conn.commit()
        conn.close()

        return redirect("/candidate/login")

    return render_template("candidate_register.html")

@app.route("/candidate/login", methods=["GET", "POST"])
def candidate_login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        conn = get_db()
        candidate = conn.execute("""
            SELECT * FROM candidates WHERE email=?
        """, (email,)).fetchone()

        password_matches = False
        if candidate:
            stored_password = candidate["password"] or ""
            try:
                password_matches = check_password_hash(stored_password, password)
            except (ValueError, TypeError):
                password_matches = False
            if not password_matches and stored_password == password:
                password_matches = True
                conn.execute(
                    "UPDATE candidates SET password=? WHERE id=?",
                    (generate_password_hash(password), candidate["id"])
                )
                conn.commit()
        conn.close()

        if candidate and password_matches:
            session["candidate_id"] = candidate["id"]
            return redirect("/candidate/dashboard")

        return "Invalid email or password"

    return render_template("candidate_login.html")

@app.route("/candidate/dashboard")
def candidate_dashboard():
    if "candidate_id" not in session:
        return redirect("/candidate/login")

    conn = get_db()
    candidate = conn.execute("""
        SELECT * FROM candidates WHERE id=?
    """, (session["candidate_id"],)).fetchone()

    applications = conn.execute("""
        SELECT * FROM applications WHERE candidate_id=?
    """, (session["candidate_id"],)).fetchall()
    conn.close()

    return render_template(
        "candidate_dashboard.html",
        candidate=candidate,
        applications=applications
    )

def extract_resume_text(file_path):
    text = ""
    extension = Path(file_path).suffix.lower()

    try:
        if extension == ".txt":
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                text = f.read()
        elif extension == ".pdf" and PdfReader is not None:
            reader = PdfReader(file_path)
            pages = []
            for page in reader.pages:
                pages.append(page.extract_text() or "")
            text = "\n".join(pages)
        else:
            try:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    text = f.read()
            except Exception:
                text = ""
    except Exception:
        text = ""

    return text


def compute_resume_score(resume_text):
    normalized = re.sub(r"\s+", " ", resume_text.lower())
    if not normalized.strip():
        return None

    total_score = 0

    for keyword, value in SKILL_KEYWORDS.items():
        if keyword in normalized:
            total_score += value

    if "experience" in normalized or "worked" in normalized or "intern" in normalized:
        total_score += 10
    if "bachelor" in normalized or "master" in normalized or "degree" in normalized:
        total_score += 10
    if "email" in normalized or "@" in normalized:
        total_score += 5

    score = min(100, total_score)
    return score


@app.route("/candidate/apply", methods=["GET", "POST"])
def apply_job():
    if "candidate_id" not in session:
        return redirect("/candidate/login")

    if request.method == "POST":
        job = request.form["job"]
        resume = request.files["resume"]

        original_filename = secure_filename(resume.filename or "")
        extension = Path(original_filename).suffix.lower()
        if not original_filename or extension not in {".pdf", ".txt"}:
            return "Upload a PDF or TXT resume.", 400

        filename = f"{uuid.uuid4().hex}{extension}"
        resume_path = UPLOAD_FOLDER / filename
        resume.save(resume_path)

        resume_text = extract_resume_text(resume_path)
        score = compute_resume_score(resume_text)

        conn = get_db()
        conn.execute("""
            UPDATE candidates SET resume=? WHERE id=?
        """, (filename, session["candidate_id"]))

        conn.execute("""
            INSERT INTO applications
            (candidate_id, job, score, status, applied_date)
            VALUES (?, ?, ?, ?, ?)
        """, (
            session["candidate_id"],
            job,
            score,
            "Pending",
            datetime.now().strftime("%Y-%m-%d")
        ))

        conn.commit()
        conn.close()
        return redirect("/candidate/dashboard")

    return render_template("apply.html")

@app.route("/hr/login", methods=["GET", "POST"])
def hr_login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        if HR_USERNAME and HR_PASSWORD and username == HR_USERNAME and password == HR_PASSWORD:
            session["hr"] = True
            return redirect("/hr/dashboard")

        return "Invalid HR username or password"

    return render_template("hr_login.html")

@app.route("/hr/dashboard")
def hr_dashboard():
    if "hr" not in session:
        return redirect("/hr/login")

    conn = get_db()
    applications = conn.execute("""
        SELECT
            applications.id,
            candidates.name,
            candidates.email,
            candidates.phone,
            candidates.resume,
            applications.job,
            applications.score,
            applications.status,
            applications.applied_date
        FROM applications
        JOIN candidates ON applications.candidate_id = candidates.id
    """).fetchall()
    conn.close()

    return render_template("hr_dashboard.html", applications=applications)

@app.route("/hr/rescore", methods=["POST"])
def rescore_applications():
    if "hr" not in session:
        return redirect("/hr/login")

    conn = get_db()
    applications = conn.execute("""
        SELECT applications.id, candidates.resume
        FROM applications
        JOIN candidates ON applications.candidate_id = candidates.id
    """).fetchall()

    for application in applications:
        resume_name = application["resume"]
        resume_path = UPLOAD_FOLDER / resume_name if resume_name else None
        if resume_path and resume_path.is_file():
            resume_text = extract_resume_text(resume_path)
            score = compute_resume_score(resume_text)
            conn.execute(
                "UPDATE applications SET score=? WHERE id=?",
                (score, application["id"])
            )

    conn.commit()
    conn.close()
    return redirect("/hr/dashboard")

@app.route("/hire/<int:application_id>", methods=["POST"])
def hire_candidate(application_id):
    if "hr" not in session:
        return redirect("/hr/login")

    conn = get_db()
    application = conn.execute("""
        SELECT applications.*, candidates.name, candidates.email
        FROM applications
        JOIN candidates ON applications.candidate_id = candidates.id
        WHERE applications.id=?
    """, (application_id,)).fetchone()

    conn.execute("""
        UPDATE applications SET status='Selected'
        WHERE id=?
    """, (application_id,))
    conn.commit()
    conn.close()

    if application:
        send_selection_email(application["email"], application["name"])

    return redirect("/hr/dashboard")

def send_selection_email(receiver_email, candidate_name):
    sender_email = os.environ.get("SMTP_USERNAME")
    sender_password = os.environ.get("SMTP_PASSWORD")
    sender_name = os.environ.get("SMTP_FROM", sender_email or "")
    smtp_host = os.environ.get("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.environ.get("SMTP_PORT", "587"))

    if not sender_email or not sender_password:
        app.logger.warning("Selection email not sent: SMTP credentials are not configured.")
        return

    try:
        message = EmailMessage()
        message["Subject"] = "Congratulations - You are Selected"
        message["From"] = sender_name
        message["To"] = receiver_email
        message.set_content(f"""
Dear {candidate_name},

Congratulations!

We are happy to inform you that you have been selected for the position.

Our HR team will contact you with further details.

Regards,
HR Department
""")

        with smtplib.SMTP(smtp_host, smtp_port, timeout=20) as server:
            server.starttls()
            server.login(sender_email, sender_password)
            server.send_message(message)

    except (OSError, smtplib.SMTPException) as error:
        app.logger.exception("Selection email could not be sent: %s", error)

@app.route("/resume/<filename>")
def resume(filename):
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)

@app.route("/statistics")
def statistics():
    if "hr" not in session:
        return redirect("/hr/login")

    conn = get_db()

    total = conn.execute("SELECT COUNT(*) FROM candidates").fetchone()[0]
    selected = conn.execute("""
        SELECT COUNT(*) FROM applications WHERE status='Selected'
    """).fetchone()[0]
    pending = conn.execute("""
        SELECT COUNT(*) FROM applications WHERE status='Pending'
    """).fetchone()[0]

    month = datetime.now().strftime("%Y-%m")
    monthly_selected = conn.execute("""
        SELECT COUNT(*) FROM applications
        WHERE status='Selected' AND applied_date LIKE ?
    """, (month + "%",)).fetchone()[0]

    records = conn.execute("""
        SELECT
            candidates.name,
            candidates.email,
            candidates.phone,
            applications.job,
            applications.score,
            applications.status,
            applications.applied_date
        FROM applications
        JOIN candidates ON applications.candidate_id = candidates.id
        ORDER BY applications.applied_date DESC, applications.id DESC
    """).fetchall()

    conn.close()

    return render_template(
        "statistics.html",
        total=total,
        selected=selected,
        pending=pending,
        monthly_selected=monthly_selected,
        records=records
    )

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

create_database()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")), debug=False)
