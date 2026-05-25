"""
main.py
Ponto de entrada do conduler.
- Sobe o servidor HTTP na porta 7071
- Inicia o FolderWatcher em thread separada
- Inicia o Scheduler em thread separada
"""

import json
import logging
import os
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer

import config
from watcher import FolderWatcher
from scheduler import Scheduler
from publisher_router import publish_job
from schedule_resolver import next_slot, load_schedules

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("main")

scheduler = Scheduler(publisher_fn=publish_job)


# ---------------------------------------------------------------------------
# Helpers de auto-agendamento
# ---------------------------------------------------------------------------

def _parse_channel(filename: str) -> str | None:
    """
    Extrai o canal do nome do arquivo.
    Convenção: {channel}_{qualquer_coisa}.ext
    Ex: bitcoinfacil_20260525_hook.mp4  →  "bitcoinfacil"
        pandapoints_defi-intro.mp4      →  "pandapoints"
    Retorna None se o prefixo não bater com nenhum canal conhecido.
    """
    try:
        schedules   = load_schedules()
        known       = set(schedules["channels"].keys())
        stem        = os.path.splitext(filename)[0]           # remove extensão
        prefix      = stem.split("_")[0].lower()              # primeiro segmento
        return prefix if prefix in known else None
    except Exception:
        return None


def _read_sidecar(video_path: str) -> dict:
    """
    Lê metadados opcionais de um sidecar JSON com mesmo stem do vídeo.
    Ex: bitcoinfacil_hook.mp4  →  bitcoinfacil_hook.json
    Campos suportados: title, description, tags (lista de strings).
    """
    stem     = os.path.splitext(video_path)[0]
    sidecar  = stem + ".json"
    if not os.path.exists(sidecar):
        return {}
    try:
        with open(sidecar, "r", encoding="utf-8") as f:
            data = json.load(f)
        logger.info("Sidecar lido: %s", sidecar)
        return data
    except Exception as e:
        logger.warning("Erro ao ler sidecar %s: %s", sidecar, e)
        return {}


# ------------------------------------------------------------------
# Callback do Watcher: novo vídeo detectado
# ------------------------------------------------------------------

def on_new_video(filepath: str):
    """
    Chamado pelo watcher quando um novo vídeo aparece na pasta.
    Auto-agenda um job por plataforma no próximo slot ótimo do canal.
    """
    filename = os.path.basename(filepath)
    channel  = _parse_channel(filename)

    if not channel:
        logger.warning(
            "Auto-agendamento ignorado — não foi possível identificar o canal em '%s'. "
            "Use o prefixo do canal no nome do arquivo: {canal}_{slug}.mp4",
            filename,
        )
        return

    meta = _read_sidecar(filepath)
    title       = meta.get("title", "")
    description = meta.get("description", "")
    tags        = meta.get("tags", [])

    schedules        = load_schedules()
    channel_cfg      = schedules["channels"][channel]
    platforms        = channel_cfg.get("platforms", [])

    created, skipped = [], []

    for platform in platforms:
        try:
            slot    = next_slot(channel, platform)
            job_id  = scheduler.add_job(
                video_path   = filepath,
                platforms    = [platform],
                scheduled_at = slot,
                title        = title,
                description  = description,
                tags         = tags,
                channel      = channel,
            )
            created.append(f"{platform}@{slot}")
            logger.info(
                "Job auto-criado  [%s]  canal=%s  plataforma=%s  slot=%s",
                job_id[:8], channel, platform, slot,
            )
        except Exception as e:
            skipped.append(platform)
            logger.error(
                "Falha ao agendar %s/%s para '%s': %s",
                channel, platform, filename, e,
            )

    if created:
        logger.info(
            "Auto-agendamento concluído para '%s' → %s",
            filename, " | ".join(created),
        )
    if skipped:
        logger.warning("Plataformas sem slot disponível: %s", skipped)


# ------------------------------------------------------------------
# Rotas HTTP
# ------------------------------------------------------------------

def _json_response(handler, status, data):
    body = json.dumps(data, ensure_ascii=False).encode()
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.end_headers()
    handler.wfile.write(body)


def _html_response(handler, html: str):
    body = html.encode()
    handler.send_response(200)
    handler.send_header("Content-Type", "text/html; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


class Handler(BaseHTTPRequestHandler):

    def log_message(self, fmt, *args):
        logger.debug(fmt, *args)

    def _read_body(self):
        length = int(self.headers.get("Content-Length", 0))
        return json.loads(self.rfile.read(length)) if length else {}

    # --- OPTIONS (CORS preflight) ---
    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin",  "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    # --- GET ---
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path   = parsed.path.rstrip("/")
        params = urllib.parse.parse_qs(parsed.query)

        if path in ("", "/"):
            ui_path = os.path.join(os.path.dirname(__file__), "ui", "index.html")
            with open(ui_path, "r", encoding="utf-8") as f:
                _html_response(self, f.read())
            return

        if path == "/api/jobs":
            status = params.get("status", [None])[0]
            _json_response(self, 200, {"jobs": scheduler.list_jobs(status=status)})
            return

        if path.startswith("/api/jobs/"):
            job_id = path.split("/api/jobs/")[1]
            job    = scheduler.get_job(job_id)
            if job:
                _json_response(self, 200, job)
            else:
                _json_response(self, 404, {"error": "Job não encontrado."})
            return

        if path == "/api/watch_folder":
            files = []
            try:
                for name in os.listdir(config.WATCH_FOLDER):
                    ext = os.path.splitext(name)[1].lower()
                    if ext in config.VIDEO_EXTENSIONS:
                        files.append(name)
            except OSError:
                pass
            _json_response(self, 200, {"folder": config.WATCH_FOLDER, "files": files})
            return

        if path == "/api/auth/status":
            from auth.oauth_flow import load_tokens
            tokens = load_tokens()
            status = {p: bool(tokens.get(p)) for p in config.PLATFORMS}
            _json_response(self, 200, status)
            return

        _json_response(self, 404, {"error": "Rota não encontrada."})

    # --- POST ---
    def do_POST(self):
        path = self.path.rstrip("/")

        # Criar job
        if path == "/api/jobs":
            data = self._read_body()
            try:
                job_id = scheduler.add_job(
                    video_path   = data["video_path"],
                    platforms    = data["platforms"],
                    scheduled_at = data["scheduled_at"],
                    title        = data.get("title", ""),
                    description  = data.get("description", ""),
                    tags         = data.get("tags", []),
                )
                _json_response(self, 201, {"id": job_id})
            except (KeyError, ValueError) as e:
                _json_response(self, 400, {"error": str(e)})
            return

        # Iniciar OAuth
        if path.startswith("/api/auth/"):
            platform = path.split("/api/auth/")[1]
            _json_response(self, 202, {"message": f"Iniciando OAuth para {platform}. Verifique o browser."})

            def _run_oauth():
                from auth import oauth_flow
                from config import (
                    INSTAGRAM_APP_ID, INSTAGRAM_APP_SECRET,
                    YOUTUBE_CLIENT_ID, YOUTUBE_CLIENT_SECRET,
                    TIKTOK_CLIENT_KEY, TIKTOK_CLIENT_SECRET,
                )
                try:
                    if platform == "instagram":
                        oauth_flow.authorize_instagram(INSTAGRAM_APP_ID, INSTAGRAM_APP_SECRET)
                    elif platform == "youtube":
                        oauth_flow.authorize_youtube(YOUTUBE_CLIENT_ID, YOUTUBE_CLIENT_SECRET)
                    elif platform == "tiktok":
                        oauth_flow.authorize_tiktok(TIKTOK_CLIENT_KEY, TIKTOK_CLIENT_SECRET)
                    else:
                        logger.warning("Plataforma desconhecida: %s", platform)
                except Exception as e:
                    logger.error("Erro OAuth %s: %s", platform, e)

            threading.Thread(target=_run_oauth, daemon=True).start()
            return

        _json_response(self, 404, {"error": "Rota não encontrada."})

    # --- DELETE ---
    def do_DELETE(self):
        path = self.path.rstrip("/")
        if path.startswith("/api/jobs/"):
            job_id = path.split("/api/jobs/")[1]
            ok = scheduler.cancel_job(job_id)
            if ok:
                _json_response(self, 200, {"cancelled": job_id})
            else:
                _json_response(self, 400, {"error": "Job não pode ser cancelado (não existe ou não está pending)."})
            return
        _json_response(self, 404, {"error": "Rota não encontrada."})


# ------------------------------------------------------------------
# Entrypoint
# ------------------------------------------------------------------

def main():
    watcher = FolderWatcher(on_new_video=on_new_video)

    t_watcher   = threading.Thread(target=watcher.run_forever,   daemon=True, name="watcher")
    t_scheduler = threading.Thread(target=scheduler.run_forever, daemon=True, name="scheduler")
    t_watcher.start()
    t_scheduler.start()

    server = HTTPServer((config.HOST, config.PORT), Handler)
    logger.info("conduler rodando em http://%s:%d", config.HOST, config.PORT)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Encerrando...")
        watcher.stop()
        scheduler.stop()
        server.server_close()


if __name__ == "__main__":
    main()
