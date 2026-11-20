from datetime import datetime, timezone
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.main import app
from app.database import engine, get_db
from app.models.identity import Role, User
from app.models.surveys import Survey, SurveyQuestion
from app.models.subscriptions import SubscriptionPlan, UserSubscription
from app.security.dependencies import get_optional_current_user


def test_subscription_tier_access():
    now = datetime.now(timezone.utc)
    connection = engine.connect()
    transaction = connection.begin()

    basic_user = None
    platinum_user = None

    try:
        db = Session(expire_on_commit=False, bind=connection, join_transaction_mode="create_savepoint")

        role = db.scalar(select(Role).where(Role.name == "respondent"))
        platinum_plan = db.scalar(
            select(SubscriptionPlan).where(SubscriptionPlan.code == "platinum")
        )

        assert role is not None, "Respondent role is missing."
        assert platinum_plan is not None, "Platinum plan is missing."

        basic_user = User(
            id=uuid4(), email=f"tier-basic-{uuid4()}@test.invalid",
            full_name="Temporary Basic", password_hash="test-only",
            role_id=role.id, status="active", email_verified_at=now,
        )
        platinum_user = User(
            id=uuid4(), email=f"tier-platinum-{uuid4()}@test.invalid",
            full_name="Temporary Platinum", password_hash="test-only",
            role_id=role.id, status="active", email_verified_at=now,
        )
        db.add_all([basic_user, platinum_user])
        db.flush()

        db.add(UserSubscription(
            user_id=platinum_user.id,
            plan_id=platinum_plan.id,
            status="active",
            starts_at=now,
            ends_at=None,
        ))

        surveys = {}
        for tier in ("basic", "bronze", "platinum"):
            survey = Survey(
                id=uuid4(),
                slug=f"tier-test-{tier}-{uuid4().hex[:8]}",
                title=f"Temporary {tier.title()} Survey",
                required_tier=tier,
                description="PRIVATE DESCRIPTION",
                instructions="PRIVATE INSTRUCTIONS",
                estimated_minutes=5,
                reward_amount=10,
                reward_currency="KES",
                status="published",
                published_at=now,
                participant_count=0,
            )
            db.add(survey)
            db.flush()

            question = SurveyQuestion(
                survey_id=survey.id,
                order_index=0,
                question_type="short_text",
                prompt=f"PRIVATE {tier.upper()} QUESTION",
                is_required=True,
                config={
                    "placeholder": "Your answer",
                    "correct_answer": "PRIVATE_SECRET",
                    "expected_answer": "PRIVATE_EXPECTED",
                    "attention_check": True,
                },
            )
            db.add(question)
            surveys[tier] = survey.id

        db.commit()
        db.close()

        def override_db():
            session = Session(
                bind=connection,
                join_transaction_mode="create_savepoint",
            )
            try:
                yield session
            finally:
                session.close()

        current_user = None

        def override_optional_user():
            return current_user

        app.dependency_overrides[get_db] = override_db
        app.dependency_overrides[get_optional_current_user] = override_optional_user

        client = TestClient(app)

        # Anonymous catalogue
        response = client.get("/api/surveys/")
        assert response.status_code == 200, response.text
        cards = {item["required_tier"]: item for item in response.json()["items"]}

        assert cards["basic"]["is_locked"] is False
        assert cards["bronze"]["is_locked"] is True
        assert cards["platinum"]["is_locked"] is True
        assert "description" not in cards["platinum"]
        assert "instructions" not in cards["platinum"]
        print("PASS: Anonymous catalogue shows cards with correct locks.")

        # Anonymous access
        for tier in ("basic", "bronze", "platinum"):
            sid = surveys[tier]
            detail = client.get(f"/api/surveys/{sid}")
            questions = client.get(f"/api/surveys/{sid}/questions")

            if tier == "basic":
                assert detail.status_code == 200, detail.text
                assert questions.status_code == 200, questions.text

                public_config = questions.json()[0]["config"]
                assert public_config["placeholder"] == "Your answer"
                assert "correct_answer" not in public_config
                assert "expected_answer" not in public_config
                assert "attention_check" not in public_config
            else:
                assert detail.status_code == 403, detail.text
                assert questions.status_code == 403, questions.text
                assert questions.json()["detail"]["code"] == "upgrade_required"

        print("PASS: Anonymous users can access Basic only.")

        # Basic account access
        current_user = basic_user
        response = client.get("/api/surveys/")
        cards = {item["required_tier"]: item for item in response.json()["items"]}
        assert cards["basic"]["is_locked"] is False
        assert cards["bronze"]["is_locked"] is True

        assert client.get(f"/api/surveys/{surveys['basic']}").status_code == 200
        assert client.get(f"/api/surveys/{surveys['bronze']}").status_code == 403
        assert client.get(f"/api/surveys/{surveys['bronze']}/questions").status_code == 403
        print("PASS: Basic respondent is blocked from Bronze and Platinum.")

        # Platinum account access
        current_user = platinum_user
        response = client.get("/api/surveys/")
        cards = {item["required_tier"]: item for item in response.json()["items"]}
        assert all(not item["is_locked"] for item in cards.values())

        for tier in ("basic", "bronze", "platinum"):
            sid = surveys[tier]
            assert client.get(f"/api/surveys/{sid}").status_code == 200
            assert client.get(f"/api/surveys/{sid}/questions").status_code == 200

        print("PASS: Platinum respondent can access all tested tiers.")
        print("\nALL SUBSCRIPTION ACCESS INTEGRATION TESTS PASSED.")

    finally:
        app.dependency_overrides.clear()
        transaction.rollback()
        connection.close()
        print("Temporary database changes rolled back." if transaction.is_active is False else "")
