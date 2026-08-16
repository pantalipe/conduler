"""
test_jobs_channel.py — confirms POST /api/jobs forwards 'channel' through to
the stored job (regression test for the gap where manually-created jobs
had no channel, so utm_campaign fell back to 'unknown' at publish time).

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


def test_post_jobs_forwards_channel():
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
    finally:
        server.shutdown()
        server.server_close()
        main.scheduler = original_scheduler
        config.JOBS_FILE = original_jobs_file
        if os.path.exists(tmp_jobs_path):
            os.remove(tmp_jobs_path)


def test_post_jobs_channel_defaults_empty_when_omitted():
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
        assert status == 201, f"POST /api/jobs failed: {status} {body}"
        stored = main.scheduler.get_job(body["id"])
        assert stored["channel"] == "", f"expected empty channel, got: {stored}"
    finally:
        server.shutdown()
        server.server_close()
        main.scheduler = original_scheduler
        config.JOBS_FILE = original_jobs_file
        if os.path.exists(tmp_jobs_path):
            os.remove(tmp_jobs_path)


ALL_TESTS = [
    test_post_jobs_forwards_channel,
    test_post_jobs_channel_defaults_empty_when_omitted,
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
