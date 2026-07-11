"""
scheduler.py
Gerencia a fila de jobs de publicação.
Cada job representa um vídeo a ser postado em uma ou mais plataformas
em um horário agendado.
"""

import json
import uuid
import logging
import threading
import time
from datetime import datetime, timezone
from config import JOBS_FILE, PLATFORMS

logger = logging.getLogger(__name__)

# Status possíveis de um job
STATUS_PENDING   = "pending"    # aguardando horário
STATUS_RUNNING   = "running"    # publicando agora
STATUS_DONE      = "done"       # publicado com sucesso
STATUS_FAILED    = "failed"     # erro em pelo menos uma plataforma
STATUS_CANCELLED = "cancelled"  # cancelado pelo usuário


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


class Scheduler:
    def __init__(self, publisher_fn):
        """
        publisher_fn(job) -> dict {platform: {"ok": bool, "url": str, "error": str}}
        """
        self.publisher_fn = publisher_fn
        self._lock         = threading.Lock()
        self._jobs         = {}   # id -> job dict
        self._running      = False
        self._load()

    # ------------------------------------------------------------------
    # Persistência
    # ------------------------------------------------------------------

    def _load(self):
        try:
            with open(JOBS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._jobs = {j["id"]: j for j in data.get("jobs", [])}
            logger.info("Jobs carregados: %d", len(self._jobs))
        except FileNotFoundError:
            self._jobs = {}
        except Exception as e:
            logger.error("Erro ao carregar jobs.json: %s", e)
            self._jobs = {}

    def _save(self):
        try:
            with open(JOBS_FILE, "w", encoding="utf-8") as f:
                json.dump({"jobs": list(self._jobs.values())}, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error("Erro ao salvar jobs.json: %s", e)

    # ------------------------------------------------------------------
    # CRUD de jobs
    # ------------------------------------------------------------------

    def add_job(self, video_path, platforms, scheduled_at, title="", description="", tags=None, channel=""):
        """
        Cria um novo job e retorna seu ID.
        scheduled_at: string ISO 8601 UTC  ex: "2025-08-01T18:00:00+00:00"
        platforms: lista de strings, ex: ["instagram", "youtube"]
        """
        invalid = [p for p in platforms if p not in PLATFORMS]
        if invalid:
            raise ValueError(f"Plataformas inválidas: {invalid}")

        # Dedup: evita criar um job duplicado para o mesmo vídeo + mesmo
        # conjunto de plataformas (protege contra re-scans do watcher,
        # reenvios do bridge do rotman, ou chamadas repetidas da API).
        with self._lock:
            for existing in self._jobs.values():
                if (
                    existing["video_path"] == video_path
                    and existing["platforms"] == platforms
                    and existing["status"] in (STATUS_PENDING, STATUS_RUNNING, STATUS_DONE)
                ):
                    logger.info(
                        "Job duplicado ignorado para '%s' [%s] — já existe %s (status=%s)",
                        video_path, platforms, existing["id"][:8], existing["status"],
                    )
                    return existing["id"]

        job = {
            "id":           str(uuid.uuid4()),
            "channel":      channel,
            "video_path":   video_path,
            "title":        title,
            "description":  description,
            "tags":         tags or [],
            "platforms":    platforms,
            "scheduled_at": scheduled_at,
            "status":       STATUS_PENDING,
            "created_at":   _now_iso(),
            "results":      {},   # plataforma -> {ok, url, error}
        }

        with self._lock:
            self._jobs[job["id"]] = job
            self._save()

        logger.info("Job criado: %s  [%s]  → %s", job["id"][:8], scheduled_at, platforms)
        return job["id"]

    def cancel_job(self, job_id):
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return False
            if job["status"] != STATUS_PENDING:
                return False
            job["status"] = STATUS_CANCELLED
            self._save()
        return True

    def list_jobs(self, status=None):
        with self._lock:
            jobs = list(self._jobs.values())
        if status:
            jobs = [j for j in jobs if j["status"] == status]
        return sorted(jobs, key=lambda j: j["scheduled_at"])

    def get_job(self, job_id):
        with self._lock:
            return self._jobs.get(job_id)

    # ------------------------------------------------------------------
    # Engine de agendamento
    # ------------------------------------------------------------------

    def _due_jobs(self):
        now = datetime.now(timezone.utc).isoformat()
        with self._lock:
            return [
                j for j in self._jobs.values()
                if j["status"] == STATUS_PENDING and j["scheduled_at"] <= now
            ]

    def _process(self, job):
        job_id = job["id"]
        logger.info("Publicando job %s...", job_id[:8])

        with self._lock:
            self._jobs[job_id]["status"] = STATUS_RUNNING
            self._save()

        try:
            results = self.publisher_fn(job)
        except Exception as e:
            results = {p: {"ok": False, "url": "", "error": str(e)} for p in job["platforms"]}

        all_ok = all(r.get("ok") for r in results.values())

        with self._lock:
            self._jobs[job_id]["results"]    = results
            self._jobs[job_id]["status"]     = STATUS_DONE if all_ok else STATUS_FAILED
            self._jobs[job_id]["finished_at"] = _now_iso()
            self._save()

        logger.info("Job %s → %s | resultados: %s", job_id[:8], self._jobs[job_id]["status"], results)

    def run_forever(self):
        self._running = True
        logger.info("Scheduler iniciado.")
        while self._running:
            for job in self._due_jobs():
                t = threading.Thread(target=self._process, args=(job,), daemon=True)
                t.start()
            time.sleep(15)

    def stop(self):
        self._running = False
