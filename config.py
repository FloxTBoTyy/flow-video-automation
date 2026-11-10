"""Configuración global para la automatización de Google Flow y TikTok."""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Directorios principales
BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "output_videos"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
DOWNLOADS_DIR = BASE_DIR / "downloads"
DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)

# Conexión CDP (Chrome DevTools Protocol)
CDP_PORT = int(os.getenv("CDP_PORT", "9222"))
CDP_URL = f"http://127.0.0.1:{CDP_PORT}"

# URLs de Google Flow
FLOW_URL = "https://flow.google.com"
FLOW_PROJECT_URL = os.getenv("FLOW_PROJECT_URL", "https://flow.google.com")

# URL de TikTok Studio
TIKTOK_UPLOAD_URL = "https://www.tiktok.com/tiktokstudio/upload?from=creator_center&tab=video"

# Diccionario genérico de episodios (para retrocompatibilidad)
EPISODES = {}
