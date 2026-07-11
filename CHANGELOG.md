# Changelog

All notable changes to conduler are documented here.

---

## [Unreleased]

### Fixed
- **Duplicação de posts em restart**: `watcher.py` mantinha os arquivos já
  vistos apenas em memória (`seen`), então reiniciar o conduler fazia o
  watcher re-escanear `watch_input/` do zero e recriar jobs para vídeos
  já agendados. Corrigido movendo cada vídeo (e seu sidecar JSON) para
  `watch_input/processed/{channel}/` assim que os jobs são criados
  (`_archive_video` em `main.py`), tirando-o da pasta monitorada.
- **Sem dedup em `Scheduler.add_job`**: adicionada checagem que ignora
  criação de job duplicado quando já existe um job pending/running/done
  para o mesmo `video_path` + mesmo conjunto de `platforms`. Segunda
  camada de proteção contra duplicação, cobrindo também o bridge do
  rotman (`conduler_bridge.py`) e chamadas repetidas da API.

---

## [1.1] — 2026-05-05

### Added
- Rotman bridge integration — `conduler_bridge.py` in rotman now POSTs a job to
  `POST /api/jobs` automatically when a pipeline run completes; conduler requires
  no changes, the existing endpoint and scheduler handle it transparently

---

## [1.0] — 2026-04-11

### Added
- HTTP server on port 7071 (Python stdlib `http.server`, zero external dependencies)
- OAuth 2.0 flows for Instagram (Graph API v21), YouTube (Data API v3), and
  TikTok (Content Posting API v2) — all implemented via `urllib`, no third-party HTTP libs
- OAuth callback listener on port 7072 — temporary server spun up per auth flow
- `auth/tokens.json` — persists access tokens per platform (gitignored)
- `scheduler.py` — job queue with 15-second polling loop; publishes jobs when
  their scheduled time arrives
- `watcher.py` — monitors `watch_input/` folder for new video files
- `publisher_router.py` — dispatches jobs to the correct platform publisher
- `publishers/instagram.py` — Instagram Reels upload via Graph API (requires public URL)
- `publishers/youtube.py` — YouTube Shorts direct upload from local file path
- `publishers/tiktok.py` — TikTok video upload (requires approved app in developer portal)
- `config.py` — central configuration for credentials, folder paths, and ports
- `jobs.example.json` — sample job queue format reference
- Web UI at `http://127.0.0.1:7071` — Authentication, Schedule, and Queue tabs
- Full UI and README in English
