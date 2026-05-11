# AI-Powered Recruitment Automation Platform

Automates LinkedIn candidate sourcing, scoring and email outreach — reducing recruiting time from **5 hours to 15 minutes**.

---

## Tech Stack
- **Backend:** Python, FastAPI, SQLAlchemy, Celery
- **Frontend:** React.js, Vite
- **Database:** MySQL
- **Scraping:** Playwright (Browser Automation)
- **APIs:** Playwright Browser Automation

---

## Features
- LinkedIn profile scraping with location filter
- Smart search query generation with synonyms + seniority
- 100-point candidate ranking algorithm
- Real-time scraping status with Celery async tasks

---

## Setup

```bash
# Backend
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
python init_db.py
playwright install chromium

# Frontend
cd frontend
npm install
```

---

## Run

```bash
# Terminal 1 — API
cd backend && .\start_api.bat

# Terminal 2 — Worker
cd backend && .\start_worker.bat

# Terminal 3 — Frontend
cd frontend && .\start_frontend.bat
```

Open **http://localhost:5173**

---

## First Time LinkedIn Setup

```bash
cd backend
python scripts/linkedin_login.py
```

Log in to LinkedIn in the browser → press Enter to save session.
