"""
config.py — Scraper + pipeline configuration.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ── Firebase ──────────────────────────────────────────────────────────────────
FIREBASE_CREDENTIALS_PATH = os.getenv("FIREBASE_CREDENTIALS_PATH", "serviceAccountKey.json")

# Firebase is ONLY used to trigger job alerts (not for job storage)
FIREBASE_ALERT_COLLECTION = "jobs"

# ── Static website paths ──────────────────────────────────────────────────────
BASE_DIR         = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEBSITE_DIR      = BASE_DIR
DATA_DIR         = os.path.join(BASE_DIR, "data")
JOBS_JSON_PATH   = os.path.join(DATA_DIR, "jobs.json")
RAWJOBS_JSON_PATH = os.path.join(DATA_DIR, "rawjobs.json")
JOBS_OUTPUT_DIR  = os.path.join(BASE_DIR, "jobs")          # /jobs/{slug}/
IMAGES_JOBS_DIR  = os.path.join(WEBSITE_DIR, "images", "jobs") # source images by category
SENT_ALERTS_PATH = os.path.join(DATA_DIR, "sent_alerts.json")  # tracks firebase alerts

# ── Valid Categories from jobcategories.txt ──────────────────────────────────
JOBCATEGORIES_TXT = os.path.join(os.path.dirname(__file__), "jobcategories.txt")
VALID_CATEGORIES = []
if os.path.exists(JOBCATEGORIES_TXT):
    with open(JOBCATEGORIES_TXT, "r", encoding="utf-8") as f:
        VALID_CATEGORIES = [line.strip() for line in f if line.strip()]
else:
    VALID_CATEGORIES = ["Cleaning", "Restaurant", "Caregiver", "Driver", "Logistics", "Security", "IT", "Sales", "Construction", "Hospitality"]

def slugify_category(cat: str) -> str:
    """Standardized slugification for category folders and URLs."""
    import re
    f = str(cat).lower()
    f = f.replace("&", "and")
    f = f.replace("/", " ")
    f = f.replace("_", "-")
    f = re.sub(r'[^a-z0-9\s-]', '', f)
    f = f.replace(" ", "-")
    f = re.sub(r'-+', '-', f)
    return f.strip("-")

def get_safe_category_slug(cat: str) -> str:
    """Returns slug if folder exists in images/jobs, else 'other'."""
    slug = slugify_category(cat)
    folder_path = os.path.join(IMAGES_JOBS_DIR, slug)
    if os.path.exists(folder_path):
        return slug
    return "other"

# ── Location Mapping ──────────────────────────────────────────────────────────
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

# ── GitHub Pages / public URLs ────────────────────────────────────────────────
GITHUB_PAGES_BASE_URL = os.getenv("GITHUB_PAGES_BASE_URL", "https://findjobinfinland.fi")

# ── Job lifecycle ─────────────────────────────────────────────────────────────
EXPIRATION_DAYS = int(os.getenv("EXPIRATION_DAYS", "30"))

# ── Scraping target ───────────────────────────────────────────────────────────
BASE_URL    = "https://duunitori.fi"
SEARCH_URL  = "https://duunitori.fi/tyopaikat"

SEARCH_PARAMS = {
    # "haku": "cleaner",
    # "alue": "helsinki",
}

MAX_PAGES            = int(os.getenv("MAX_PAGES", "10"))
AI_BATCH_SIZE        = int(os.getenv("AI_BATCH_SIZE", "10"))
REQUEST_DELAY_SECONDS = float(os.getenv("REQUEST_DELAY_SECONDS", "2.0"))
DETAIL_DELAY_SECONDS  = float(os.getenv("DETAIL_DELAY_SECONDS", "1.5"))

# ── HTTP headers ──────────────────────────────────────────────────────────────
REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
    "Accept-Language": "fi-FI,fi;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Cache-Control": "max-age=0",
    "Sec-Ch-Ua": '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"Windows"',
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1",
}

# ── Job categories (keyword → category label) ─────────────────────────────────
CATEGORY_KEYWORDS = {
    "Cleaning":    ["clean", "siivous", "housekeep", "maid", "janitor", "siivooj"],
    "Restaurant":  ["cook", "chef", "waiter", "bartender", "kitchen", "restaurant",
                    "ravintola", "kokki", "tarjoilij", "barista", "dishwash"],
    "Caregiver":   ["nurse", "care", "hoitaja", "assistant", "lähihoitaj", "nursing",
                    "elderly", "disability", "healthcare", "sosiaali"],
    "Driver":      ["driver", "delivery", "truck", "kuljettaja", "ajaja", "courier",
                    "taxi", "chauffeur", "logistics driver"],
    "Logistics":   ["warehouse", "logistics", "varasto", "varastotyö", "picking",
                    "packing", "fulfillment", "inventory", "forklift"],
    "Security":    ["security", "guard", "vartija", "vartiointi", "turvahenkilö"],
    "IT":          ["developer", "software", "programmer", "data", "cloud", "devops",
                    "engineer", "coding", "python", "java", "react", "backend"],
    "Sales":       ["sales", "myynti", "myyjä", "retail", "cashier", "kassatyöntekijä",
                    "account manager", "business development"],
    "Construction":["construction", "rakennustyö", "rakentaja", "carpenter", "welder",
                    "electrician", "plumber", "structural"],
    "Hospitality": ["hotel", "hotelli", "reception", "vastaanottovirkaili", "hostel",
                    "accommodation", "front desk"],
}

# Finnish city names to normalize
CITY_KEYWORDS = [
    "Helsinki", "Espoo", "Vantaa", "Tampere", "Turku", "Oulu", "Jyväskylä",
    "Lahti", "Kuopio", "Pori", "Kouvola", "Joensuu", "Lappeenranta", "Vaasa",
    "Hämeenlinna", "Rovaniemi", "Seinäjoki", "Mikkeli", "Kotka", "Salo",
    "Porvoo", "Kokkola", "Lohja", "Hyvinkää", "Nurmijärvi", "Järvenpää",
    "Kajaani", "Rauma", "Kerava", "Nokia", "Tuusula", "Kirkkonummi",
    "Sipoo", "Vihti", "Kauniainen",
]
