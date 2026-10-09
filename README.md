# HR Resume Analyzer

A responsive Flask recruitment website with candidate accounts, resume uploads, HR review, email notifications, automated resume-match estimates, and recruitment statistics. Candidates and HR access it in a browser on a phone or computer; there is no mobile app to install.

## Run Locally

Locally, open the website at `http://127.0.0.1:5000/`. After hosting deployment, users access it through the public HTTPS URL provided by the host.

1. Create and activate a virtual environment:
   - Windows PowerShell: `python -m venv .venv` then `.\.venv\Scripts\Activate.ps1`
   - macOS/Linux: `python3 -m venv .venv` then `source .venv/bin/activate`
2. Install packages: `pip install -r requirements.txt`
3. Copy `.env.example` to `.env` and replace the secret and HR password.
4. Start the app: `python app.py`
5. Open `http://127.0.0.1:5000/`.

The local development HR username/password default to `admin` / `admin123`; replace them in `.env` before sharing the site.

### Test on a phone on the same Wi-Fi

1. Start the website on your computer with `python app.py`.
2. Run `ipconfig` on Windows and find the computer's IPv4 address under the active Wi-Fi adapter.
3. On the phone connected to that same Wi-Fi, open `http://<computer-ipv4-address>:5000/` (replace the placeholder with the address from `ipconfig`).
4. If Windows Firewall asks, allow Python on your private network. Do not expose this development server directly to the public internet; use the Render deployment below for that.

## Deploy Publicly on Render

1. Push this project to a private GitHub repository. Do not commit `.env`, database files, or uploaded resumes.
2. Create a Render account and choose **New > Blueprint**; connect the repository containing `render.yaml`.
3. Set the prompted `HR_USERNAME` and `HR_PASSWORD` values in Render. Use a unique, strong password.
4. Wait for the service to finish building. Render supplies a public HTTPS URL.
5. To send selection emails, set `SMTP_USERNAME` and `SMTP_PASSWORD` in Render. For Gmail, use an app password, not your normal account password.

The Render configuration uses a persistent disk for SQLite and uploaded resumes. The disk requires a paid Render service and is suitable for a small demonstration deployment. For a larger production service, migrate SQLite to managed PostgreSQL and store resumes in private object storage. Existing local database contents and uploaded files are not automatically copied to the hosted service.

## Security and Scoring Notes

- Candidate passwords are hashed; existing plaintext passwords are upgraded after a successful login.
- Production requires a generated `SECRET_KEY`; HR and email credentials are configured as host secrets.
- Resume uploads are limited to PDF/TXT and 8 MB per request.
- Resume scores are keyword-based estimates, not a generative AI decision or a substitute for human review.
- Candidate information and resumes are sensitive. Share the public URL, not uploaded files or database exports.
