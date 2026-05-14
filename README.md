# conduler

Local scheduler for publishing short videos to Instagram Reels, YouTube Shorts and TikTok.

Companion project to [Rotman](../rotman) — Rotman generates the video, conduler schedules and publishes it.

## Requirements

- Python 3.8+
- No external dependencies (stdlib only)

## Getting started

### 1. Set credentials

Edit `config.py` or set environment variables before starting:

```
INSTAGRAM_APP_ID        INSTAGRAM_APP_SECRET
YOUTUBE_CLIENT_ID       YOUTUBE_CLIENT_SECRET
TIKTOK_CLIENT_KEY       TIKTOK_CLIENT_SECRET
```

### 2. Start the server

```bash
python main.py
```

Open: http://127.0.0.1:7071

### 3. Authenticate platforms

Go to the **Authentication** tab and click **Connect** for each platform.
The OAuth flow opens in the browser and saves the token to `auth/tokens.json` (gitignored).

### 4. Schedule a video

- Drop a video into the watch folder (default: `watch_input/`, configurable via `WATCH_FOLDER`)
- In the **Schedule** tab, select the file, fill in title/description and pick a publish time
- The scheduler checks the queue every 15 seconds and publishes when the time comes

## Project structure

```
conduler/
├── main.py              # HTTP server + entrypoint
├── watcher.py           # watches the video input folder
├── scheduler.py         # job queue + scheduling engine
├── publisher_router.py  # dispatches jobs to each platform
├── config.py            # central configuration
├── publishers/
│   ├── instagram.py     # Graph API v21
│   ├── youtube.py       # Data API v3
│   └── tiktok.py        # Content Posting API v2
├── auth/
│   └── oauth_flow.py    # OAuth flow via urllib
├── ui/
│   └── index.html       # web interface
├── watch_input/         # monitored folder (gitignored)
└── jobs.example.json    # sample jobs.json
```

## Ports

| Service                      | Port |
|------------------------------|------|
| conduler (UI / API)          | 7071 |
| Rotman                       | 7070 |
| OAuth callback (temporary)   | 7072 |

## API notes

**Instagram** requires the video to be available at a public URL at publish time (the `video_url` field on the job). For local testing, use ngrok or a temporary hosting service.

**YouTube** uploads directly from the local file — no public URL needed.

**TikTok** requires app approval through the developer portal. The flow is fully implemented but only works with an approved app.

## Rotman integration

Rotman notifies conduler automatically via `conduler_bridge.py` when a pipeline
run completes. No changes are needed on the conduler side — the bridge calls
conduler's existing `POST /api/jobs` endpoint.

| Env var                  | Default                    | Description                                          |
|--------------------------|----------------------------|------------------------------------------------------|
| `CONDULER_URL`           | `http://127.0.0.1:7071`    | Base URL of this conduler instance                   |
| `CONDULER_DELAY_MINUTES` | `30`                       | Minutes from pipeline completion before publishing   |

Channel-to-platform mapping (defined in `conduler_bridge.py`):

| Channel         | Platforms                  |
|-----------------|----------------------------|
| bitcoinfacil    | YouTube, Instagram         |
| pandapoints     | YouTube, TikTok            |

If conduler is unreachable the pipeline still completes — a warning is logged
and the video remains on disk for manual scheduling via the UI.

## Roadmap

- [x] Rotman integration — rotman's `conduler_bridge.py` POSTs finished videos to
      `POST /api/jobs` on pipeline completion (HTTP handoff, not shared folder)
- [ ] Direct upload support for Instagram (no public URL required)
- [ ] Automatic token refresh on expiry
- [ ] Webhook notification after publishing
