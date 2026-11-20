"""Seed survey categories (idempotent)."""

from app.database import SessionLocal
from app.models.surveys import SurveyCategory
from sqlalchemy import select

CATEGORIES = [
    ("Energy & Utilities", "energy-utilities"),
    ("Telecommunications", "telecommunications"),
    ("Banking & Finance", "banking-finance"),
    ("Shopping & Retail", "shopping-retail"),
    ("Healthcare", "healthcare"),
    ("Transport", "transport"),
    ("Education", "education"),
    ("Employment", "employment"),
    ("Technology", "technology"),
    ("Agriculture", "agriculture"),
    ("Food & Lifestyle", "food-lifestyle"),
    ("Environment", "environment"),
    ("Entertainment", "entertainment"),
    ("Housing", "housing"),
    ("Public Services", "public-services"),
    ("Other Research", "other-research"),
]

def main():
    db = SessionLocal()
    added = skipped = 0
    try:
        for i, (name, slug) in enumerate(CATEGORIES):
            if db.scalar(select(SurveyCategory).where(SurveyCategory.slug == slug)):
                skipped += 1
                continue
            db.add(SurveyCategory(name=name, slug=slug, sort_order=i))
            added += 1
        db.commit()
        print(f"Added: {added}, Skipped: {skipped}")
    finally:
        db.close()

if __name__ == "__main__":
    main()
