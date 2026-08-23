"""
test_jobs_channel.py — confirms POST /api/jobs forwards 'channel' (and 'cta')
through to the stored job, and — since commit 421e716 documented the gap —
that omitting/misspelling 'channel' is now rejected outright instead of
silently falling back to '' (which used to produce utm_campaign='unknown'
at publish time).

Runs a real HTTPServer instance against a temp jobs.json so it never
touches the real production jobs.json. Run directly:

    python test_jobs_channel.py
"""

import json
import os
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from http.server import HTTPServer

import config
import main
from scheduler import Scheduler

TEST_PORT = 7099


def _request(method, path, body=None):
    url = f"http://127.0.0.1:{TEST_PORT}{path}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method,
                                  headers={"Content-Type": "application/json"} if data else {})
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def test_post_jobs_forwards_channel_and_cta():
    fd, tmp_jobs_path = tempfile.mkstemp(suffix=".json")
    os.close(fd)
    os.remove(tmp_jobs_path)  # Scheduler._load() handles FileNotFoundError → starts empty

    original_scheduler = main.scheduler
    original_jobs_file = config.JOBS_FILE
    config.JOBS_FILE = tmp_jobs_path
    main.scheduler = Scheduler(publisher_fn=lambda job: {p: {"ok": True, "url": "", "error": ""} for p in job["platforms"]})

    server = HTTPServer((config.HOST, TEST_PORT), main.Handler)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    time.sleep(0.3)  # let the server bind

    try:
        status, body = _request("POST", "/api/jobs", {
            "video_path":   "C:/fake/pandapoints_demo.mp4",
            "channel":      "pandapoints",
            "cta":          "create_wallet",
            "title":        "Demo video",
            "description":  "desc",
            "tags":         ["demo"],
            "platforms":    ["youtube"],
            "scheduled_at": "2099-01-01T00:00:00+00:00",
        })
        assert status == 201, f"POST /api/jobs failed: {status} {body}"
        job_id = body["id"]

        stored = main.scheduler.get_job(job_id)
        assert stored is not None, "Job not found after creation"
        assert stored["channel"] == "pandapoints", f"channel not forwarded: {stored}"
        assert stored["cta"] == "create_wallet", f"cta not forwarded: {stored}"
    finally:
        server.shutdown()
        server.server_close()
        main.scheduler = original_scheduler
        config.JOBS_FILE = original_jobs_file
        if os.path.exists(tmp_jobs_path):
            os.remove(tmp_jobs_path)


def test_post_jobs_requires_channel():
    """
    Regression test for the gap documented in commit 421e716: omitting
    'channel' must now be rejected with 400, not silently accepted with ''
    (which used to produce utm_campaign='unknown' at publish time).
    """
    fd, tmp_jobs_path = tempfile.mkstemp(suffix=".json")
    os.close(fd)
    os.remove(tmp_jobs_path)

    original_scheduler = main.scheduler
    original_jobs_file = config.JOBS_FILE
    config.JOBS_FILE = tmp_jobs_path
    main.scheduler = Scheduler(publisher_fn=lambda job: {p: {"ok": True, "url": "", "error": ""} for p in job["platforms"]})

    server = HTTPServer((config.HOST, TEST_PORT), main.Handler)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    time.sleep(0.3)

    try:
        status, body = _request("POST", "/api/jobs", {
            "video_path":   "C:/fake/no_channel.mp4",
            "platforms":    ["youtube"],
            "scheduled_at": "2099-01-01T00:00:00+00:00",
        })
        assert status == 400, f"expected 400 for missing channel, got: {status} {body}"
        assert "channel" in body.get("error", "").lower(), body
    finally:
        server.shutdown()
        server.server_close()
        main.scheduler = original_scheduler
        config.JOBS_FILE = original_jobs_file
        if os.path.exists(tmp_jobs_path):
            os.remove(tmp_jobs_path)


def test_post_jobs_rejects_unknown_channel():
    fd, tmp_jobs_path = tempfile.mkstemp(suffix=".json")
    os.close(fd)
    os.remove(tmp_jobs_path)

    original_scheduler = main.scheduler
    original_jobs_file = config.JOBS_FILE
    config.JOBS_FILE = tmp_jobs_path
    main.scheduler = Scheduler(publisher_fn=lambda job: {p: {"ok": True, "url": "", "error": ""} for p in job["platforms"]})

    server = HTTPServer((config.HOST, TEST_PORT), main.Handler)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    time.sleep(0.3)

    try:
        status, body = _request("POST", "/api/jobs", {
            "video_path":   "C:/fake/bogus_channel.mp4",
            "channel":      "not_a_real_channel",
            "platforms":    ["youtube"],
            "scheduled_at": "2099-01-01T00:00:00+00:00",
        })
        assert status == 400, f"expected 400 for unknown channel, got: {status} {body}"
    finally:
        server.shutdown()
        server.server_close()
        main.scheduler = original_scheduler
        config.JOBS_FILE = original_jobs_file
        if os.path.exists(tmp_jobs_path):
            os.remove(tmp_jobs_path)


ALL_TESTS = [
    test_post_jobs_forwards_channel_and_cta,
    test_post_jobs_requires_channel,
    test_post_jobs_rejects_unknown_channel,
]


def run():
    passed, failed = 0, 0
    for t in ALL_TESTS:
        try:
            t()
            print(f"PASS  {t.__name__}")
            passed += 1
        except AssertionError as e:
            print(f"FAIL  {t.__name__}: {e}")
            failed += 1
        except Exception as e:
            print(f"ERROR {t.__name__}: {e!r}")
            failed += 1
    print(f"\n{passed} passed, {failed} failed")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    run()
