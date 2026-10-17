"""Central configuration: paths, API settings and the business rules used by the pipeline.

Everything that would otherwise be a magic number lives here so it can be changed in one place.
"""
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")

# --- Paths -----------------------------------------------------------------
RAW_DIR = ROOT / "data" / "raw"
SERPAPI_CACHE_DIR = RAW_DIR / "serpapi"
PROCESSED_DIR = ROOT / "data" / "processed"
DIRTY_CSV_PATH = RAW_DIR / "brand_dirty_dataset.csv"
API_CSV_PATH = PROCESSED_DIR / "api_products.csv"
CLEAN_CSV_PATH = PROCESSED_DIR / "clean_dataset.csv"
DB_PATH = ROOT / "data" / "brand_visibility.db"

# --- SerpApi (Google Shopping) --------------------------------------------
SERPAPI_KEY = os.getenv("SERPAPI_API_KEY")
SERPAPI_ENDPOINT = "https://serpapi.com/search.json"
# India locale so prices come back in INR, matching the provided CSV.
SERPAPI_PARAMS = {
    "engine": "google_shopping",
    "google_domain": "google.co.in",
    "gl": "in",
    "hl": "en",
    "location": "India",
}
REQUEST_TIMEOUT_SECONDS = 30

# Same keywords as the provided CSV so API and CSV rows are comparable after merging.
KEYWORDS = [
    "microwave oven convection",
    "air fryer India",
    "power bank fast charging",
    "office chair ergonomic",
    "men running shoes",
]

# --- Unified schema --------------------------------------------------------
BASE_COLUMNS = [
    "keyword", "title", "price", "raw_price", "rating", "reviews",
    "platform", "delivery", "position", "data_source",
]

# --- Cleaning rules --------------------------------------------------------
# Placeholder strings that mean "no value" in the raw data.
MISSING_TOKENS = ["not available", "n/a", "na", "none", "null", "-", "", "many"]
# Sentinel numbers used in place of a real value (e.g. -999).
INVALID_PRICE_MAX = 0  # prices <= this are invalid
RATING_MIN, RATING_MAX = 0.0, 5.0
# Prices above Q3 + k * IQR (per keyword) are capped to that fence.
OUTLIER_IQR_MULTIPLIER = 1.5
OUTLIER_CAP_SOURCES = ["csv"]
# Sources where a missing review count means "no reviews yet" rather than "unknown".
REVIEWS_MISSING_IS_ZERO = ["api"]
# A duplicate is the same listing: same product on the same platform at the same price.
DUPLICATE_KEYS = ["keyword", "title", "platform", "price"]

# Seller names from Google Shopping -> canonical platform. Matched as substrings, lowercase.
PLATFORM_ALIASES = {
    "amazon": "Amazon",
    "flipkart": "Flipkart",
    "croma": "Croma",
    "reliance": "Reliance Digital",
    "jiomart": "JioMart",
    "tata cliq": "Tata CLiQ",
    "myntra": "Myntra",
    "ajio": "AJIO",
    "vijay sales": "Vijay Sales",
    "snapdeal": "Snapdeal",
    "meesho": "Meesho",
    "decathlon": "Decathlon",
    "pepperfry": "Pepperfry",
    "bigbasket": "BigBasket",
}
# Suffixes stripped from seller names before matching ("Bata IN", "Ikea.in").
PLATFORM_SUFFIXES = r"(\.co\.in|\.com|\.in|\s+india|\s+in)$"

# --- Feature engineering ---------------------------------------------------
# Brands matched (case-insensitive, whole word) in titles; otherwise the first word is used.
KNOWN_BRANDS = [
    "HP", "LG", "Philips", "Nike", "Boat", "Puma", "Samsung", "Dell", "Sony",
    "Adidas", "Asics", "Reebok", "Skechers", "Campus", "Bajaj", "Prestige", "Pigeon",
    "Havells", "Inalsa", "Kent", "Agaro", "IFB", "Panasonic", "Godrej", "Morphy Richards",
    "Mi", "Xiaomi", "Redmi", "Ambrane", "Anker", "Realme", "OnePlus", "Portronics",
    "Green Soul", "Featherlite", "Wakefit", "Sleepyhead", "Savya Home", "Ikea",
    "Decathlon", "Kalenji", "Whirlpool", "Haier", "Voltas Beko", "Lifelong", "Glen",
    "Preethi", "Kepler Brooks", "Nivia", "Bata", "Red Tape", "Sparx", "Asian", "Noise",
]
# Leading title words that describe the product, not the maker.
GENERIC_TITLE_WORDS = {
    "men", "mens", "women", "womens", "unisex", "ergonomic", "office", "chair", "chairs",
    "the", "new", "premium", "high", "mesh", "running", "sports", "portable", "digital",
}
# Band upper bounds are exclusive; the last band is open-ended.
PRICE_BANDS = [
    (5_000, "Budget (<₹5k)"),
    (15_000, "Mid-range (₹5k–15k)"),
    (35_000, "Premium (₹15k–35k)"),
    (float("inf"), "Luxury (₹35k+)"),
]
RATING_BANDS = [
    (3.0, "Below 3"),
    (4.0, "3–4"),
    (4.5, "4–4.5"),
    (float("inf"), "4.5–5"),
]
TOP_N_POSITION = 10
