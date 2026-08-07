import os

# --- Servidor ---
HOST = "127.0.0.1"
PORT = 7071

# --- Pasta monitorada (saída do Rotman) ---
WATCH_FOLDER = os.environ.get(
    "WATCH_FOLDER",
    os.path.join(os.path.dirname(__file__), "watch_input")
)
POLL_INTERVAL = 10  # segundos entre cada varredura

# Pasta para onde vídeos já agendados são movidos, para que o watcher
# nunca os reprocesse após um restart (watch_input é sempre escaneado
# do zero — "visto" precisa ser persistido movendo o arquivo, não
# apenas guardado em memória).
PROCESSED_FOLDER = os.path.join(WATCH_FOLDER, "processed")

# --- Extensões de vídeo aceitas ---
VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv"}

# --- Persistência ---
BASE_DIR = os.path.dirname(__file__)
JOBS_FILE   = os.path.join(BASE_DIR, "jobs.json")
TOKENS_FILE = os.path.join(BASE_DIR, "auth", "tokens.json")

# --- OAuth redirect (usado no fluxo de autorização local) ---
OAUTH_REDIRECT_PORT = 7072
OAUTH_REDIRECT_URI  = f"http://localhost:{OAUTH_REDIRECT_PORT}/callback"

# --- Plataformas disponíveis ---
PLATFORMS = ["instagram", "youtube", "tiktok"]

# --- Link da dapp usado nas descrições publicadas (com UTM, ver utm.py) ---
DAPP_BASE_URL = os.environ.get("DAPP_BASE_URL", "https://pandapointscoin.com")

# --- Credenciais OAuth (preencher após criar apps nas plataformas) ---
# Instagram / Facebook
INSTAGRAM_APP_ID     = os.environ.get("INSTAGRAM_APP_ID", "")
INSTAGRAM_APP_SECRET = os.environ.get("INSTAGRAM_APP_SECRET", "")

# YouTube / Google
YOUTUBE_CLIENT_ID     = os.environ.get("YOUTUBE_CLIENT_ID", "")
YOUTUBE_CLIENT_SECRET = os.environ.get("YOUTUBE_CLIENT_SECRET", "")

# TikTok
TIKTOK_CLIENT_KEY    = os.environ.get("TIKTOK_CLIENT_KEY", "")
TIKTOK_CLIENT_SECRET = os.environ.get("TIKTOK_CLIENT_SECRET", "")
