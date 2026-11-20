"""Public survey-category listing."""

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.surveys import SurveyCategory

router = APIRouter(prefix="/api/categories", tags=["categories"])


@router.get("/")
def list_categories(db: Session = Depends(get_db)):
    rows = db.scalars(
        select(SurveyCategory).order_by(SurveyCategory.sort_order, SurveyCategory.name)
    ).all()
    return [
        {"id": str(c.id), "slug": c.slug, "name": c.name, "description": c.description}
        for c in rows
    ]
