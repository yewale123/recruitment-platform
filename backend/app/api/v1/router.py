from fastapi import APIRouter
from app.api.v1 import requests, candidates

router = APIRouter(prefix="/api/v1")
router.include_router(requests.router)
router.include_router(candidates.router)
