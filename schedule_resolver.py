"""
schedule_resolver.py
Calcula o próximo slot de publicação baseado em schedules.json.

Uso:
    from schedule_resolver import next_slot

    iso_utc = next_slot("bitcoinfacil", "tiktok")
    iso_utc = next_slot("pandapoints", "youtube", after=some_datetime)

next_slot() retorna string ISO 8601 UTC pronta para passar ao scheduler.add_job().
"""

import json
import os
import logging
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

_BASE_DIR       = os.path.dirname(__file__)
_SCHEDULES_PATH = os.path.join(_BASE_DIR, "schedules.json")
_JOBS_PATH      = os.path.join(_BASE_DIR, "jobs.json")

# ---------------------------------------------------------------------------
# Carregamento
# ---------------------------------------------------------------------------

def load_schedules() -> dict:
    """Lê e retorna schedules.json. Levanta FileNotFoundError se ausente."""
    with open(_SCHEDULES_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _load_pending_jobs() -> list[dict]:
    try:
        with open(_JOBS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return [j for j in data.get("jobs", []) if j.get("status") == "pending"]
    except FileNotFoundError:
        return []
    except Exception as e:
        logger.warning("Erro ao ler jobs.json: %s", e)
        return []


# ---------------------------------------------------------------------------
# Lógica central
# ---------------------------------------------------------------------------

def next_slot(
    channel: str,
    platform: str,
    after: datetime | None = None,
) -> str:
    """
    Retorna a próxima janela de publicação como string ISO 8601 UTC.

    Parâmetros:
        channel   — ex: "bitcoinfacil" | "pandapoints"
        platform  — ex: "tiktok" | "instagram" | "youtube"
        after     — datetime de referência (default: agora). Deve ter tzinfo.

    Retorna:
        String ISO 8601 UTC, ex: "2026-05-27T13:00:00+00:00"

    Levanta:
        KeyError  — canal ou plataforma não encontrados em schedules.json
        ValueError — nenhuma janela definida para o par canal+plataforma
    """
    schedules = load_schedules()
    tz        = ZoneInfo(schedules["timezone"])
    gap_h     = schedules.get("gap_hours", 23)

    channel_cfg  = schedules["channels"][channel]
    platform_windows = channel_cfg["schedule"][platform]   # lista de {weekday, time}

    if not platform_windows:
        raise ValueError(f"Nenhuma janela definida para {channel}/{platform}")

    if after is None:
        after = datetime.now(timezone.utc)

    # Converte referência para o fuso local do canal
    after_local = after.astimezone(tz)

    # Coleta horários de posts pendentes (canal+plataforma) para evitar colisão
    pending_slots = _pending_slots_for(channel, platform)

    # Itera pelos próximos 14 dias procurando o primeiro slot disponível
    for day_offset in range(14):
        candidate_date = (after_local + timedelta(days=day_offset)).date()

        for window in platform_windows:
            h, m = map(int, window["time"].split(":"))
            candidate = datetime(
                candidate_date.year, candidate_date.month, candidate_date.day,
                h, m, tzinfo=tz,
            )

            # Deve ser no futuro (pelo menos 5 min de margem)
            if candidate <= after_local + timedelta(minutes=5):
                continue

            # Deve ser no weekday correto
            if candidate.weekday() != window["weekday"]:
                continue

            # Não deve colidir com job pendente (gap_hours de distância)
            if _conflicts(candidate, pending_slots, gap_h):
                continue

            return candidate.astimezone(timezone.utc).isoformat()

    raise RuntimeError(
        f"Não foi possível encontrar slot livre em 14 dias para {channel}/{platform}"
    )


def next_slots_all(channel: str, after: datetime | None = None) -> dict[str, str]:
    """
    Retorna o próximo slot para TODAS as plataformas do canal.

    Retorna:
        {"tiktok": "2026-...", "instagram": "2026-...", "youtube": "2026-..."}
    """
    schedules    = load_schedules()
    channel_cfg  = schedules["channels"][channel]
    platforms    = channel_cfg.get("platforms", [])
    result       = {}

    for platform in platforms:
        try:
            result[platform] = next_slot(channel, platform, after=after)
        except Exception as e:
            logger.warning("Sem slot para %s/%s: %s", channel, platform, e)
            result[platform] = None

    return result


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _pending_slots_for(channel: str, platform: str) -> list[datetime]:
    """Retorna datetimes UTC de jobs pending para esse canal+plataforma."""
    slots = []
    for job in _load_pending_jobs():
        if job.get("channel") != channel:
            continue
        if platform not in job.get("platforms", []):
            continue
        try:
            dt = datetime.fromisoformat(job["scheduled_at"])
            slots.append(dt.astimezone(timezone.utc))
        except Exception:
            pass
    return slots


def _conflicts(candidate: datetime, pending: list[datetime], gap_hours: int) -> bool:
    """True se candidate está a menos de gap_hours de qualquer slot pendente."""
    gap = timedelta(hours=gap_hours)
    cand_utc = candidate.astimezone(timezone.utc)
    for p in pending:
        if abs(cand_utc - p) < gap:
            return True
    return False


# ---------------------------------------------------------------------------
# CLI rápida para testes
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    channel  = sys.argv[1] if len(sys.argv) > 1 else "bitcoinfacil"
    platform = sys.argv[2] if len(sys.argv) > 2 else "tiktok"

    try:
        slot = next_slot(channel, platform)
        print(f"Próximo slot  {channel}/{platform}:  {slot}")
    except Exception as e:
        print(f"Erro: {e}", file=sys.stderr)
        sys.exit(1)
