#!/usr/bin/env python3
"""GradeAI worker.

Runs on your computer next to GradeAI. `npm run model:connect` starts it after opening an SSH
tunnel to the model job on Fir. It takes queued files from GradeAI, has the fine-tuned model
grade them through the tunnel, and sends the grades back.

Standard library only: no pip installs.

Environment (npm run model:connect sets these; extra settings can go in .env):
  GRADEAI_URL            http://127.0.0.1:8080
  GRADEAI_WORKER_TOKEN   WORKER_TOKEN from .env
  VLLM_URL               http://127.0.0.1:<tunnel port>/v1
  VLLM_API_KEY           key of the current model job
  MODEL_NAME             name the model job serves
  FIR_JOB_ID, FIR_NODE, FIR_JOB_END   the Fir job (end as Unix seconds), shown in GradeAI
  WORKER_CONCURRENCY     files graded at once (default 8)
  JSON_MODE              json_schema | guided_json | none  (default json_schema)
  ENABLE_THINKING        true to let Qwen3-family models reason before answering (default false)
  STOP_BEFORE_END_SEC    stop taking new files this long before the job ends (default 600)
"""

import json
import os
import signal
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

VERSION = "1.0.0"
SERVER = os.environ["GRADEAI_URL"].rstrip("/")
TOKEN = os.environ["GRADEAI_WORKER_TOKEN"]
VLLM = os.environ.get("VLLM_URL", "http://127.0.0.1:8000/v1").rstrip("/")
VLLM_KEY = os.environ.get("VLLM_API_KEY", "")
MODEL = os.environ.get("MODEL_NAME", "gradeai")
CONCURRENCY = max(1, int(os.environ.get("WORKER_CONCURRENCY", "8")))
JSON_MODE = os.environ.get("JSON_MODE", "json_schema")
STOP_BEFORE_END = int(os.environ.get("STOP_BEFORE_END_SEC", "600"))
# Qwen3-family models "think" before answering unless told not to. Grading wants the JSON answer only.
ENABLE_THINKING = os.environ.get("ENABLE_THINKING", "false").lower() in ("1", "true", "yes")
JOB_ID = os.environ.get("FIR_JOB_ID") or os.environ.get("SLURM_JOB_ID")
NODE = os.environ.get("FIR_NODE") or socket.gethostname()

stopping = threading.Event()
model_up = threading.Event()  # cleared when vLLM can't be reached (crashed, or an SSH tunnel dropped)
active = 0
active_lock = threading.Lock()


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def http_json(method, url, body=None, headers=None, timeout=60):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    req.add_header("User-Agent", f"gradeai-worker/{VERSION}")
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read()
        return json.loads(raw) if raw else {}


def server(path, body):
    return http_json("POST", f"{SERVER}/api/worker/{path}", body, {"Authorization": f"Bearer {TOKEN}"}, timeout=60)


def job_end_epoch_ms():
    """When the Fir job ends, so GradeAI can show it and we stop taking files in time."""
    for name in ("FIR_JOB_END", "SLURM_JOB_END_TIME"):
        v = os.environ.get(name, "")
        if v.isdigit():
            return int(v) * 1000
    if not os.environ.get("SLURM_JOB_ID"):
        return None
    try:
        out = subprocess.run(["squeue", "-h", "-j", JOB_ID, "-o", "%e"], capture_output=True, text=True, timeout=20).stdout.strip()
        return int(datetime.strptime(out, "%Y-%m-%dT%H:%M:%S").timestamp() * 1000)
    except Exception:
        return None


END_AT = job_end_epoch_ms()


def status_body():
    return {"model": MODEL, "slurmJobId": JOB_ID, "node": NODE, "endsAt": END_AT, "version": VERSION}


def wait_for_vllm(limit_sec=1800):
    log("waiting for the model to finish loading on Fir (a few minutes after the job starts)…")
    t0 = time.time()
    while time.time() - t0 < limit_sec and not stopping.is_set():
        try:
            r = http_json("GET", f"{VLLM}/models", headers={"Authorization": f"Bearer {VLLM_KEY}"} if VLLM_KEY else None, timeout=10)
            names = [m.get("id") for m in r.get("data", [])]
            log("model is up:", ", ".join(names))
            return True
        except Exception:
            time.sleep(5)
    return False


def model_reachable():
    try:
        http_json("GET", f"{VLLM}/models", headers={"Authorization": f"Bearer {VLLM_KEY}"} if VLLM_KEY else None, timeout=10)
        return True
    except Exception:
        return False


def is_connection_error(e):
    return isinstance(e, (urllib.error.URLError, ConnectionError, TimeoutError, socket.timeout)) and not isinstance(e, urllib.error.HTTPError)


def chat(task, structured=True):
    body = {
        "model": MODEL,
        "messages": task["messages"],
        "temperature": task.get("temperature", 0),
        "max_tokens": task.get("max_tokens", 1500),
        "chat_template_kwargs": {"enable_thinking": ENABLE_THINKING},
    }
    if ENABLE_THINKING:
        body["max_tokens"] = body["max_tokens"] + 4000  # room for the reasoning before the JSON
    if structured and task.get("json_schema") and JSON_MODE == "json_schema":
        body["response_format"] = {"type": "json_schema", "json_schema": {"name": task["kind"], "schema": task["json_schema"]}}
    elif structured and task.get("json_schema") and JSON_MODE == "guided_json":
        body["guided_json"] = task["json_schema"]
    headers = {"Authorization": f"Bearer {VLLM_KEY}"} if VLLM_KEY else None
    r = http_json("POST", f"{VLLM}/chat/completions", body, headers, timeout=900)
    return r["choices"][0]["message"]["content"] or ""


def post_result(body):
    for attempt in range(5):
        try:
            server("result", body)
            return
        except Exception as e:
            log(f"could not post result ({e}); retrying")
            time.sleep(2 * (attempt + 1))
    log("gave up posting result for", body.get("id"), "- the server will hand it out again later")


def run_task(task):
    global active
    started = time.time()
    try:
        try:
            content = chat(task, structured=True)
        except urllib.error.HTTPError as e:
            detail = e.read().decode(errors="replace")[:500]
            if e.code == 400 and JSON_MODE != "none" and "context" not in detail.lower():
                log(f"structured output refused ({detail[:120]}); retrying without it")
                content = chat(task, structured=False)
            else:
                raise RuntimeError(f"vLLM HTTP {e.code}: {detail}")
        post_result({"id": task["id"], "ok": True, "content": content, "model": MODEL})
        log(f"done {task['kind']} {task['id']} in {time.time() - started:.1f}s")
    except Exception as e:
        if is_connection_error(e):
            # The model is unreachable, not the file's fault: hand it back and pause.
            model_up.clear()
            log(f"model unreachable ({e}); returning {task['id']} to the queue")
            try:
                server("release", {"id": task["id"]})
            except Exception:
                pass  # the server returns it to the queue when the lease expires
            return
        msg = str(e)
        if "maximum context length" in msg.lower() or "context length" in msg.lower():
            msg = "The submission is too long for the model's context window. Lower 'Max submission length' in GradeAI Settings or raise MAX_MODEL_LEN."
        log(f"failed {task['id']}: {msg[:200]}")
        post_result({"id": task["id"], "ok": False, "error": msg[:1000], "model": MODEL})
    finally:
        with active_lock:
            active -= 1


def heartbeat_loop():
    while not stopping.is_set():
        if not model_up.is_set():
            stopping.wait(5)
            continue
        try:
            s = server("heartbeat", status_body())
            if s.get("waiting"):
                log(f"queue: {s['waiting']} waiting, {s.get('grading', 0)} grading")
        except Exception as e:
            log(f"heartbeat failed: {e}")
        stopping.wait(20)


def near_end():
    return END_AT is not None and time.time() * 1000 > END_AT - STOP_BEFORE_END * 1000


def main():
    global active
    signal.signal(signal.SIGTERM, lambda *_: (log("SIGTERM: finishing current tasks"), stopping.set()))
    signal.signal(signal.SIGINT, lambda *_: stopping.set())
    log(f"GradeAI worker {VERSION} · job {JOB_ID} on {NODE} · model {MODEL} · server {SERVER}")
    if not wait_for_vllm():
        log("the model did not answer within 30 minutes; check it with: npm run model:log")
        sys.exit(1)
    try:
        server("heartbeat", status_body())
    except urllib.error.HTTPError as e:
        log(f"GradeAI refused the worker (HTTP {e.code}). Restart GradeAI (npm start) after running npm run setup, so both use the same WORKER_TOKEN.")
        sys.exit(1)
    except Exception as e:
        log(f"cannot reach GradeAI at {SERVER} ({e}). Is it running? Start it with: npm start")
        sys.exit(1)
    model_up.set()
    threading.Thread(target=heartbeat_loop, daemon=True).start()

    idle = 2
    with ThreadPoolExecutor(max_workers=CONCURRENCY) as pool:
        while not stopping.is_set():
            if near_end():
                log("the Fir job is about to end: no new files")
                break
            if not model_up.is_set():
                # Stop taking work (GradeAI shows the model offline) until vLLM answers again.
                if model_reachable():
                    log("model reachable again; resuming")
                    model_up.set()
                else:
                    stopping.wait(10)
                    continue
            free = CONCURRENCY - active
            if free <= 0:
                time.sleep(0.5)
                continue
            try:
                tasks = server("claim", {**status_body(), "max": free}).get("tasks", [])
            except Exception as e:
                log(f"claim failed: {e}")
                stopping.wait(10)
                continue
            if not tasks:
                stopping.wait(idle)
                idle = min(15, idle + 2)
                continue
            idle = 2
            for t in tasks:
                with active_lock:
                    active += 1
                pool.submit(run_task, t)
        log("waiting for running tasks…")
    stopping.set()
    log("worker stopped")


if __name__ == "__main__":
    main()
