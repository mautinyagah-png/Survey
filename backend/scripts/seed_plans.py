"""Seed subscription plans (idempotent).

Pricing (monthly, KES) — equal 250-gap so upgrading feels cheap:
  Basic    0     (free)
  Bronze   250
  Silver   500
  Gold     750
  Platinum 1000
"""

from decimal import Decimal

from sqlalchemy import select

from app.database import SessionLocal
from app.models.subscriptions import SubscriptionPlan

PLANS = [
    ("basic",    "Basic",    1, Decimal("0"),    "Unlock the platform. Access to Basic-tier surveys."),
    ("bronze",   "Bronze",   2, Decimal("250"),  "All Basic surveys, plus Bronze-tier surveys."),
    ("silver",   "Silver",   3, Decimal("500"),  "All Bronze features, plus Silver-tier surveys."),
    ("gold",     "Gold",     4, Decimal("750"),  "All Silver features, plus Gold-tier surveys."),
    ("platinum", "Platinum", 5, Decimal("1000"), "Every survey, every tier, no restrictions."),
]


def main():
    db = SessionLocal()
    added = updated = 0
    try:
        for code, name, rank, price, _desc in PLANS:
            existing = db.scalar(select(SubscriptionPlan).where(SubscriptionPlan.code == code))
            if existing:
                existing.name = name
                existing.tier_rank = rank
                existing.price_amount = price
                existing.currency = "KES"
                existing.billing_period = "monthly"
                existing.is_active = True
                updated += 1
            else:
                db.add(SubscriptionPlan(
                    code=code, name=name, tier_rank=rank,
                    price_amount=price, currency="KES",
                    billing_period="monthly", is_active=True,
                ))
                added += 1
        db.commit()
        print(f"Plans — added: {added}, updated: {updated}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
