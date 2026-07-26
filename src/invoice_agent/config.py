import os
from pathlib import Path
from dotenv import load_dotenv

PROJECT_ROOT = (
    Path(__file__).resolve().parents[2]
)  # src/invoice_agent/ -> src/ -> repo root

# LOCAL STORAGE FOR PROJECT SCOPE, NO S3/R2
UPLOADS_DIR = PROJECT_ROOT / "data" / "uploads"
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
MAX_CONCURRENCY = 16

load_dotenv(PROJECT_ROOT / ".env")
VLLM_BASE_URL = os.environ.get("VLLM_BASE_URL")
VLLM_API_KEY = os.environ.get("VLLM_API_KEY")
SPECIALIST_MODEL = os.environ.get("SPECIALIST_MODEL", "qwen3-vl-fullds-merged-r8")
FRONTIER_MODEL = os.environ.get("FRONTIER_MODEL", "claude-haiku-4-5-20251001")

REDIS_HOST = os.environ.get("REDIS_HOST")
REDIS_PORT = os.environ.get("REDIS_PORT")
