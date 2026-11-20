"""Seed the SurveyKE question bank with curated Kenyan research questions.

Safe to run repeatedly:
- Existing categories are reused by slug.
- Existing questions are skipped by exact prompt.
- Existing surveys and responses are never modified.
"""

from sqlalchemy import select

from app.database import SessionLocal
from app.models.question_bank import QuestionBankQuestion, QuestionBankTitle
from app.schemas.question_bank import (
    BankOptionCreate,
    BankQuestionCreate,
    BankTitleCreate,
)
from app.services.question_bank import create_bank_question, create_title


CATEGORIES = [
    {
        "title": "Healthcare Access and Patient Experience",
        "slug": "healthcare-access-patient-experience",
        "description": (
            "Experiences accessing outpatient healthcare in Kenya, including "
            "waiting times, medicine availability, costs and service access."
        ),
        "questions": [
            {
                "type": "single_choice",
                "prompt": (
                    "Thinking about your most recent outpatient visit to a "
                    "health facility in the past 12 months, what type of "
                    "facility did you visit?"
                ),
                "options": [
                    "Public dispensary",
                    "Public health centre",
                    "County or sub-county hospital",
                    "National referral hospital",
                    "Private hospital or clinic",
                    "Faith-based health facility",
                    "Other",
                    "I have not visited a health facility in the past 12 months",
                ],
            },
            {
                "type": "single_choice",
                "prompt": (
                    "During that most recent visit, approximately how long "
                    "did you wait between registration and being attended "
                    "to by a healthcare worker?"
                ),
                "options": [
                    "Less than 30 minutes",
                    "30–59 minutes",
                    "1–2 hours",
                    "More than 2 hours",
                    "I was not attended to",
                    "I cannot remember",
                ],
            },
            {
                "type": "single_choice",
                "prompt": (
                    "If a healthcare worker prescribed medicine during your "
                    "most recent visit, how much of the prescribed medicine "
                    "was available at that facility?"
                ),
                "options": [
                    "All of it was available",
                    "Some of it was available",
                    "None of it was available",
                    "No medicine was prescribed",
                    "I cannot remember",
                ],
            },
            {
                "type": "single_choice",
                "prompt": (
                    "What was the main source of payment for your most recent "
                    "outpatient visit?"
                ),
                "options": [
                    "Paid directly out of pocket",
                    "Private health insurance",
                    "Public health coverage",
                    "Employer or organisation paid",
                    "Facility provided the service free of charge",
                    "Another source",
                    "I cannot remember",
                ],
            },
        ],
    },
    {
        "title": "Internet Access and Digital Connectivity",
        "slug": "internet-access-digital-connectivity",
        "description": (
            "Internet access, connection reliability, data affordability "
            "and the practical use of digital services."
        ),
        "questions": [
            {
                "type": "single_choice",
                "prompt": (
                    "What is your main method of accessing the internet "
                    "during a typical week?"
                ),
                "options": [
                    "Mobile data on a smartphone",
                    "Home fixed broadband or fibre",
                    "Wi-Fi at work or school",
                    "Public or shared Wi-Fi",
                    "A mobile hotspot from another person",
                    "I do not access the internet in a typical week",
                    "Another method",
                ],
            },
            {
                "type": "single_choice",
                "prompt": (
                    "During the past 30 days, how often has poor internet "
                    "connectivity prevented you from completing something "
                    "you intended to do online?"
                ),
                "options": [
                    "Never",
                    "Once",
                    "2–3 times",
                    "About once a week",
                    "Several times a week",
                    "Almost every day",
                ],
            },
            {
                "type": "single_choice",
                "prompt": (
                    "Which factor most often limits your ability to use "
                    "the internet when you need it?"
                ),
                "options": [
                    "Cost of data or subscription",
                    "Weak or unavailable network signal",
                    "Electricity or charging difficulties",
                    "Lack of a suitable device",
                    "Limited digital skills",
                    "Lack of relevant online services or content",
                    "No major limitation",
                    "Another factor",
                ],
            },
            {
                "type": "single_choice",
                "prompt": (
                    "Approximately how much does your household or you "
                    "personally spend on internet access in a typical month?"
                ),
                "options": [
                    "Below KES 200",
                    "KES 200–499",
                    "KES 500–999",
                    "KES 1,000–1,999",
                    "KES 2,000–3,999",
                    "KES 4,000 or more",
                    "I do not pay for internet access",
                    "I do not know",
                ],
            },
        ],
    },
    {
        "title": "Mobile Money and Banking Experiences",
        "slug": "mobile-money-banking-experiences",
        "description": (
            "Use of mobile money and banking services, transaction "
            "reliability, payment methods and service difficulties."
        ),
        "questions": [
            {
                "type": "single_choice",
                "prompt": (
                    "Which method do you use most often when sending money "
                    "to another person in Kenya?"
                ),
                "options": [
                    "Mobile money transfer",
                    "Bank-to-bank transfer",
                    "Bank-to-mobile money transfer",
                    "Cash handed directly to the recipient",
                    "Another method",
                    "I do not send money to other people",
                ],
            },
            {
                "type": "single_choice",
                "prompt": (
                    "During the past 30 days, how often has a mobile money "
                    "or digital banking transaction failed, been delayed, "
                    "or remained pending?"
                ),
                "options": [
                    "Never",
                    "Once",
                    "2–3 times",
                    "4–5 times",
                    "More than 5 times",
                    "I did not use these services during this period",
                ],
            },
            {
                "type": "multi_select",
                "prompt": (
                    "Which difficulties have you personally experienced "
                    "when using mobile money or digital banking services "
                    "during the past 12 months? Select all that apply."
                ),
                "options": [
                    "Transaction charges were higher than expected",
                    "Transaction took too long to complete",
                    "Money was sent to the wrong recipient",
                    "Reversal or refund took too long",
                    "Service was temporarily unavailable",
                    "Difficulty accessing customer support",
                    "Suspected fraud or unauthorised activity",
                    "Difficulty using the service",
                    "None of these",
                ],
            },
            {
                "type": "single_choice",
                "prompt": (
                    "When a digital money transaction fails but money is "
                    "deducted, how long does it usually take for the issue "
                    "to be resolved?"
                ),
                "options": [
                    "Within a few minutes",
                    "Within 24 hours",
                    "2–3 days",
                    "4–7 days",
                    "More than 7 days",
                    "The issue has not been resolved",
                    "I have not experienced this",
                ],
            },
        ],
    },
    {
        "title": "Employment and Work Conditions",
        "slug": "employment-work-conditions",
        "description": (
            "Employment status, work patterns, income regularity and "
            "barriers encountered when seeking work in Kenya."
        ),
        "questions": [
            {
                "type": "single_choice",
                "prompt": (
                    "Which of the following best describes your current "
                    "main work situation?"
                ),
                "options": [
                    "Employed full-time",
                    "Employed part-time",
                    "Self-employed or running a business",
                    "Casual or temporary work",
                    "Working in the informal sector",
                    "Unemployed and actively looking for work",
                    "Not currently working and not looking for work",
                    "Student",
                    "Another situation",
                ],
            },
            {
                "type": "single_choice",
                "prompt": (
                    "In a typical week during the past month, approximately "
                    "how many hours did you spend doing paid work or "
                    "income-generating activities?"
                ),
                "options": [
                    "No hours",
                    "1–9 hours",
                    "10–19 hours",
                    "20–29 hours",
                    "30–39 hours",
                    "40–49 hours",
                    "50 hours or more",
                    "My hours vary too much to estimate",
                ],
            },
            {
                "type": "single_choice",
                "prompt": (
                    "How predictable has your income from work been over "
                    "the past three months?"
                ),
                "options": [
                    "Very predictable; I receive roughly the same amount regularly",
                    "Somewhat predictable; amounts vary slightly",
                    "Unpredictable; amounts vary significantly",
                    "I receive income only when work is available",
                    "I have not received work income during this period",
                    "Prefer not to say",
                ],
            },
            {
                "type": "multi_select",
                "prompt": (
                    "If you have looked for paid work during the past "
                    "12 months, which difficulties have you encountered? "
                    "Select all that apply."
                ),
                "options": [
                    "Few suitable vacancies",
                    "Lack of required work experience",
                    "Lack of required qualifications or skills",
                    "Transport costs or distance to workplaces",
                    "Limited access to job information",
                    "Difficulty with application or recruitment processes",
                    "Low pay offered for available jobs",
                    "Unpaid or unclear recruitment requirements",
                    "I have not looked for work during this period",
                    "I did not encounter these difficulties",
                ],
            },
        ],
    },
    {
        "title": "Transport and Daily Mobility",
        "slug": "transport-daily-mobility",
        "description": (
            "Daily travel patterns, journey duration, transport costs "
            "and reliability of common transport options."
        ),
        "questions": [
            {
                "type": "single_choice",
                "prompt": (
                    "What is the main mode of transport you use for your "
                    "most frequent regular journey, such as travelling to "
                    "work, school or a place of business?"
                ),
                "options": [
                    "Walking",
                    "Matatu or minibus",
                    "Bus",
                    "Motorcycle taxi (boda boda)",
                    "Bicycle",
                    "Private car",
                    "Taxi or ride-hailing service",
                    "Train",
                    "Other",
                    "I do not make a regular journey",
                ],
            },
            {
                "type": "single_choice",
                "prompt": (
                    "On a typical day, how long does your one-way regular "
                    "journey take?"
                ),
                "options": [
                    "Less than 15 minutes",
                    "15–29 minutes",
                    "30–59 minutes",
                    "1–2 hours",
                    "More than 2 hours",
                    "My journey time varies considerably",
                    "I do not make a regular journey",
                ],
            },
            {
                "type": "single_choice",
                "prompt": (
                    "During the past 30 days, how often has your regular "
                    "journey taken longer than you expected because of "
                    "traffic, delays or transport availability?"
                ),
                "options": [
                    "Never",
                    "Rarely",
                    "Sometimes",
                    "Often",
                    "Very often",
                    "I do not make a regular journey",
                ],
            },
            {
                "type": "single_choice",
                "prompt": (
                    "Compared with three months ago, how has the amount "
                    "you spend on your regular transport journey changed?"
                ),
                "options": [
                    "Increased significantly",
                    "Increased slightly",
                    "Stayed about the same",
                    "Decreased slightly",
                    "Decreased significantly",
                    "I did not make this journey three months ago",
                    "I do not pay for this journey",
                ],
            },
        ],
    },
    {
        "title": "Household Utilities and Energy",
        "slug": "household-utilities-energy",
        "description": (
            "Household access to electricity, cooking energy, water "
            "supply and interruptions to essential utilities."
        ),
        "questions": [
            {
                "type": "single_choice",
                "prompt": (
                    "What is the main source of energy used for cooking "
                    "in your household?"
                ),
                "options": [
                    "LPG (cooking gas)",
                    "Electricity",
                    "Charcoal",
                    "Firewood",
                    "Kerosene",
                    "Biogas",
                    "Other",
                    "My household does not prepare meals",
                ],
            },
            {
                "type": "single_choice",
                "prompt": (
                    "During the past 30 days, how often has your household "
                    "experienced an electricity interruption lasting "
                    "longer than 30 minutes?"
                ),
                "options": [
                    "Never",
                    "Once",
                    "2–3 times",
                    "About once a week",
                    "Several times a week",
                    "Almost every day",
                    "My household does not have electricity",
                ],
            },
            {
                "type": "single_choice",
                "prompt": (
                    "What is the main source of water your household uses "
                    "for drinking?"
                ),
                "options": [
                    "Piped water into the dwelling",
                    "Communal or shared water tap",
                    "Borehole",
                    "Protected well or spring",
                    "Unprotected well or spring",
                    "Water vendor or water bowser",
                    "Bottled or packaged water",
                    "River, lake or other surface water",
                    "Another source",
                ],
            },
            {
                "type": "single_choice",
                "prompt": (
                    "During the past 30 days, how often has your household "
                    "been unable to access its usual main water source "
                    "when water was needed?"
                ),
                "options": [
                    "Never",
                    "Once",
                    "2–3 times",
                    "About once a week",
                    "Several times a week",
                    "Almost every day",
                    "My household does not have a usual main water source",
                ],
            },
        ],
    },
]


def main():
    db = SessionLocal()
    added_categories = 0
    existing_categories = 0
    added_questions = 0
    skipped_questions = 0

    try:
        for category in CATEGORIES:
            title = db.scalar(
                select(QuestionBankTitle).where(
                    QuestionBankTitle.slug == category["slug"]
                )
            )

            if title is None:
                create_title(
                    db,
                    BankTitleCreate(
                        title=category["title"],
                        slug=category["slug"],
                        description=category["description"],
                    ),
                )
                title = db.scalar(
                    select(QuestionBankTitle).where(
                        QuestionBankTitle.slug == category["slug"]
                    )
                )
                added_categories += 1
                print(f"\n[NEW CATEGORY] {category['title']}")
            else:
                existing_categories += 1
                print(f"\n[EXISTING CATEGORY] {category['title']}")

            existing_prompts = set(
                db.scalars(
                    select(QuestionBankQuestion.prompt).where(
                        QuestionBankQuestion.title_id == title.id
                    )
                ).all()
            )

            for item in category["questions"]:
                if item["prompt"] in existing_prompts:
                    skipped_questions += 1
                    print(f"  [SKIP] {item['prompt'][:85]}...")
                    continue

                options = [
                    BankOptionCreate(label=label, value=label)
                    for label in item.get("options", [])
                ]

                create_bank_question(
                    db,
                    title.id,
                    BankQuestionCreate(
                        question_type=item["type"],
                        prompt=item["prompt"],
                        is_required=False,
                        config={},
                        options=options,
                    ),
                )

                existing_prompts.add(item["prompt"])
                added_questions += 1
                print(f"  [ADDED] {item['prompt'][:85]}...")

        print("\n========== SEED SUMMARY ==========")
        print(f"New categories:       {added_categories}")
        print(f"Existing categories:  {existing_categories}")
        print(f"New questions:        {added_questions}")
        print(f"Skipped questions:    {skipped_questions}")
        print("Question bank seeding completed.")

    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
