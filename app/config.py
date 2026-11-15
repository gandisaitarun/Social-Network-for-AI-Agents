import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DEFAULT_DB_PATH = DATA_DIR / "social_network.db"

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    f"sqlite:///{DEFAULT_DB_PATH}",
)

WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "dev-platform-secret")
EMBEDDING_DIMENSION = int(os.getenv("EMBEDDING_DIMENSION", "64"))
PGVECTOR_ENABLED = DATABASE_URL.startswith("postgres")
