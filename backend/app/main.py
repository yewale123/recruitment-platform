from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.api.v1.router import router as v1_router

settings = get_settings()

app = FastAPI(
    title="Recruitment Platform API",
    description="Async candidate sourcing and ranking platform",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(v1_router)


@app.get("/api/v1/health", tags=["Health"])
def health():
    from app.database import engine
    import sqlalchemy
    try:
        with engine.connect() as conn:
            conn.execute(sqlalchemy.text("SELECT 1"))
        db_status = "ok"
    except Exception as e:
        db_status = f"error: {e}"

    return {"status": "ok", "db": db_status}
