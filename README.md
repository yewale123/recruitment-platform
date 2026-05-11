# AI-Powered Recruitment Automation Platform

An end-to-end recruitment tool that automates candidate sourcing from LinkedIn, scores them using an AI ranking algorithm, and sends personalized email outreach — reducing recruiting time from **5 hours to 15 minutes**.

---

## Features

- **LinkedIn Scraping** — Automated profile extraction using Playwright browser automation
- **Smart Search Queries** — Rule-based query generation with title synonyms and seniority detection
- **Location Filter** — City-level filtering using LinkedIn geoUrn for 30+ cities
- **Candidate Scoring** — 100-point ranking algorithm (skills, experience, location, keywords)
- **Async Processing** — Celery task queue for non-blocking background scraping
- **Real-time Status** — Live progress updates with auto-refresh every 5 seconds
- **Email Discovery** — Automated email finding via Hunter.io API
- **Email Outreach** — Personalized automated emails via SendGrid
- **Delete & Manage** — Full CRUD for recruitment requests

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python, FastAPI, SQLAlchemy |
| Frontend | React.js, Vite |
| Database | MySQL |
| Task Queue | Celery |
| Scraping | Playwright (Browser Automation) |
| Email Find | Hunter.io API |
| Email Send | SendGrid API |

---

## Project Structure

```
recruitment-platform/
├── backend/
│   ├── app/
│   │   ├── api/          # FastAPI route handlers
│   │   ├── connectors/   # LinkedIn, Naukri, Indeed scrapers
│   │   ├── models/       # SQLAlchemy database models
│   │   ├── schemas/      # Pydantic request/response schemas
│   │   ├── services/     # Business logic (ranking, AI queries)
│   │   └── tasks/        # Celery async tasks
│   ├── scripts/          # Login scripts for each platform
│   ├── requirements.txt
│   └── .env.example
└── frontend/
    └── src/
        ├── components/   # Reusable UI components
        ├── pages/        # Route pages
        ├── hooks/        # Custom React hooks
        └── api/          # API client
```

---

## Setup & Installation

### Prerequisites
- Python 3.11+
- Node.js 18+
- MySQL 8+

### Backend Setup
```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# Fill in your values in .env
python init_db.py
playwright install chromium
```

### Frontend Setup
```bash
cd frontend
npm install
```

---

## Running the Project

Open **3 terminals** and run each command:

```bash
# Terminal 1 — Backend API
cd backend
.\start_api.bat

# Terminal 2 — Celery Worker
cd backend
.\start_worker.bat

# Terminal 3 — Frontend
cd frontend
.\start_frontend.bat
```

Open browser at **http://localhost:5173**

---

## First Time LinkedIn Setup

```bash
cd backend
.venv\Scripts\activate
python scripts/linkedin_login.py
```

A browser opens → log in to LinkedIn → press Enter to save session.

---

## How It Works

```
HR fills request form (title, skills, experience, location)
        ↓
Smart query builder generates 3 targeted LinkedIn search queries
        ↓
Playwright scrapes matching profiles (runs in background)
        ↓
Candidates scored out of 100 and ranked
        ↓
Hunter.io finds professional emails
        ↓
SendGrid sends personalized outreach emails
        ↓
HR sees ranked candidates with email status
```

---

## Candidate Scoring Algorithm

| Factor | Weight |
|---|---|
| Skills Match | 40 points |
| Experience | 25 points |
| Location | 20 points |
| Keywords | 15 points |
| **Total** | **100 points** |

---

## Environment Variables

Copy `backend/.env.example` to `backend/.env` and fill in:

```env
DB_HOST=localhost
DB_USER=root
DB_PASSWORD=your_password
DB_NAME=recruitment_platform
GEMINI_API_KEY=optional
HUNTER_API_KEY=your_hunter_key
SENDGRID_API_KEY=your_sendgrid_key
```

---

## Impact

| Task | Manual Time | Platform Time |
|---|---|---|
| Search LinkedIn | 2–3 hours | 2–3 minutes |
| Score candidates | 1 hour | Instant |
| Find emails | 30–60 min | Automated |
| Send outreach | 30 min | One click |
| **Total** | **5–8 hours** | **15 minutes** |
