import os
from dotenv import load_dotenv

load_dotenv()

# Telegram Bot Token
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
ADMIN_IDS = [int(id_str) for id_str in os.getenv("ADMIN_IDS", "123456789").split(",") if id_str.strip()]
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")

# Gemini Token
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# Subscription settings
SUBSCRIPTION_PRICE_UZS = 30000
SUBSCRIPTION_PRICE_STARS = 150 # example equivalent in stars
SUBSCRIPTION_DAYS = 30

CARD_NUMBER = os.getenv("CARD_NUMBER", "8600 0000 0000 0000")
CARD_HOLDER = os.getenv("CARD_HOLDER", "Ivan Ivanov")

# DB Path
DB_PATH = os.getenv("DB_PATH", "coach_database.db")
