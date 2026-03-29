"""
config.py — Scraper + pipeline configuration.
"""

import os
import re
from dotenv import load_dotenv

load_dotenv()

# ── Firebase ──────────────────────────────────────────────────────────────────
FIREBASE_CREDENTIALS_PATH = os.getenv("FIREBASE_CREDENTIALS_PATH", "serviceAccountKey.json")
FIREBASE_ALERT_COLLECTION = "jobs"

# ── Static website paths ──────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEBSITE_DIR = BASE_DIR
DATA_DIR = os.path.join(BASE_DIR, "scraper", "data")

JOBS_JSON_PATH = os.path.join(DATA_DIR, "jobs.json")
RAWJOBS_JSON_PATH = os.path.join(DATA_DIR, "rawjobs.json")
SENT_ALERTS_PATH = os.path.join(DATA_DIR, "sent_alerts.json")

JOBS_OUTPUT_DIR = os.path.join(BASE_DIR, "jobs")
IMAGES_JOBS_DIR = os.path.join(WEBSITE_DIR, "images", "jobs")

# ── Categories ────────────────────────────────────────────────────────────────
JOBCATEGORIES_TXT = os.path.join(os.path.dirname(__file__), "jobcategories.txt")

VALID_CATEGORIES = []
if os.path.exists(JOBCATEGORIES_TXT):
    with open(JOBCATEGORIES_TXT, "r", encoding="utf-8") as f:
        VALID_CATEGORIES = [line.strip() for line in f if line.strip()]
else:
    VALID_CATEGORIES = ["other"]


def slugify_category(cat: str) -> str:
    """Standardized slugification for category folders and URLs."""
    f = str(cat).lower().strip()
    f = f.replace("&", "and")
    f = f.replace("/", " ")
    f = f.replace("_", "-")
    f = re.sub(r"[^a-z0-9\s-]", "", f)
    f = f.replace(" ", "-")
    f = re.sub(r"-+", "-", f)
    return f.strip("-")


def get_safe_category_slug(cat: str) -> str:
    """Returns slug if folder exists in images/jobs, else 'other'."""
    slug = slugify_category(cat)
    folder_path = os.path.join(IMAGES_JOBS_DIR, slug)
    if os.path.exists(folder_path):
        return slug
    return "other"


# ── GitHub Pages ──────────────────────────────────────────────────────────────
GITHUB_PAGES_BASE_URL = os.getenv(
    "GITHUB_PAGES_BASE_URL",
    "https://findjobinfinland.fi"
)

# ── Job lifecycle ─────────────────────────────────────────────────────────────
EXPIRATION_DAYS = int(os.getenv("EXPIRATION_DAYS", "30"))

# ── Scraping target ───────────────────────────────────────────────────────────
BASE_URL = "https://duunitori.fi"
SEARCH_URL = "https://duunitori.fi/tyopaikat"

SEARCH_PARAMS = {
    # "haku": "cleaner",
    # "alue": "helsinki",
}

MAX_PAGES = int(os.getenv("MAX_PAGES", "10"))
AI_BATCH_SIZE = int(os.getenv("AI_BATCH_SIZE", "10"))
REQUEST_DELAY_SECONDS = float(os.getenv("REQUEST_DELAY_SECONDS", "2.0"))
DETAIL_DELAY_SECONDS = float(os.getenv("DETAIL_DELAY_SECONDS", "1.5"))

# ── HTTP headers ──────────────────────────────────────────────────────────────
REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "fi-FI,fi;q=0.9,en;q=0.8",
}

# ── CATEGORY KEYWORDS ─────────────────────────────────────────────────────────
CATEGORY_KEYWORDS = {
    # IT / SOFTWARE
    "software-development": [
        "developer", "software developer", "programmer", "koodari", "ohjelmistokehittäjä",
        "ohjelmistosuunnittelija", "sovelluskehittäjä", "web developer", "mobile developer",
        "frontend", "backend", "full stack", "fullstack", "react", "angular", "vue",
        "node", "javascript", "typescript", "python", "java", "php", "c#", ".net",
        "spring", "django", "flask", "laravel", "wordpress"
    ],
    "web-development": [
        "web developer", "website developer", "wordpress developer", "front-end developer",
        "back-end developer", "web designer"
    ],
    "mobile-development": [
        "mobile developer", "android developer", "ios developer", "flutter", "react native",
        "swift", "kotlin"
    ],
    "frontend-development": [
        "frontend", "front-end", "ui developer", "react developer", "angular developer", "vue developer"
    ],
    "backend-development": [
        "backend", "back-end", "api developer", "server-side", "microservices"
    ],
    "full-stack-development": [
        "full stack", "full-stack", "fullstack"
    ],
    "it-and-tech": [
        "it", "tech", "technical support", "it support", "helpdesk", "ict",
        "it specialist", "technical specialist", "support engineer"
    ],
    "data-and-ai-machine-learning": [
        "data scientist", "machine learning", "tekoäly", "ai", "artificial intelligence",
        "data engineer", "analytics", "deep learning", "nlp", "computer vision",
        "predictive model", "ml engineer"
    ],
    "data-engineering": [
        "data engineer", "etl", "data pipeline", "data warehouse", "bigquery", "spark"
    ],
    "data-analytics-and-bi": [
        "data analyst", "business intelligence", "bi analyst", "power bi", "tableau", "analytics"
    ],
    "cybersecurity": [
        "cybersecurity", "information security", "infosec", "soc analyst",
        "penetration testing", "security analyst", "ethical hacker"
    ],
    "cloud-and-devops": [
        "devops", "cloud", "aws", "azure", "gcp", "docker", "kubernetes", "ci/cd",
        "terraform", "ansible", "platform engineer", "site reliability engineer", "sre"
    ],
    "qa-and-testing": [
        "qa", "quality assurance", "tester", "test engineer", "manual testing", "automation testing"
    ],
    "it-support-and-helpdesk": [
        "helpdesk", "it support", "desktop support", "service desk", "technical support"
    ],
    "systems-and-network-administration": [
        "system administrator", "network administrator", "sysadmin", "network engineer", "infrastructure"
    ],
    "product-management": [
        "product manager", "product owner", "technical product manager"
    ],
    "technical-writing": [
        "technical writer", "documentation specialist", "documentation engineer"
    ],

    # ENGINEERING / TECHNICAL
    "engineering": [
        "engineer", "insinööri", "project engineer", "design engineer", "engineer trainee"
    ],
    "mechanical-engineering": [
        "mechanical engineer", "mekaniikka", "machine design", "mechanical design"
    ],
    "electrical-engineering": [
        "electrical engineer", "sähköinsinööri", "electronics engineer"
    ],
    "automation-and-controls": [
        "automation engineer", "automation technician", "plc", "controls engineer"
    ],
    "process-engineering": [
        "process engineer", "process specialist"
    ],
    "civil-engineering": [
        "civil engineer", "structural engineer", "site engineer"
    ],
    "architecture-and-design": [
        "architect", "architecture", "building designer", "architectural designer"
    ],
    "cad-and-bim": [
        "cad", "bim", "revit", "autocad", "draftsperson"
    ],
    "research-and-development": [
        "research", "r&d", "innovation", "development specialist"
    ],
    "science-and-laboratory": [
        "laboratory", "lab", "scientist", "chemist", "biologist", "research assistant"
    ],

    # MANUFACTURING / INDUSTRY
    "manufacturing-and-production": [
        "manufacturing", "production", "factory", "plant", "operator", "production worker",
        "tuotanto", "tuotantotyö"
    ],
    "industrial-and-factory-work": [
        "industrial", "factory work", "line worker", "plant worker", "production line"
    ],
    "mechanical-and-metal-work": [
        "mechanic", "metal", "metal work", "machinist", "sheet metal", "metalworker"
    ],
    "machining-and-cnc": [
        "cnc", "machining", "cnc operator", "lathe operator", "milling"
    ],
    "welding": [
        "welder", "welding", "hitsaaja"
    ],
    "electronics-and-electrical": [
        "electronics", "electrical", "electrical assembly", "pcb", "soldering"
    ],
    "assembly-and-installation": [
        "assembly", "assembler", "installation", "installer"
    ],
    "food-production-industry": [
        "food production", "bakery production", "meat processing", "food packing"
    ],
    "wood-and-forest-industry": [
        "wood industry", "timber", "sawmill", "forest industry"
    ],
    "textile-and-clothing-industry": [
        "textile", "garment", "clothing production", "sewing"
    ],
    "printing-and-packaging": [
        "printing", "packaging", "packer", "labeling"
    ],
    "quality-control-and-assurance": [
        "quality control", "quality assurance", "inspection", "inspector"
    ],

    # CONSTRUCTION
    "construction-and-labor": [
        "construction", "rakennus", "rakennustyö", "builder", "site worker",
        "laborer", "rakennustyöntekijä", "general construction"
    ],
    "carpentry": [
        "carpenter", "puuseppä", "joiner", "woodworker"
    ],
    "plumbing": [
        "plumber", "putkiasentaja", "putki", "pipe installer"
    ],
    "electrical-work": [
        "electrician", "sähköasentaja", "electrical installer"
    ],
    "hvac-and-maintenance": [
        "hvac", "ventilation", "maintenance worker", "maintenance installer"
    ],
    "property-maintenance": [
        "property maintenance", "kiinteistö", "caretaker", "facility maintenance"
    ],
    "painting-and-finishing": [
        "painter", "painting", "finishing", "surface treatment"
    ],
    "tiling-and-flooring": [
        "tiler", "flooring", "tile installation", "laminate installation"
    ],
    "roofing": [
        "roofer", "roofing", "kattotyö", "roof installer"
    ],
    "earthworks-and-infrastructure": [
        "maanrakennus", "maanrakennustyöntekijä", "earthworks", "road construction",
        "excavator", "groundworks", "infrastructure"
    ],
    "surveying-and-site-engineering": [
        "surveying", "land surveyor", "site engineer", "measurement technician"
    ],
    "construction-cleaning": [
        "construction cleaning", "rakennussiivous", "site cleaning", "post-construction cleaning"
    ],
    "moving-jobs": [
        "moving", "mover", "removals", "relocation worker"
    ],

    # LOGISTICS / TRANSPORT
    "logistics-and-delivery": [
        "logistics", "delivery", "distribution", "dispatcher", "lähetti"
    ],
    "warehouse-and-inventory": [
        "warehouse", "varasto", "varastotyö", "inventory", "stock control",
        "picker", "packer", "storage worker"
    ],
    "transportation-and-driving": [
        "driver", "kuljettaja", "driving", "chauffeur", "transport driver"
    ],
    "courier-jobs": [
        "courier", "lähetti", "parcel delivery", "messenger"
    ],
    "courier-and-last-mile-delivery": [
        "last mile", "home delivery", "delivery courier"
    ],
    "food-delivery-driver": [
        "food delivery", "restaurant delivery", "meal delivery", "wolt courier", "foodora courier"
    ],
    "forklift-driver": [
        "forklift", "forklift driver", "trukki", "trukkikuski"
    ],
    "forklift-and-material-handling": [
        "material handling", "warehouse machinery", "loading and unloading"
    ],
    "picker-and-packer": [
        "picker", "packer", "order picker", "packing", "keräilijä"
    ],
    "terminal-worker": [
        "terminal worker", "sorting center", "cargo terminal"
    ],
    "supply-chain-management": [
        "supply chain", "planner", "demand planning", "supply planner"
    ],
    "procurement-and-sourcing": [
        "procurement", "purchasing", "buyer", "sourcing"
    ],
    "customs-and-import-export": [
        "customs", "import", "export", "freight forwarding"
    ],
    "taxi-and-ride-services": [
        "taxi", "ride service", "ride-sharing", "uber driver", "bolt driver"
    ],
    "bus-driver": [
        "bus driver", "linja-autonkuljettaja", "coach driver"
    ],
    "truck-driver": [
        "truck driver", "rekka", "rekkakuski", "heavy vehicle driver"
    ],

    # HEALTHCARE / CARE
    "nursing": [
        "nurse", "registered nurse", "practical nurse", "sairaanhoitaja", "lähihoitaja"
    ],
    "healthcare": [
        "healthcare", "medical", "clinic", "hospital", "doctor", "physician"
    ],
    "caregiver-elderly-care": [
        "caregiver", "elderly care", "home care", "care worker", "care assistant",
        "hoiva", "vanhustenhoito"
    ],
    "social-work": [
        "social work", "social worker", "community support", "family worker"
    ],
    "disability-support": [
        "disability support", "special needs support", "support worker"
    ],
    "mental-health-services": [
        "mental health", "therapy", "psychology", "counselling", "psychiatric"
    ],
    "doctor-and-physician-jobs": [
        "doctor", "physician", "general practitioner", "medical doctor"
    ],
    "dentistry": [
        "dentist", "dental", "dental assistant", "suuhygienisti"
    ],
    "pharmacy": [
        "pharmacy", "pharmacist", "apteekki", "pharmaceutical"
    ],
    "laboratory-healthcare": [
        "medical laboratory", "clinical laboratory", "lab technician"
    ],
    "medical-imaging": [
        "radiographer", "medical imaging", "x-ray", "mri", "ct"
    ],
    "physiotherapy-and-rehabilitation": [
        "physiotherapist", "rehabilitation", "physical therapy"
    ],
    "occupational-therapy": [
        "occupational therapist", "occupational therapy"
    ],
    "childcare-and-family-support": [
        "childcare", "family support", "child welfare"
    ],
    "personal-assistant-jobs": [
        "personal assistant", "executive assistant", "avustaja", "assistant for disabled"
    ],

    # CLEANING / FACILITY
    "cleaning": [
        "cleaner", "cleaning", "siivooja", "siivous", "cleaning staff"
    ],
    "industrial-cleaning": [
        "industrial cleaning", "factory cleaning", "teollisuussiivous"
    ],
    "office-cleaning": [
        "office cleaning", "toimistosiivous", "cleaning offices"
    ],
    "hotel-cleaning": [
        "hotel cleaning", "hotel cleaner", "room cleaning", "housekeeping hotel"
    ],
    "housekeeping": [
        "housekeeping", "housekeeper", "room attendant"
    ],
    "laundry-services": [
        "laundry", "washing", "dry cleaning", "pesula"
    ],
    "property-and-facility-services": [
        "facility services", "property services", "building services"
    ],
    "janitor": [
        "janitor", "caretaker building", "vahtimestari"
    ],
    "caretaker": [
        "caretaker", "kiinteistönhoitaja", "property caretaker"
    ],
    "waste-management-and-recycling": [
        "waste management", "recycling", "sorting waste"
    ],

    # FOOD / RESTAURANT / HOSPITALITY
    "cooking-and-kitchen-staff": [
        "cook", "chef", "kokki", "kitchen staff", "keittiö", "kitchen worker"
    ],
    "restaurant": [
        "restaurant", "ravintola", "tarjoilija", "waiter", "waitress",
        "server", "barista", "kahvila"
    ],
    "fast-food-jobs": [
        "fast food", "hesburger", "mcdonalds", "burger worker", "quick service restaurant"
    ],
    "pizza-kebab-workers": [
        "pizza", "kebab", "pizzeria", "pizza baker", "kebab worker"
    ],
    "bakery-jobs": [
        "bakery", "baker", "leipomo", "leipuri"
    ],
    "bakery-and-pastry": [
        "pastry", "confectioner", "dessert chef"
    ],
    "dishwasher": [
        "dishwasher", "tiski", "astianpesu", "kitchen porter"
    ],
    "hospitality-and-service": [
        "hospitality", "guest service", "service staff", "host", "hostess"
    ],
    "hotel-jobs": [
        "hotel", "hotelli", "reception", "front desk", "hotel receptionist"
    ],
    "tourism-and-seasonal-work": [
        "tourism", "seasonal work", "travel", "ski resort", "summer season"
    ],
    "catering": [
        "catering", "banquet", "event food service"
    ],
    "bar-and-nightlife": [
        "bartender", "bar staff", "nightclub", "cocktail bar"
    ],
    "coffee-shop-and-cafe-jobs": [
        "coffee shop", "cafe", "kahvila", "café worker"
    ],
    "reception-and-front-desk": [
        "receptionist", "front desk", "reception"
    ],

    # CUSTOMER SERVICE / RETAIL
    "customer-service-support": [
        "customer service", "customer support", "asiakaspalvelu",
        "asiakaspalvelija", "service advisor"
    ],
    "retail-and-store-jobs": [
        "retail", "store", "shop assistant", "myymälä", "sales floor", "store worker"
    ],
    "cashier": [
        "cashier", "kassa", "kassatyöntekijä", "checkout"
    ],
    "sales-assistant": [
        "sales assistant", "shop assistant", "store assistant", "myyjä"
    ],
    "call-center-and-phone-support": [
        "call center", "phone support", "contact center", "telemarketing"
    ],
    "technical-customer-support": [
        "technical customer support", "support specialist", "product support"
    ],
    "field-service-and-installation": [
        "field service", "field technician", "on-site service"
    ],
    "installation-jobs": [
        "installation", "installer", "asentaja", "equipment installation"
    ],
    "complaints-and-back-office-support": [
        "back office", "complaints handling", "case processing"
    ],

    # BUSINESS / OFFICE / FINANCE
    "finance-and-accounting": [
        "accounting", "accountant", "bookkeeper", "finance", "controller", "payroll"
    ],
    "banking-and-insurance": [
        "banking", "bank", "insurance", "loan advisor", "claims handler"
    ],
    "sales-and-marketing": [
        "sales", "marketing", "digital marketing", "seo", "advertising",
        "myynti", "myyjä", "account manager", "business development",
        "customer acquisition", "growth marketing"
    ],
    "digital-marketing": [
        "digital marketing", "seo", "sem", "google ads", "social media marketing", "content marketing"
    ],
    "e-commerce": [
        "e-commerce", "online store", "shopify", "marketplace", "verkkokauppa"
    ],
    "human-resources": [
        "hr", "human resources", "recruiter", "recruitment", "talent acquisition"
    ],
    "recruitment-and-talent-acquisition": [
        "talent acquisition", "headhunter", "staffing consultant"
    ],
    "business-development": [
        "business development", "partnership", "commercial development"
    ],
    "administration-and-office-work": [
        "office", "toimisto", "administrator", "administration", "coordinator",
        "secretary", "clerical", "office assistant"
    ],
    "project-management": [
        "project manager", "project coordinator", "program manager"
    ],
    "operations-management": [
        "operations manager", "operations coordinator", "operational excellence"
    ],
    "executive-and-leadership": [
        "ceo", "managing director", "head of", "director", "country manager"
    ],
    "legal-services": [
        "legal", "lawyer", "attorney", "paralegal", "jurist"
    ],
    "consulting": [
        "consultant", "advisor", "specialist consultant"
    ],
    "auditing": [
        "audit", "auditor", "internal audit"
    ],
    "compliance": [
        "compliance", "risk", "regulatory", "governance"
    ],
    "real-estate-and-property-management": [
        "real estate", "property manager", "leasing", "property administration"
    ],

    # EDUCATION / PUBLIC
    "education-and-teaching": [
        "teacher", "opettaja", "teaching", "school", "subject teacher"
    ],
    "early-childhood-education": [
        "daycare", "päiväkoti", "varhaiskasvatus", "kindergarten", "early childhood"
    ],
    "training-and-coaching": [
        "trainer", "coach", "instructor", "facilitator"
    ],
    "special-education": [
        "special education", "special needs teacher", "special educator"
    ],
    "school-support-and-assistant-jobs": [
        "school assistant", "teaching assistant", "classroom assistant"
    ],
    "higher-education-and-research-teaching": [
        "lecturer", "university teacher", "professor", "research teaching"
    ],
    "public-administration": [
        "public administration", "municipality", "city office", "civil service", "kunta"
    ],
    "government-jobs": [
        "government", "public sector", "state job", "ministry"
    ],
    "ngo-and-nonprofit": [
        "ngo", "nonprofit", "charity", "association work"
    ],

    # CREATIVE / MEDIA
    "graphic-design": [
        "graphic designer", "visual designer", "branding", "print design"
    ],
    "ui-ux-design": [
        "ui", "ux", "product designer", "interaction designer", "user experience"
    ],
    "content-creation": [
        "content creator", "copywriter", "writer", "social media content"
    ],
    "copywriting-and-editing": [
        "copywriter", "editor", "proofreader", "content editor"
    ],
    "photography-and-video": [
        "photography", "videography", "video editor", "camera operator"
    ],
    "digital-media": [
        "digital media", "media specialist", "multimedia"
    ],
    "journalism-and-publishing": [
        "journalist", "editorial", "publishing", "reporter"
    ],
    "translation-and-localization": [
        "translator", "localization", "interpreting", "proofreading languages"
    ],

    # BEAUTY / SPORTS
    "beauty-and-hairdressing": [
        "hairdresser", "barber", "beautician", "cosmetologist"
    ],
    "fitness-and-sports": [
        "fitness", "sports", "gym instructor", "personal trainer", "coach"
    ],
    "wellness-and-spa": [
        "spa", "wellness", "sauna", "beauty spa"
    ],
    "massage-therapy": [
        "massage", "massage therapist", "therapist"
    ],

    # AGRICULTURE / ENVIRONMENT
    "farming-and-agriculture": [
        "farm", "agriculture", "farmer", "harvest"
    ],
    "farm-worker": [
        "farm worker", "maatila", "agricultural worker"
    ],
    "greenhouse-work": [
        "greenhouse", "kasvihuone", "greenhouse worker"
    ],
    "berry-picking": [
        "berry picking", "marjanpoiminta", "berry picker"
    ],
    "seasonal-agriculture": [
        "seasonal agriculture", "seasonal farm work"
    ],
    "forestry": [
        "forestry", "forest worker", "logging"
    ],
    "fishing": [
        "fishing", "fish farm", "fisherman"
    ],
    "animal-care-and-veterinary": [
        "animal care", "veterinary", "vet nurse", "pet care"
    ],
    "environmental-jobs": [
        "environment", "sustainability", "recycling", "waste management"
    ],
    "renewable-energy": [
        "renewable energy", "solar", "wind power"
    ],
    "energy-and-utilities": [
        "energy", "utilities", "power plant", "district heating"
    ],

    # SECURITY / SAFETY
    "security-jobs": [
        "security", "vartiointi", "security officer"
    ],
    "security-guard": [
        "security guard", "vartija", "guard"
    ],
    "surveillance-and-monitoring": [
        "surveillance", "monitoring", "control room", "cctv"
    ],
    "fire-and-safety-services": [
        "fire safety", "rescue", "emergency services"
    ],
    "occupational-health-and-safety": [
        "occupational safety", "health and safety", "hse"
    ],

    # AUTOMOTIVE / TECH MAINTENANCE
    "automotive": [
        "automotive", "car service", "vehicle service"
    ],
    "vehicle-maintenance-and-repair": [
        "mechanic", "automechanic", "vehicle repair", "car repair"
    ],
    "maintenance-technician": [
        "maintenance technician", "huoltoteknikko", "maintenance mechanic"
    ],
    "service-technician": [
        "service technician", "field technician", "service engineer"
    ],
    "repair-technician": [
        "repair technician", "equipment repair", "fault repair"
    ],
    "marine-and-aviation": [
        "marine", "aviation", "aircraft", "shipyard", "vessel"
    ],

    # JOB TYPES / LANGUAGE / PLATFORM
    "internships-and-traineeships": [
        "internship", "trainee", "graduate program", "harjoittelu"
    ],
    "apprenticeships": [
        "apprenticeship", "oppisopimus"
    ],
    "part-time-jobs": [
        "part-time", "osa-aikainen", "part time"
    ],
    "student-jobs": [
        "student job", "opiskelija", "for students"
    ],
    "summer-jobs": [
        "summer job", "kesätyö", "summer worker"
    ],
    "freelance-and-gig-jobs": [
        "freelance", "gig", "contractor", "self-employed"
    ],
    "remote-jobs": [
        "remote", "work from home", "hybrid", "etätyö"
    ],
    "bilingual-and-multilingual-jobs": [
        "bilingual", "multilingual", "swedish speaking", "english speaking", "language skills"
    ],
    "no-experience-jobs": [
        "no experience", "entry level", "training provided", "no prior experience"
    ],
    "english-speaking-jobs": [
        "english speaking", "english required", "english only"
    ],
    "finnish-speaking-jobs": [
        "finnish speaking", "finnish required", "suomen kielen taito"
    ],
    "wolt-jobs": [
        "wolt", "wolt courier", "wolt delivery"
    ],
    "foodora-jobs": [
        "foodora", "foodora courier", "foodora delivery"
    ],
    "bolt-jobs": [
        "bolt", "bolt driver", "bolt courier"
    ],
    "uber-jobs": [
        "uber", "uber driver"
    ],

    # FALLBACK
    "other": []
}

# ── CITY KEYWORDS ─────────────────────────────────────────────────────────────
CITY_KEYWORDS = [
    # Uusimaa and nearby
    "Helsinki", "Espoo", "Vantaa", "Kauniainen", "Järvenpää", "Kerava",
    "Tuusula", "Sipoo", "Kirkkonummi", "Lohja", "Nurmijärvi", "Hyvinkää",
    "Inkoo", "Porvoo", "Pukkila", "Siuntio", "Mäntsälä", "Pornainen",
    "Vihti", "Hanko", "Raseborg", "Raasepori", "Lapinjärvi", "Loviisa",
    "Askola",

    # Capital area districts / common localities
    "Pasila", "Malmi", "Tikkurila", "Leppävaara", "Matinkylä", "Myyrmäki",
    "Kamppi", "Kallio", "Tapiola", "Itäkeskus", "Lauttasaari", "Vuosaari",
    "Oulunkylä", "Munkkiniemi", "Kivenlahti", "Espoonlahti", "Koivukylä",
    "Pitäjänmäki", "Herttoniemi", "Kaarela", "Viinikkala", "Nikkilä",
    "Rajamäki", "Klaukkala", "Tammisto", "Hiekkaharju", "Kauklahti",
    "Kilo", "Olari", "Friisilä",

    # Major cities
    "Tampere", "Turku", "Oulu", "Jyväskylä", "Kuopio", "Lahti", "Vaasa",
    "Seinäjoki", "Rovaniemi", "Kotka", "Lappeenranta", "Pori", "Kokkola",
    "Joensuu", "Hämeenlinna", "Mikkeli", "Salo", "Rauma", "Kajaani",
    "Nokia", "Ylöjärvi", "Kaarina", "Naantali", "Savonlinna", "Imatra",
    "Riihimäki", "Forssa", "Iisalmi", "Varkaus", "Pieksämäki",

    # Additional important cities
    "Kemi", "Tornio", "Raahe", "Jämsä", "Äänekoski", "Uusikaupunki",
    "Loimaa", "Pietarsaari", "Jakobstad", "Parainen", "Kemijärvi",
    "Kristiinankaupunki", "Närpiö", "Kauhajoki", "Kurikka", "Alavus",
    "Lapua", "Ylivieska", "Nivala", "Haapajärvi", "Suonenjoki", "Lieksa",
    "Nurmes", "Kitee", "Outokumpu", "Siilinjärvi", "Mustasaari", "Pedersöre"
]

UUSIMAA_CITIES = [
    "Helsinki", "Espoo", "Vantaa", "Kauniainen", "Järvenpää", "Kerava",
    "Tuusula", "Sipoo", "Kirkkonummi", "Lohja", "Nurmijärvi", "Hyvinkää",
    "Inkoo", "Porvoo", "Pukkila", "Siuntio", "Mäntsälä", "Pornainen",
    "Vihti", "Hanko", "Raseborg", "Raasepori", "Lapinjärvi", "Loviisa",
    "Askola", "Pasila", "Malmi", "Tikkurila", "Leppävaara", "Matinkylä",
    "Myyrmäki", "Kamppi", "Kallio", "Tapiola", "Itäkeskus", "Lauttasaari",
    "Vuosaari", "Oulunkylä", "Munkkiniemi", "Kivenlahti", "Espoonlahti",
    "Koivukylä", "Pitäjänmäki", "Herttoniemi", "Kaarela", "Viinikkala",
    "Nikkilä", "Rajamäki", "Klaukkala", "Tammisto", "Hiekkaharju",
    "Kauklahti", "Kilo", "Olari", "Friisilä"
]
UUSIMAA_CITIES_LOWER = {c.lower() for c in UUSIMAA_CITIES}