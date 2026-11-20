"""Seed 21 more survey titles (batch 3 of 5)."""

from sqlalchemy import select
from app.database import SessionLocal
from app.models.question_bank import QuestionBankQuestion, QuestionBankTitle
from app.schemas.question_bank import BankOptionCreate, BankQuestionCreate, BankTitleCreate
from app.services.question_bank import create_bank_question, create_title

TYPE_MAP = {"sc":"single_choice","ms":"multi_select","yn":"yes_no","r":"rating","st":"short_text","lt":"long_text"}

BATCH = [
  {"title":"Newspapers & Print Media","slug":"newspapers-print","description":"Reading habits, print news, and information sources.","qs":[
    ("sc","How often do you read a physical newspaper?",["Daily","Weekly","Monthly","Rarely","Never"]),
    ("ms","Which newspapers do you read? Select all that apply.",["Daily Nation","Standard","Star","Business Daily","Taifa Leo","None"]),
    ("sc","Where do you usually access news?",["TV","Radio","Online","Social media","Newspaper","Word of mouth"]),
    ("r","How much do you trust newspapers?",None),
    ("yn","Do you ever buy a newspaper?",None),
    ("sc","How much do you spend on newspapers per month?",["Nothing","Under KES 200","KES 200-500","Over KES 500"]),
    ("ms","Which sections do you read most? Select all that apply.",["National news","Politics","Business","Sports","Entertainment","Classifieds"]),
    ("sc","Are newspapers good value for money?",["Excellent","Good","Fair","Poor"]),
    ("yn","Do you prefer digital or print news?",None),
    ("sc","How do you usually get breaking news?",["TV","Radio","Social media","Apps","Friends"]),
    ("st","What would make you read newspapers more?",None),
    ("st","Describe a newspaper story that stuck with you.",None),
  ]},
  {"title":"Radio & TV Consumption","slug":"radio-tv","description":"Broadcast media habits and preferences.","qs":[
    ("sc","How many hours per day do you listen to the radio?",["Under 1","1-2","3-4","5-6","Over 6"]),
    ("ms","What radio stations do you listen to? Select all that apply.",["Classic FM","Kiss FM","Citizen","Radio Jambo","KBC","Ghetto Radio","None"]),
    ("sc","How many hours of TV do you watch daily?",["Under 1","1-2","3-4","5-6","Over 6","No TV"]),
    ("sc","What is your main TV source?",["Free-to-air","DStv","StarTimes","Netflix/streaming","YouTube","No TV"]),
    ("r","How satisfied are you with local broadcast content?",None),
    ("ms","What do you watch most? Select all that apply.",["News","Soap operas","Sports","Movies","Documentaries","Religious shows","Reality TV","Kids shows"]),
    ("yn","Would you pay more for better TV content?",None),
    ("sc","What's your favorite time to watch TV?",["Morning","Afternoon","Prime evening","Late night"]),
    ("sc","What's your favorite radio show type?",["Talk show","Music","News","Sports","Comedy","Religious"]),
    ("yn","Do you listen to podcasts?",None),
    ("st","What content would you like to see more of?",None),
    ("st","Describe a memorable show or broadcast.",None),
  ]},
  {"title":"Music & Streaming Audio","slug":"music-streaming","description":"Listening habits, streaming platforms, and spending.","qs":[
    ("sc","How many hours per day do you listen to music?",["Under 1","1-2","3-4","Over 4"]),
    ("ms","Which music platforms do you use? Select all that apply.",["Spotify","YouTube Music","Apple Music","Boomplay","Audiomack","MP3 files","Radio","None"]),
    ("sc","Do you pay for a music subscription?",["Yes, monthly","Yes, yearly","No, free only","Pirated"]),
    ("r","How satisfied are you with streaming options?",None),
    ("sc","How much do you spend on music monthly?",["Nothing","Under KES 300","KES 300-1000","Over KES 1000"]),
    ("ms","What genres do you enjoy most? Select all that apply.",["Afrobeats","Bongo","Gospel","Hip-hop","R&B","Reggae","Gengetone","Traditional"]),
    ("yn","Do you listen to local Kenyan artists?",None),
    ("sc","How do you discover new music?",["Radio","YouTube","Social media","Friends","Playlists"]),
    ("r","How important is music to your daily life?",None),
    ("yn","Do you attend live music events?",None),
    ("st","What Kenyan artist deserves more recognition?",None),
    ("st","Describe the role music plays in your life.",None),
  ]},
  {"title":"Religion & Faith Life","slug":"religion-faith","description":"Religious affiliation, practice, and beliefs.","qs":[
    ("sc","How would you describe your religious affiliation?",["Christian","Muslim","Traditional","Hindu","Other","None"]),
    ("sc","How often do you attend religious services?",["Weekly","Several times a month","Monthly","Rarely","Never"]),
    ("r","How important is religion in your daily life?",None),
    ("yn","Do you pray regularly?",None),
    ("ms","What role does religion play in your life? Select all that apply.",["Moral guide","Community","Comfort","Identity","Social network","Financial advice"]),
    ("sc","How much do you give to religious causes per month?",["Nothing","Under KES 500","KES 500-2000","KES 2000-5000","Over KES 5000"]),
    ("yn","Do you participate in religious youth groups?",None),
    ("sc","Do you read any religious texts?",["Daily","Weekly","Rarely","Never"]),
    ("r","How much do you trust religious leaders?",None),
    ("yn","Have you attended a religious event in the past month?",None),
    ("st","What role should religion play in public life?",None),
    ("st","Describe a religious experience that shaped you.",None),
  ]},
  {"title":"Marriage & Relationships","slug":"marriage-relationships","description":"Views on marriage, dating, and partnership.","qs":[
    ("sc","What is your current relationship status?",["Single","Dating","Engaged","Married","Divorced","Widowed"]),
    ("sc","At what age do you think people should marry?",["Under 20","20-24","25-29","30-34","35+"]),
    ("ms","What matters most in a partner? Select all that apply.",["Character","Education","Income","Family background","Religion","Appearance","Humour"]),
    ("yn","Would you consider a long-distance relationship?",None),
    ("r","How important is marriage for a fulfilling life?",None),
    ("sc","Do you prefer traditional or modern dating?",["Traditional","Modern","Mixed","No preference"]),
    ("ms","Biggest challenges in modern relationships? Select all that apply.",["Communication","Money","Trust","Family pressure","Career","None"]),
    ("yn","Do you believe in equal partnership responsibilities?",None),
    ("sc","How many children would you want?",["0","1","2","3","4+"]),
    ("yn","Would you marry outside your religion?",None),
    ("st","What is the most important advice you'd give a young couple?",None),
    ("st","Describe what a healthy relationship looks like to you.",None),
  ]},
  {"title":"Parenting & Family Life","slug":"parenting-family","description":"Raising children, family dynamics, and home life.","qs":[
    ("sc","How many children do you have?",["0","1","2","3","4+"]),
    ("sc","How would you describe your parenting style?",["Authoritative","Permissive","Authoritarian","Hands-off","Learning as I go"]),
    ("r","How confident are you in your parenting?",None),
    ("ms","Biggest parenting challenges? Select all that apply.",["Discipline","Screen time","Money","School work","Peer pressure","Health","None"]),
    ("yn","Do you believe in physical discipline?",None),
    ("sc","How much time do you spend with your children per day?",["Under 1 hour","1-2 hours","3-4 hours","Over 4 hours","Not applicable"]),
    ("ms","What activities do you do with children? Select all that apply.",["Reading","Games","Outdoor play","Church","Homework","Watching TV","None"]),
    ("r","How supported do you feel as a parent?",None),
    ("sc","Who is your main co-parenting support?",["Spouse","Grandparents","Siblings","Friends","No one"]),
    ("yn","Do you talk with your children about hard topics?",None),
    ("st","What parenting support would help most?",None),
    ("st","Describe a parenting moment you're proud of.",None),
  ]},
  {"title":"Nutrition & Diet","slug":"nutrition-diet","description":"Eating habits, dietary choices, and health.","qs":[
    ("sc","How would you rate your diet?",["Excellent","Good","Fair","Poor"]),
    ("sc","How many servings of fruits and vegetables daily?",["0","1-2","3-4","5+"]),
    ("sc","How much water do you drink per day?",["Under 1L","1-2L","2-3L","Over 3L"]),
    ("ms","What do you worry about in your diet? Select all that apply.",["Too much sugar","Too much salt","Too much oil","Not enough vegetables","Skipping meals","None"]),
    ("yn","Do you take any dietary supplements?",None),
    ("sc","How often do you eat out?",["Daily","Weekly","Monthly","Rarely","Never"]),
    ("r","How healthy are your typical meals?",None),
    ("sc","Who usually cooks in your household?",["Yourself","Spouse","Parent","Househelp","Self-service"]),
    ("ms","Diet changes you'd like to make? Select all that apply.",["Eat more vegetables","Drink more water","Reduce sugar","Cook at home","Take supplements","None"]),
    ("yn","Would you consult a nutritionist?",None),
    ("st","What dietary change would most benefit you?",None),
    ("st","Describe a typical day of eating for you.",None),
  ]},
  {"title":"Sleep Health","slug":"sleep-health","description":"Sleep patterns, quality, and habits.","qs":[
    ("sc","How many hours do you sleep per night?",["Under 5","5-6","7-8","9+"]),
    ("sc","How would you rate your sleep quality?",["Excellent","Good","Fair","Poor","Very poor"]),
    ("sc","What time do you usually go to sleep?",["Before 9pm","9-10pm","10-11pm","11pm-12am","After midnight"]),
    ("ms","What affects your sleep? Select all that apply.",["Stress","Phone","Noise","Children","Work","Health","None"]),
    ("yn","Do you use a screen right before bed?",None),
    ("r","How rested do you feel on waking?",None),
    ("sc","Do you take naps?",["Daily","Sometimes","Rarely","Never"]),
    ("ms","Sleep challenges? Select all that apply.",["Insomnia","Waking at night","Snoring","Sleeping late","Early waking","None"]),
    ("yn","Would you try a sleep tracking app?",None),
    ("sc","Do you share a bed with others?",["Alone","Partner","Children","Others","Mixed"]),
    ("st","What would most improve your sleep?",None),
    ("st","Describe your ideal sleep routine.",None),
  ]},
  {"title":"Sexual & Reproductive Health","slug":"srh","description":"SRH knowledge, access, and challenges.","qs":[
    ("sc","How would you rate your SRH knowledge?",["Excellent","Good","Fair","Poor"]),
    ("ms","Which SRH topics do you want more information on? Select all that apply.",["Contraception","STIs","Fertility","Menstrual health","Consent","Pregnancy","None"]),
    ("yn","Do you know where to access SRH services?",None),
    ("sc","How easy is it to access SRH services near you?",["Very easy","Easy","Difficult","Very difficult"]),
    ("r","How comfortable are you discussing SRH with a health worker?",None),
    ("ms","Barriers to SRH services? Select all that apply.",["Cost","Distance","Stigma","Lack of privacy","Judgemental staff","None"]),
    ("yn","Have you ever been denied SRH services?",None),
    ("sc","Where did you first learn about SRH?",["School","Parents","Friends","Media","Health worker"]),
    ("sc","Would you use telehealth for SRH?",["Yes","No","Not sure"]),
    ("yn","Do you feel informed about your reproductive rights?",None),
    ("st","What SRH education would most help young people?",None),
    ("st","Describe a barrier you have faced with SRH services.",None),
  ]},
  {"title":"Gender Equality","slug":"gender-equality","description":"Views on gender roles, equality, and rights.","qs":[
    ("r","How equal are opportunities for men and women in Kenya?",None),
    ("ms","Where is gender inequality most visible? Select all that apply.",["Workplace","Politics","Home","Education","Media","Religion","None"]),
    ("yn","Do you believe men and women should share household work equally?",None),
    ("sc","Should women be encouraged to take leadership roles?",["Strongly agree","Agree","Neutral","Disagree","Strongly disagree"]),
    ("ms","Which gender issues matter most? Select all that apply.",["Domestic violence","Equal pay","Representation","Education","Childcare","None"]),
    ("yn","Have you seen or experienced gender discrimination?",None),
    ("sc","How equal are men and women at home in your experience?",["Very equal","Somewhat equal","Somewhat unequal","Very unequal"]),
    ("r","How much do you trust gender equality policies?",None),
    ("sc","Which gender dimension should improve first?",["Equal pay","Safety","Representation","Education","Health"]),
    ("yn","Would you vote for a woman for president?",None),
    ("st","What would most improve gender equality in your community?",None),
    ("st","Describe a moment you saw gender equality in action.",None),
  ]},
  {"title":"Disability & Inclusion","slug":"disability-inclusion","description":"Disability awareness, inclusion, and access.","qs":[
    ("sc","Do you or a household member live with a disability?",["Yes, myself","Yes, household member","No","Prefer not to say"]),
    ("ms","Which disability types are you aware of? Select all that apply.",["Physical","Visual","Hearing","Intellectual","Learning","Mental health"]),
    ("r","How accessible are public spaces for disabled people?",None),
    ("yn","Do you know where to access disability services?",None),
    ("ms","Biggest barriers for disabled people? Select all that apply.",["Stigma","Transport","Buildings","Employment","Education","Services","None"]),
    ("sc","How inclusive is the workplace you know best?",["Very inclusive","Somewhat","Not very","Not at all"]),
    ("yn","Do you have a friend or colleague with a disability?",None),
    ("sc","How aware are you of disability rights in Kenya?",["Very aware","Somewhat","Not much","Not at all"]),
    ("ms","What inclusion changes are most needed? Select all that apply.",["Accessible buildings","Sign language","Employment quotas","Awareness","Assistive tech","None"]),
    ("yn","Would you advocate for disability inclusion?",None),
    ("st","What would most improve inclusion for disabled people?",None),
    ("st","Describe a person with a disability who inspires you.",None),
  ]},
  {"title":"Youth & Leadership","slug":"youth-leadership","description":"Youth perspectives, leadership, and participation.","qs":[
    ("sc","How old are you?",["Under 18","18-24","25-34","35-44","Over 45"]),
    ("r","How confident are you in the next generation of leaders?",None),
    ("ms","Youth issues that matter most? Select all that apply.",["Employment","Education","Health","Mental health","Civic participation","Entrepreneurship","None"]),
    ("yn","Are youth included in decision-making where you live?",None),
    ("sc","Which leadership quality is most needed in Kenya?",["Integrity","Vision","Competence","Empathy","Courage"]),
    ("ms","Where do youth lead locally? Select all that apply.",["Youth groups","Church","Business","Politics","Sports","None"]),
    ("r","How well are youth represented in national politics?",None),
    ("yn","Would you vote if elections were held today?",None),
    ("sc","Would you run for office one day?",["Yes","Maybe","No","Not sure"]),
    ("sc","What drives youth to engage in civic life?",["Education","Role models","Opportunity","Crisis","Peer influence"]),
    ("st","What would help youth become stronger leaders?",None),
    ("st","Describe a young leader you admire.",None),
  ]},
  {"title":"Political Awareness","slug":"political-awareness","description":"Political knowledge, voting, and engagement.","qs":[
    ("sc","How would you rate your political knowledge?",["Excellent","Good","Fair","Poor"]),
    ("yn","Are you a registered voter?",None),
    ("sc","How often do you follow political news?",["Daily","Weekly","Monthly","Rarely","Never"]),
    ("ms","Which political topics matter most? Select all that apply.",["Economy","Corruption","Health","Education","Security","Housing","None"]),
    ("r","How much do you trust political leaders?",None),
    ("yn","Did you vote in the last general election?",None),
    ("sc","What's the biggest political issue facing Kenya?",["Cost of living","Unemployment","Corruption","Insecurity","Healthcare"]),
    ("ms","Political issues where you'd like more action? Select all that apply.",["Cost of living","Health","Education","Infrastructure","Corruption","None"]),
    ("yn","Would you protest for a cause you believe in?",None),
    ("sc","How fair do you think elections are?",["Very fair","Somewhat fair","Not very fair","Not at all fair"]),
    ("st","What would make you more politically engaged?",None),
    ("st","Describe how politics has affected your daily life.",None),
  ]},
  {"title":"Legal Services & Courts","slug":"legal-services","description":"Legal awareness, court access, and rights.","qs":[
    ("sc","Have you ever used legal services?",["Yes, lawyer","Yes, legal aid","Yes, courts","No"]),
    ("ms","Legal issues you have faced? Select all that apply.",["Land dispute","Family matter","Employment","Criminal","Business contract","None"]),
    ("yn","Do you know your basic legal rights?",None),
    ("sc","How accessible are courts for ordinary Kenyans?",["Very accessible","Somewhat","Not very","Not at all"]),
    ("r","How much do you trust the justice system?",None),
    ("ms","Barriers to legal help? Select all that apply.",["Cost","Distance","Complexity","Language","Fear","None"]),
    ("yn","Would you know where to find legal aid?",None),
    ("sc","Approximately how long would a typical court case take?",["Under 3 months","3-6 months","6-12 months","1-2 years","Over 2 years"]),
    ("sc","Do you have any legal documents in order?",["Will","Title deed","Marriage cert","Business reg","None"]),
    ("yn","Have you ever participated in mediation?",None),
    ("st","What legal service would most help ordinary Kenyans?",None),
    ("st","Describe a legal situation you or someone you know faced.",None),
  ]},
  {"title":"Entrepreneurship & Small Business","slug":"entrepreneurship","description":"Business ownership, growth, and challenges.","qs":[
    ("sc","Do you run your own business?",["Yes, full-time","Yes, side business","No, previously","No"]),
    ("sc","What sector is your business?",["Retail","Food","Services","Manufacturing","Agriculture","Digital","Other"]),
    ("sc","How long has your business been running?",["Under 1 year","1-3 years","3-5 years","Over 5 years","Not applicable"]),
    ("r","How profitable is your business?",None),
    ("ms","Business challenges? Select all that apply.",["Financing","Marketing","Competition","Regulation","Staffing","Cashflow","None"]),
    ("sc","How much capital did you start with?",["Under KES 10000","KES 10000-50000","KES 50000-200000","Over KES 200000"]),
    ("yn","Do you have a written business plan?",None),
    ("sc","How do you usually find customers?",["Word of mouth","Social media","Location","Advertising","Referrals"]),
    ("ms","Support a business needs most? Select all that apply.",["Loans","Training","Market access","Tax relief","Mentors","None"]),
    ("yn","Do you have a separate business bank account?",None),
    ("st","What would most help your business grow?",None),
    ("st","Describe a business challenge you overcame.",None),
  ]},
  {"title":"Marketing & Advertising Preferences","slug":"marketing-ads","description":"Ad responses, ad preferences, and effectiveness.","qs":[
    ("sc","How often do ads influence your purchases?",["Always","Often","Sometimes","Rarely","Never"]),
    ("ms","Where do you notice ads most? Select all that apply.",["Social media","TV","Radio","Billboards","YouTube","Newspapers","None"]),
    ("sc","What ad format catches your attention?",["Video","Image","Text","Audio","Interactive"]),
    ("r","How much do you trust ads in Kenya?",None),
    ("yn","Have you ever clicked an ad and bought something?",None),
    ("ms","Ads you find most annoying? Select all that apply.",["Pop-ups","Skippable video","Auto-play","Robocalls","SMS spam","None"]),
    ("sc","Approximate monthly spend influenced by ads?",["Under KES 500","KES 500-2000","KES 2000-5000","Over KES 5000"]),
    ("yn","Do you skip ads?",None),
    ("sc","Which industry has the most persuasive ads?",["Food","Telecom","Banking","Betting","Retail","Automotive"]),
    ("yn","Would you follow a brand you like?",None),
    ("st","What makes an ad memorable to you?",None),
    ("st","Describe an ad campaign you remember.",None),
  ]},
  {"title":"Customer Service Experience","slug":"customer-service","description":"Dealing with businesses, complaints, and support.","qs":[
    ("r","How satisfied are you with customer service in Kenya?",None),
    ("ms","Which sectors have the best service? Select all that apply.",["Banking","Telcos","Retail","Hospitality","Healthcare","Government","None"]),
    ("sc","How do you prefer to contact support?",["Call centre","WhatsApp","Email","In-person","Chatbot"]),
    ("ms","Customer service issues you face most? Select all that apply.",["Long wait times","No response","Rude staff","Poor resolution","Repeat issues","None"]),
    ("yn","Have you ever posted a complaint on social media?",None),
    ("sc","How long is acceptable for a first response?",["Under 1 hour","1-4 hours","Within a day","Within 2 days","Longer"]),
    ("r","How much do you trust company promises?",None),
    ("sc","What causes you to stop using a service?",["Bad service","Price increase","Better alternative","Personal reasons"]),
    ("yn","Do you leave reviews online?",None),
    ("sc","How likely are you to recommend a brand after great service?",["Very likely","Somewhat","Neutral","Not likely"]),
    ("st","What one change would most improve customer service?",None),
    ("st","Describe a memorable customer service experience.",None),
  ]},
  {"title":"Business Digital Tools","slug":"business-digital","description":"Software, payment, and digital adoption in business.","qs":[
    ("sc","Which digital tools does your business use?",["POS","Accounting","Inventory","CRM","Social media","None"]),
    ("ms","Payment methods your business accepts? Select all that apply.",["Cash","M-Pesa","Airtel Money","Card","Bank transfer","Cheque"]),
    ("r","How helpful are digital tools for your business?",None),
    ("ms","Barriers to more digital adoption? Select all that apply.",["Cost","Training","Reliability","Security","No need","None"]),
    ("sc","How do you manage business records?",["Paper","Excel","Accounting software","Mixed","Nothing"]),
    ("yn","Do you use social media for business?",None),
    ("sc","How much do you spend on digital tools monthly?",["Nothing","Under KES 1000","KES 1000-5000","Over KES 5000"]),
    ("sc","Which tool would you invest in next?",["POS","Accounting","Marketing","Inventory","None"]),
    ("yn","Would you use a business WhatsApp bot?",None),
    ("sc","How reliable is internet at your business?",["Excellent","Good","Fair","Poor"]),
    ("st","What digital tool would most help your business?",None),
    ("st","Describe how digital tools have changed your business.",None),
  ]},
]

def main():
    db = SessionLocal()
    ta=ts=qa=qs=0
    try:
        for e in BATCH:
            t = db.scalar(select(QuestionBankTitle).where(QuestionBankTitle.slug == e["slug"]))
            if t: ts += 1
            else:
                create_title(db, BankTitleCreate(title=e["title"], slug=e["slug"], description=e["description"]))
                t = db.scalar(select(QuestionBankTitle).where(QuestionBankTitle.slug == e["slug"]))
                ta += 1
            existing = set(db.scalars(select(QuestionBankQuestion.prompt).where(QuestionBankQuestion.title_id == t.id)).all())
            for q in e["qs"]:
                if q[1] in existing: qs += 1; continue
                opts = [BankOptionCreate(label=o, value=o) for o in (q[2] or [])]
                create_bank_question(db, t.id, BankQuestionCreate(question_type=TYPE_MAP[q[0]], prompt=q[1], is_required=False, config={}, options=opts))
                existing.add(q[1]); qa += 1
        db.commit()
        print(f"Batch 3 — titles added: {ta}, skipped: {ts}")
        print(f"Batch 3 — questions added: {qa}, skipped: {qs}")
    except Exception as e:
        db.rollback(); print(f"ERROR: {e}"); raise
    finally:
        db.close()

if __name__ == "__main__":
    main()
