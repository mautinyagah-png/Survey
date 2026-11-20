"""Seed 20 survey titles (batch 1 of 5) with ~12 questions each.

Idempotent: skips titles by slug, skips questions by exact prompt.
"""

from sqlalchemy import select
from app.database import SessionLocal
from app.models.question_bank import QuestionBankQuestion, QuestionBankTitle
from app.schemas.question_bank import BankOptionCreate, BankQuestionCreate, BankTitleCreate
from app.services.question_bank import create_bank_question, create_title

TYPE_MAP = {"sc":"single_choice","ms":"multi_select","yn":"yes_no","r":"rating","st":"short_text","lt":"long_text","d":"date","dr":"dropdown"}

BATCH = [
    {"title":"Healthcare Access - Public vs Private","slug":"hc-public-private","description":"Public and private healthcare experiences in Kenya.",
     "qs":[
       ("sc","In the past 12 months, which health facility type have you used most often?",["Public dispensary","Public health centre","County hospital","National referral hospital","Private clinic","Private hospital","Faith-based facility","No facility in past year"]),
       ("sc","What is the main reason you chose that facility type?",["Affordability","Proximity to home","Quality of care","Recommendation from others","Availability of specific service","No other option nearby"]),
       ("sc","Approximately how long did you wait before being attended to on your last visit?",["Under 30 min","30-59 min","1-2 hours","Over 2 hours","Not attended"]),
       ("r","How satisfied were you with the care you received on your last visit?",None),
       ("yn","Were all prescribed medicines available at the facility?",None),
       ("sc","How was your last outpatient visit paid for?",["Out of pocket","NHIF/SHA","Private insurance","Employer covered","Free service"]),
       ("ms","Challenges faced accessing healthcare in the past year? Select all that apply.",["Long waits","High costs","Medicine shortages","Distance","Unfriendly staff","Lack of specialists","None of these"]),
       ("r","Rate the overall quality of public healthcare in your area",None),
       ("yn","Would you recommend your main facility to a family member?",None),
       ("sc","For a routine checkup, would you prefer:",["Public facility","Private facility","Faith-based","No preference"]),
       ("st","What is the single most important improvement you want in local healthcare?",None),
       ("st","Describe one positive healthcare experience you have had in Kenya.",None),
     ]},
    {"title":"Maternal Health Experiences","slug":"maternal-health","description":"Pregnancy, delivery, and postnatal experiences.",
     "qs":[
       ("sc","Have you or your partner given birth in the past 5 years?",["Yes, in past 12 months","Yes, 1-3 years ago","Yes, 3-5 years ago","No"]),
       ("sc","Where was the most recent delivery?",["Public hospital","Private hospital","Faith-based facility","Home with midwife","Home without help","Health centre"]),
       ("sc","How many antenatal visits were attended during your most recent pregnancy?",["0","1-2","3-4","5-6","7+"]),
       ("r","Rate the quality of antenatal care you received",None),
       ("ms","Challenges experienced during pregnancy or delivery? Select all that apply.",["Transport to facility","Cost","Lack of skilled staff","Complications","Poor communication","None of these"]),
       ("yn","Did you receive all recommended postnatal checkups?",None),
       ("sc","Who assisted with the most recent delivery?",["Doctor","Nurse/midwife","Traditional birth attendant","Family member","No one"]),
       ("r","How supported did you feel by health workers during delivery?",None),
       ("sc","How was delivery paid for?",["NHIF/SHA","Out of pocket","Private insurance","Free","Other"]),
       ("yn","Were you given information about family planning after delivery?",None),
       ("st","What support would have helped you most during pregnancy?",None),
       ("st","Describe any challenge you faced accessing maternal care.",None),
     ]},
    {"title":"Child Healthcare & Vaccination","slug":"child-healthcare","description":"Child health, immunisation, and paediatric care.",
     "qs":[
       ("sc","How many children under 18 live in your household?",["0","1","2","3","4+"]),
       ("yn","Are all children in your household fully vaccinated per the national schedule?",None),
       ("sc","Where do you usually take children for routine health checks?",["Public clinic","Private clinic","County hospital","Faith-based","Pharmacy only","Do not take them"]),
       ("r","Rate the availability of child vaccines at your usual facility",None),
       ("sc","How far is your usual child healthcare facility from home?",["Under 1 km","1-3 km","3-5 km","5-10 km","Over 10 km"]),
       ("ms","Which child health concerns worry you most? Select all that apply.",["Malaria","Respiratory infections","Malnutrition","Diarrhoeal disease","Vaccine-preventable diseases","Injuries","None"]),
       ("yn","Have any of your children missed a scheduled vaccine in the past year?",None),
       ("r","Rate how respectful health workers are towards your children",None),
       ("sc","Do you use any traditional remedies for child illness?",["Never","Rarely","Sometimes","Often","Always"]),
       ("yn","Do you know where to seek emergency child care after hours?",None),
       ("st","What child health service would you most like improved locally?",None),
       ("st","Describe a recent child healthcare experience.",None),
     ]},
    {"title":"Mental Health Awareness & Stigma","slug":"mental-health-awareness","description":"Mental health awareness, attitudes, and access to support.",
     "qs":[
       ("sc","How would you rate your current mental wellbeing?",["Very good","Good","Fair","Poor","Very poor"]),
       ("yn","Do you believe mental health is as important as physical health?",None),
       ("sc","If you needed help with a mental health concern, where would you seek it?",["Family/friends","Religious leader","Hospital","Private counsellor","Helpline","Would not seek help"]),
       ("r","How comfortable would you be discussing mental health with a health worker?",None),
       ("ms","Which mental health topics do you think are most stigmatised in Kenya? Select all that apply.",["Depression","Anxiety","Suicidal thoughts","Substance abuse","Bipolar disorder","PTSD","None"]),
       ("sc","Have you ever accessed mental health services?",["Yes, currently","Yes, in the past","No, never","Prefer not to say"]),
       ("r","How aware are you of available mental health services in your area?",None),
       ("yn","Would you encourage a family member to see a mental health professional?",None),
       ("sc","What is the biggest barrier to seeking mental health help in your community?",["Cost","Stigma","Lack of services","Lack of awareness","Distance","Fear of being judged"]),
       ("yn","Do you think schools should teach mental health awareness?",None),
       ("st","What would make you more likely to seek mental health support?",None),
       ("st","How can communities reduce mental health stigma?",None),
     ]},
    {"title":"Chronic Disease Management","slug":"chronic-disease","description":"Living with long-term conditions like diabetes, hypertension, asthma.",
     "qs":[
       ("sc","Do you or a household member live with a chronic condition?",["Yes, myself","Yes, household member","No","Prefer not to say"]),
       ("ms","Which chronic conditions affect your household? Select all that apply.",["Diabetes","Hypertension","Asthma","Heart disease","Kidney disease","Cancer","HIV","None"]),
       ("sc","How often do you collect prescription medicines for the condition?",["Weekly","Monthly","Every 3 months","Less often","When needed"]),
       ("r","Rate how consistently medicines are available at your facility",None),
       ("yn","Have you ever missed a dose because medicine was unavailable or unaffordable?",None),
       ("sc","Approximately what is the monthly cost of managing the condition?",["Under KES 500","KES 500-2000","KES 2000-5000","Over KES 5000","Nothing"]),
       ("r","How well is your condition controlled currently?",None),
       ("sc","Who usually manages your condition?",["Hospital specialist","General doctor","Clinical officer","Nurse","Pharmacy","Self-managed"]),
       ("yn","Have you received any health education about your condition in the past year?",None),
       ("ms","Which aspects of care are hardest to manage? Select all that apply.",["Medicine costs","Regular checkups","Diet changes","Physical activity","Emotional stress","None"]),
       ("st","What would most improve your experience managing a chronic condition?",None),
       ("st","Describe a challenge you have faced in managing chronic care costs.",None),
     ]},
    {"title":"Mobile Money Usage & Trust","slug":"mobile-money-trust","description":"M-Pesa, Airtel Money usage, reliability and trust.",
     "qs":[
       ("sc","Which mobile money service do you use most?",["M-Pesa","Airtel Money","T-Kash","None","Multiple equally"]),
       ("sc","How often do you use mobile money in a typical week?",["Daily","Several times a week","Weekly","Monthly","Rarely","Never"]),
       ("ms","What do you use mobile money for? Select all that apply.",["Sending money to family","Paying bills","Buying airtime","Shopping online","Paying for transport","Receiving salary","Savings","Loans"]),
       ("r","How much do you trust mobile money services?",None),
       ("yn","Have you experienced a failed transaction with money deducted in the past 6 months?",None),
       ("sc","If a transaction failed, how long did resolution usually take?",["Under an hour","Within 24 hours","2-3 days","4-7 days","Over a week","Never resolved","Never happened"]),
       ("ms","Which mobile money concerns worry you most? Select all that apply.",["Fraud","Wrong recipient","Failed reversals","Service downtime","High fees","SIM swap fraud","None"]),
       ("r","Rate mobile money service reliability in your experience",None),
       ("sc","Do you keep any savings in mobile money wallets?",["Yes, most savings","Yes, some","No, only for transactions","Do not use wallets"]),
       ("yn","Do you feel mobile money fees are fair?",None),
       ("st","What single change would improve mobile money for you?",None),
       ("st","Describe a mobile money fraud or scam attempt you have encountered.",None),
     ]},
    {"title":"Banking Access & Savings","slug":"banking-savings","description":"Bank accounts, savings habits, and financial access.",
     "qs":[
       ("sc","Do you currently have a bank account?",["Yes, actively used","Yes, rarely used","No, never had","No, closed it"]),
       ("sc","What is your main form of savings?",["Bank account","Mobile wallet","SACCO","Chama/group","Cash at home","Investments","No savings"]),
       ("sc","Approximately how much do you save in a typical month?",["Nothing","Under KES 500","KES 500-2000","KES 2000-5000","KES 5000-10000","Over KES 10000"]),
       ("r","How confident are you about your financial future?",None),
       ("yn","Have you been denied a bank loan in the past 3 years?",None),
       ("sc","How far is your nearest bank branch or agent?",["Under 1 km","1-3 km","3-5 km","5-10 km","Over 10 km","Do not know"]),
       ("ms","What prevents you from saving more? Select all that apply.",["Low income","High expenses","Family obligations","No discipline","Lack of safe option","Emergency spending","Nothing"]),
       ("r","Rate how easy it is to open a bank account in Kenya",None),
       ("sc","Do you use any digital banking app?",["Yes, daily","Yes, occasionally","No, but interested","No, not interested"]),
       ("yn","Would you trust a fully digital bank with no physical branches?",None),
       ("st","What would help you save more effectively?",None),
       ("st","Describe a bad experience you have had with a bank in Kenya.",None),
     ]},
    {"title":"Insurance Coverage in Kenya","slug":"insurance-coverage","description":"Health, life, motor, and other insurance experiences.",
     "qs":[
       ("sc","Do you currently have any insurance cover?",["Health only","Life only","Motor only","Multiple types","None"]),
       ("sc","If you have health insurance, what type?",["NHIF/SHA","Private insurance","Employer scheme","Community-based","None"]),
       ("r","How well does your cover meet your healthcare needs?",None),
       ("yn","Have you ever had a claim rejected?",None),
       ("ms","Why do you not have (more) insurance? Select all that apply.",["Too expensive","Do not trust insurers","Do not understand policies","Employer doesn't provide","No need perceived","Have cover"]),
       ("sc","Approximately how much do you pay for insurance monthly?",["Nothing","Under KES 500","KES 500-2000","KES 2000-5000","Over KES 5000"]),
       ("r","Rate how easy it was to understand your policy terms",None),
       ("yn","Do you feel confident you would receive a payout if you claimed?",None),
       ("sc","If you could add one insurance type tomorrow, which would it be?",["Health","Life","Motor","Home","Business","None"]),
       ("yn","Do you know how to file an insurance claim?",None),
       ("st","What would make insurance more attractive to you?",None),
       ("st","Describe any insurance claim experience you have had.",None),
     ]},
    {"title":"SACCOs and Credit Access","slug":"saccos-credit","description":"SACCO membership, loans, and credit access in Kenya.",
     "qs":[
       ("sc","Are you a member of a SACCO?",["Yes, active","Yes, inactive","No, previously","No, never"]),
       ("sc","If yes, how long have you been a member?",["Under 1 year","1-3 years","3-5 years","Over 5 years","Not a member"]),
       ("ms","What do you use SACCO services for? Select all that apply.",["Savings","Loans","Dividends","Emergency fund","Land purchase","Business capital","Not a member"]),
       ("r","Rate your satisfaction with your SACCO",None),
       ("yn","Have you ever taken a SACCO loan?",None),
       ("sc","Approximately how long does loan approval take at your SACCO?",["Same day","2-3 days","1 week","2-4 weeks","Over a month","Never applied"]),
       ("ms","Challenges with SACCO services? Select all that apply.",["Delayed loans","High interest","Poor customer service","Limited branch access","Strict guarantor rules","None"]),
       ("r","How easy is it to access credit where you live?",None),
       ("sc","What is your main source of emergency funds?",["SACCO","Mobile loan app","Family","Bank loan","Chama","No source"]),
       ("yn","Would you recommend SACCO membership to a friend?",None),
       ("st","What would improve SACCO services for members?",None),
       ("st","Describe a positive SACCO experience you have had.",None),
     ]},
    {"title":"Digital Lending & Borrowing","slug":"digital-lending","description":"Mobile loan apps, interest rates, and borrowing habits.",
     "qs":[
       ("sc","Have you used a digital loan app in the past 12 months?",["Yes, currently","Yes, previously","No"]),
       ("ms","Which digital lenders have you used? Select all that apply.",["Fuliza","M-Shwari","KCB M-Pesa","Tala","Branch","OKash","Other","None"]),
       ("sc","What do you usually use digital loans for?",["Daily expenses","Emergency","Business","School fees","Rent","Other","Do not borrow"]),
       ("r","How fair are digital loan interest rates?",None),
       ("yn","Have you ever been listed by CRB due to a digital loan?",None),
       ("sc","How quickly do you typically repay a digital loan?",["Same day","Within a week","1-2 weeks","1 month","Over a month","Not repaid"]),
       ("ms","Concerns about digital lenders? Select all that apply.",["High interest","Harassment","Data privacy","Hidden fees","CRB listing","None"]),
       ("r","Rate how easy it is to apply for a digital loan",None),
       ("sc","How much do you typically borrow per loan?",["Under KES 500","KES 500-2000","KES 2000-10000","Over KES 10000","Do not borrow"]),
       ("yn","Do you feel informed about the terms before borrowing?",None),
       ("st","What regulation would you want on digital lenders?",None),
       ("st","Describe a challenging experience with a digital lender.",None),
     ]},
    {"title":"Formal Employment Conditions","slug":"formal-employment","description":"Salaried work, contracts, benefits, and workplace.",
     "qs":[
       ("sc","What type of employer do you currently work for?",["Government","Private company","NGO","Self-employed","Casual/informal","Unemployed"]),
       ("sc","What is your current work contract?",["Permanent","Fixed term","Casual","Consultancy","No contract"]),
       ("yn","Does your employer provide NHIF/SHA cover?",None),
       ("yn","Does your employer contribute to NSSF?",None),
       ("r","How satisfied are you with your current job?",None),
       ("sc","Approximately how many hours do you work in a typical week?",["Under 20","20-39","40-49","50-59","60+"]),
       ("ms","Which workplace benefits do you receive? Select all that apply.",["Paid leave","Medical cover","Pension","Housing allowance","Transport allowance","Lunch","None"]),
       ("r","How fairly are you paid for your work?",None),
       ("sc","In the past 12 months, have you experienced salary delays?",["Never","Once","A few times","Frequently","Always late"]),
       ("yn","Do you feel safe raising concerns with your employer?",None),
       ("st","What is the most important workplace change you would want?",None),
       ("st","Describe a positive or negative employer experience.",None),
     ]},
    {"title":"Gig Economy & Side Hustles","slug":"gig-economy","description":"Freelance, delivery, ride-hailing, and side income.",
     "qs":[
       ("sc","Do you currently earn income from gig or freelance work?",["Yes, main income","Yes, side income","No, but interested","No"]),
       ("ms","Which gig activities do you do? Select all that apply.",["Ride-hailing","Delivery","Freelance writing/design","Home services","Online tutoring","Reselling","Not applicable"]),
       ("sc","Approximately how many hours per week do you spend on gigs?",["Under 5","5-10","11-20","21-30","Over 30","Not applicable"]),
       ("r","How satisfied are you with gig earnings?",None),
       ("yn","Do you have any written agreement with gig platforms?",None),
       ("ms","Challenges with gig work? Select all that apply.",["Unstable income","No benefits","High platform fees","Long hours","Safety concerns","Payment delays","None"]),
       ("sc","What is your main gig platform?",["Bolt","Uber","Glovo","Upwork","Fiverr","Facebook Marketplace","Other","None"]),
       ("r","How easy is it to find gig work when you want it?",None),
       ("yn","Would you recommend gig work as a full-time income?",None),
       ("sc","Approximately what percentage of your monthly income comes from gigs?",["Under 25%","25-50%","51-75%","Over 75%","Not applicable"]),
       ("st","What would improve gig work in Kenya?",None),
       ("st","Describe a typical day doing gig work.",None),
     ]},
    {"title":"Unemployment & Job Seeking","slug":"unemployment-job-seeking","description":"Job search experiences, barriers, and expectations.",
     "qs":[
       ("sc","What is your current employment status?",["Employed full-time","Employed part-time","Self-employed","Unemployed, seeking","Unemployed, not seeking","Student"]),
       ("sc","If unemployed, how long have you been seeking work?",["Under 3 months","3-6 months","6-12 months","1-2 years","Over 2 years","Not applicable"]),
       ("ms","Where do you look for jobs? Select all that apply.",["BrighterMonday","LinkedIn","Fuzu","Referrals","Newspapers","Social media","Not looking"]),
       ("r","How optimistic are you about finding work in the next 6 months?",None),
       ("ms","Biggest barriers to employment? Select all that apply.",["Lack of experience","Lack of qualifications","Few openings","Transport costs","Nepotism","Age","Location","None"]),
       ("sc","How many job applications have you submitted in the past month?",["0","1-5","6-15","16-30","Over 30","Not looking"]),
       ("yn","Have you ever paid for a job opportunity?",None),
       ("sc","What monthly salary would you accept for a suitable role?",["Under KES 20000","KES 20000-40000","KES 40000-70000","KES 70000-100000","Over KES 100000"]),
       ("r","How useful are online job platforms?",None),
       ("yn","Would you relocate to another county for work?",None),
       ("st","What kind of support would most help unemployed youth?",None),
       ("st","Describe your most frustrating job-search experience.",None),
     ]},
    {"title":"Online Shopping Behavior","slug":"online-shopping","description":"E-commerce habits, trust, and delivery experiences.",
     "qs":[
       ("sc","How often do you shop online?",["Weekly","Monthly","A few times a year","Rarely","Never"]),
       ("ms","What do you buy online? Select all that apply.",["Clothing","Electronics","Food delivery","Groceries","Cosmetics","Household items","None"]),
       ("ms","Which platforms do you use? Select all that apply.",["Jumia","Kilimall","Jiji","Facebook Marketplace","Instagram shops","WhatsApp sellers","Other","None"]),
       ("sc","How do you usually pay for online purchases?",["M-Pesa","Card","Cash on delivery","Bank transfer","PayPal"]),
       ("r","How much do you trust online sellers?",None),
       ("yn","Have you received a wrong or damaged item?",None),
       ("sc","How satisfied are you with typical delivery speed?",["Very satisfied","Satisfied","Neutral","Dissatisfied","Very dissatisfied"]),
       ("ms","Barriers to online shopping? Select all that apply.",["Delivery costs","Distrust","Fake products","No card","Prefer physical stores","None"]),
       ("sc","Typical amount you spend per online order?",["Under KES 500","KES 500-2000","KES 2000-5000","Over KES 5000"]),
       ("yn","Would you shop online from a new local seller?",None),
       ("st","What would make online shopping safer for you?",None),
       ("st","Describe your best or worst online shopping experience.",None),
     ]},
    {"title":"Food & Grocery Preferences","slug":"food-grocery","description":"Shopping habits, food choices, and dietary preferences.",
     "qs":[
       ("sc","How often does your household shop for groceries?",["Daily","Several times a week","Weekly","Biweekly","Monthly"]),
       ("sc","Where do you usually buy food?",["Local market","Supermarket","Duka/shop","Wholesale","Online","Mixed"]),
       ("sc","Approximately what is your monthly food spend?",["Under KES 5000","KES 5000-10000","KES 10000-20000","KES 20000-40000","Over KES 40000"]),
       ("ms","Which food concerns matter most to you? Select all that apply.",["Price","Freshness","Food safety","Nutrition","Convenience","None"]),
       ("r","How affordable is your usual food basket?",None),
       ("yn","Do you compare prices across shops before buying?",None),
       ("sc","How often do you eat restaurant or takeaway food?",["Daily","Several times a week","Weekly","Rarely","Never"]),
       ("ms","Which diets do you follow? Select all that apply.",["No special diet","Vegetarian","Vegan","Halal","Low-carb","Gluten-free","Other"]),
       ("r","How important is organic or locally-sourced food to you?",None),
       ("yn","Do you grow any of your own food?",None),
       ("st","What single change would improve your food shopping experience?",None),
       ("st","Describe how food prices have affected your household in the past year.",None),
     ]},
    {"title":"Beauty & Personal Care","slug":"beauty-personal-care","description":"Skincare, cosmetics, grooming, and spending patterns.",
     "qs":[
       ("sc","How much do you spend on personal care products monthly?",["Under KES 500","KES 500-1500","KES 1500-3000","KES 3000-5000","Over KES 5000"]),
       ("ms","Which personal care categories do you buy most? Select all that apply.",["Skincare","Hair care","Makeup","Fragrance","Body care","Oral care","Grooming"]),
       ("sc","Where do you usually buy personal care products?",["Supermarket","Pharmacy","Beauty shop","Online","Market","Mixed"]),
       ("r","How important is brand in your buying decisions?",None),
       ("yn","Do you check product ingredients before buying?",None),
       ("sc","How would you describe your skin type?",["Oily","Dry","Combination","Sensitive","Normal","Not sure"]),
       ("ms","What matters most when choosing a product? Select all that apply.",["Price","Brand","Ingredients","Recommendation","Packaging","Reviews","None"]),
       ("yn","Have you ever had a bad reaction to a product?",None),
       ("sc","How often do you visit a salon or barber?",["Weekly","Biweekly","Monthly","Rarely","Never"]),
       ("r","How well are personal care products available in your area?",None),
       ("st","What personal care product do you wish was more affordable?",None),
       ("st","Describe a great or poor product experience you have had.",None),
     ]},
    {"title":"Housing & Rent","slug":"housing-rent","description":"Rent, home ownership, and housing conditions.",
     "qs":[
       ("sc","What is your housing situation?",["Own home","Rent","Live with family","Employer-provided","Other"]),
       ("sc","Approximately what is your monthly rent?",["Under KES 5000","KES 5000-10000","KES 10000-20000","KES 20000-40000","Over KES 40000","Not applicable"]),
       ("sc","What type of housing do you live in?",["Standalone house","Apartment","Bedsitter","Single room","Shared house","Other"]),
       ("r","How satisfied are you with your current housing?",None),
       ("ms","Housing challenges in your area? Select all that apply.",["High rent","Water shortage","Power outages","Security","Poor roads","Overcrowding","None"]),
       ("yn","Have you ever faced unfair eviction or landlord issues?",None),
       ("sc","How far is your home from public transport?",["Under 5 min walk","5-15 min","15-30 min","Over 30 min"]),
       ("yn","Do you have a written tenancy agreement?",None),
       ("r","How safe do you feel in your neighbourhood at night?",None),
       ("sc","Approximately what percentage of income goes to rent?",["Under 20%","20-30%","31-40%","41-50%","Over 50%"]),
       ("st","What would most improve housing in your area?",None),
       ("st","Describe your experience finding or renting a home.",None),
     ]},
    {"title":"Transport & Mobility","slug":"transport-mobility","description":"Daily travel, costs, and transport reliability.",
     "qs":[
       ("sc","What is your main mode of transport for regular journeys?",["Matatu","Bus","Boda boda","Private car","Taxi/ride-hailing","Walking","Train","Bicycle"]),
       ("sc","How long does your one-way regular journey take?",["Under 15 min","15-30 min","30-60 min","1-2 hours","Over 2 hours"]),
       ("sc","Approximately what do you spend on transport per day?",["Under KES 100","KES 100-300","KES 300-500","Over KES 500"]),
       ("r","How reliable is your usual transport mode?",None),
       ("ms","Transport challenges in your area? Select all that apply.",["Traffic jams","High fares","Unsafe driving","Overcrowding","Poor roads","Harassment","None"]),
       ("yn","Do you feel safe using public transport at night?",None),
       ("sc","How has your transport fare changed in the past 6 months?",["Increased a lot","Increased slightly","Same","Decreased","Not sure"]),
       ("r","How satisfied are you with the availability of transport where you live?",None),
       ("yn","Have you ever been in a transport accident?",None),
       ("sc","If cost were not a factor, which mode would you prefer?",["Private car","Ride-hailing","Matatu","Bus","Train","Bicycle"]),
       ("st","What single change would most improve your daily commute?",None),
       ("st","Describe a memorable transport experience in Kenya.",None),
     ]},
]

def main():
    db = SessionLocal()
    t_add = t_skip = q_add = q_skip = 0
    try:
        for entry in BATCH:
            existing = db.scalar(select(QuestionBankTitle).where(QuestionBankTitle.slug == entry["slug"]))
            if existing:
                title = existing; t_skip += 1
            else:
                create_title(db, BankTitleCreate(title=entry["title"], slug=entry["slug"], description=entry["description"]))
                title = db.scalar(select(QuestionBankTitle).where(QuestionBankTitle.slug == entry["slug"]))
                t_add += 1
            existing_prompts = set(db.scalars(select(QuestionBankQuestion.prompt).where(QuestionBankQuestion.question_id == title.id if False else QuestionBankQuestion.title_id == title.id)).all())
            for q in entry["qs"]:
                qtype, prompt = q[0], q[1]
                options = q[2] if len(q) > 2 else None
                if prompt in existing_prompts:
                    q_skip += 1
                    continue
                opts = [BankOptionCreate(label=o, value=o) for o in (options or [])]
                create_bank_question(db, title.id, BankQuestionCreate(
                    question_type=TYPE_MAP[qtype],
                    prompt=prompt,
                    is_required=False,
                    config={},
                    options=opts,
                ))
                existing_prompts.add(prompt)
                q_add += 1
        db.commit()
        print(f"Batch 1 — titles added: {t_add}, skipped: {t_skip}")
        print(f"Batch 1 — questions added: {q_add}, skipped: {q_skip}")
    except Exception as e:
        db.rollback(); print(f"ERROR: {e}"); raise
    finally:
        db.close()

if __name__ == "__main__":
    main()
