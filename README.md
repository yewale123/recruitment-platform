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

