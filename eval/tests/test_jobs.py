"""Tests for eval/jobs/run_eval.sh and eval/jobs/preflight.py.

Nothing here touches Fir, SLURM, a GPU or a real model. The shell tests run the job script in a
fake environment: stub `openai` and `torch` packages, a stub `nvidia-smi`, and a fake `vllm` that
serves an OpenAI-style API on 127.0.0.1 and grades every case with its draft labels.
"""

import importlib.util
import json
import os
import shlex
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from eval import backends, dataset
from eval.jobs import preflight
from eval.tests import test_set_guard

REPO = dataset.REPO
SCRIPT = REPO / "eval" / "jobs" / "run_eval.sh"

setUpModule, tearDownModule = test_set_guard()


def eval_files():
    return sorted(str(p.relative_to(REPO)) for p in (REPO / "eval").rglob("*")
                  if p.is_file() and "__pycache__" not in p.parts)


# --------------------------------------------------------------------------- fake cluster

OPENAI_STUB = '''
import json, urllib.request
from types import SimpleNamespace as NS


class OpenAI:
    def __init__(self, base_url, api_key=None, max_retries=2, timeout=None):
        self.base_url, self.max_retries, self.timeout = base_url.rstrip("/"), max_retries, timeout
        self.chat = NS(completions=NS(create=self._create))

    def _create(self, model, messages, extra_body=None, **kwargs):
        body = json.dumps({"model": model, "messages": messages, **kwargs, **(extra_body or {})}).encode()
        req = urllib.request.Request(self.base_url + "/chat/completions", data=body,
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=self.timeout) as r:
            d = json.loads(r.read())
        c = d["choices"][0]
        return NS(choices=[NS(message=NS(content=c["message"]["content"], reasoning_content=None),
                              finish_reason=c["finish_reason"])], usage=None, model=d["model"])
'''

TORCH_STUB = '''
import os


class cuda:
    @staticmethod
    def is_available():
        return os.environ.get("FAKE_CUDA", "1") == "1"

    @staticmethod
    def get_device_name(i=0):
        return "Fake GPU"
'''

FAKE_VLLM = '''
import http.server, json, os, sys, time

def log(record):
    with open(os.environ["FAKE_VLLM_LOG"], "a") as f:
        f.write(json.dumps(record) + "\\n")

with open(os.environ["FAKE_VLLM_PIDFILE"], "w") as f:
    f.write(str(os.getpid()))
log({"argv": sys.argv[1:]})
mode = os.environ.get("FAKE_VLLM_MODE", "ok")
if mode == "die":
    print("fake vllm: CUDA out of memory", file=sys.stderr)
    sys.exit(1)
if mode == "hang":
    time.sleep(3600)

argv = sys.argv[1:]
def opt(name):
    return [argv[i + 1] for i, a in enumerate(argv) if a == name]
port = int(opt("--port")[0])
names = opt("--served-model-name") + [m.split("=", 1)[0] for m in opt("--lora-modules")]

from eval import dataset, prompt
from eval.tests.fixtures import render_grade
ds = dataset.load()
cases = ds.by_id()
by_hash = {r["prompt_sha256"]: r["test_id"] for r in prompt.build_prompts(ds)}
model_lists = []


class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def send(self, code, data):
        body = json.dumps(data).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/v1/models":
            # "models_once": ready for the job's own check, then the base run finds nothing to grade with.
            model_lists.append(1)
            hidden = mode == "models_once" and len(model_lists) > 1
            self.send(200, {"data": [] if hidden else [{"id": n} for n in names]})
        elif self.path == "/version":
            self.send(200, {"version": "fake"})
        else:
            self.send(404, {})

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        if body["model"] not in names:
            return self.send(404, {"error": "unknown model"})
        tid = by_hash[prompt.messages_sha256(body["messages"])]
        log({"request": {k: body.get(k) for k in ("model", "temperature", "top_p", "max_tokens", "seed",
                                                  "chat_template_kwargs")},
             "test_id": tid, "prompt_sha256": prompt.messages_sha256(body["messages"])})
        self.send(200, {"model": body["model"], "choices": [{"message": {"content": render_grade(cases[tid])},
                                                             "finish_reason": "stop"}]})


http.server.ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()
'''


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class FakeCluster:
    def __init__(self, root: Path, adapter=True, stubs=True):
        self.root = root
        self.bin, self.stubs, self.venv = root / "bin", root / "stubs", root / "venv"
        for d in (self.bin, self.stubs / "openai", self.stubs / "torch", self.venv / "bin", root / "home"):
            d.mkdir(parents=True)
        (self.stubs / "openai" / "__init__.py").write_text(OPENAI_STUB)
        (self.stubs / "torch" / "__init__.py").write_text(TORCH_STUB)
        # A wrapper, not a symlink: a venv's python finds its venv only when started by its own path.
        self.script(self.bin / "python", f'#!/bin/sh\nexec {shlex.quote(sys.executable)} "$@"\n')
        self.script(self.bin / "vllm", f"#!{sys.executable}\n" + FAKE_VLLM)
        self.script(self.bin / "nvidia-smi", "#!/bin/sh\necho 'GPU 0: Fake GPU'\n")
        pythonpath = f"{self.stubs}:{REPO}" if stubs else str(REPO)
        # Put the stubs in front of any existing PYTHONPATH instead of replacing it.
        (self.venv / "bin" / "activate").write_text(
            f'export PATH="{self.bin}:$PATH"\nexport PYTHONPATH="{pythonpath}${{PYTHONPATH:+:$PYTHONPATH}}"\n')
        self.model = root / "models" / "Qwen3.8-27B"
        self.model.mkdir(parents=True)
        (self.model / "config.json").write_text("{}")
        self.adapter = None
        if adapter:
            self.adapter = root / "adapters" / "grading"
            self.adapter.mkdir(parents=True)
            (self.adapter / "adapter_config.json").write_text(json.dumps({"r": 16, "lora_alpha": 16}))
            (self.adapter / "adapter_model.safetensors").write_bytes(b"")
            (self.adapter / "settings.yaml").write_text(
                f"base_model: {self.model}\ndata: data/generated/skills/train.jsonl\n")
        self.out = root / "out"
        self.log = root / "vllm_calls.jsonl"
        self.pidfile = root / "vllm.pid"

    @staticmethod
    def script(path, text):
        path.write_text(text)
        path.chmod(0o755)

    def env(self, **extra):
        env = {"PATH": os.environ["PATH"], "HOME": str(self.root / "home"), "VENV": str(self.venv),
               "BASE_MODEL": str(self.model), "ADAPTER": str(self.adapter or ""), "EVAL_OUT": str(self.out),
               "PORT": str(free_port()), "SLURM_JOB_ID": "4242", "HEALTH_INTERVAL": "1",
               "HEALTH_TIMEOUT": "60", "STOP_TIMEOUT": "5", "PYTHONDONTWRITEBYTECODE": "1",
               "FAKE_VLLM_LOG": str(self.log), "FAKE_VLLM_PIDFILE": str(self.pidfile)}
        # Cluster modules (e.g. Fir's scipy-stack) provide packages such as numpy through these.
        for key in ("PYTHONPATH", "EBPYTHONPREFIXES"):
            if key in os.environ:
                env[key] = os.environ[key]
        env.update(extra)
        return env

    def run(self, *args, timeout=180, **env):
        return subprocess.run(["bash", str(SCRIPT), *args], env=self.env(**env), capture_output=True, text=True,
                              timeout=timeout, cwd=self.root)

    def calls(self):
        if not self.log.exists():
            return []
        return [json.loads(line) for line in self.log.read_text().splitlines()]

    def vllm_alive(self):
        if not self.pidfile.exists():
            return False
        try:
            os.kill(int(self.pidfile.read_text()), 0)
            return True
        except ProcessLookupError:
            return False


# --------------------------------------------------------------------------- preflight

class PreflightTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.cluster = FakeCluster(self.root / "main")
        # vllm and curl are commands; pretend both exist for these unit tests.
        self.which = mock.patch.object(preflight.shutil, "which", lambda cmd: f"/usr/bin/{cmd}")
        self.spec = mock.patch.object(preflight.importlib.util, "find_spec", lambda name: object())
        self.which.start()
        self.spec.start()

    def tearDown(self):
        mock.patch.stopall()
        self._tmp.cleanup()

    def check(self, adapter="default", out=None, run_args=(), base=None, repo=REPO, cluster=None):
        c = cluster or self.cluster
        adapter = str(c.adapter) if adapter == "default" else adapter
        return preflight.check(repo, str(base or c.model), adapter, str(out or c.out), list(run_args))

    def test_good_setups(self):
        problems, info, warnings = self.check()
        self.assertEqual(problems, [])
        self.assertEqual(info["MODE"], "base_and_fine_tuned")
        self.assertEqual(info["LORA_RANK"], "16")
        self.assertEqual(info["BASE_NAME"], backends.SERVED_MODELS["base"])
        self.assertEqual(info["FT_NAME"], backends.SERVED_MODELS["fine_tuned"])
        self.assertEqual(info["DATASET_SHA256"], dataset.EXPECTED_SHA256)
        self.assertTrue(any("grading skills" in w for w in warnings))

        problems, info, warnings = self.check(adapter=None)
        self.assertEqual(problems, [])
        self.assertEqual(info["MODE"], "base_only")
        self.assertTrue(any("only the base model" in w for w in warnings))

    def test_bad_setups_reported(self):
        c = FakeCluster(self.root / "missing")
        shutil.rmtree(c.model)
        problems, _, _ = self.check(adapter=str(c.root / "no_such_adapter"), cluster=c)
        self.assertTrue(any("no model found" in p for p in problems))
        self.assertTrue(any("no adapter folder" in p for p in problems))

        c = self.cluster
        for name, fragment in (("adapter_config.json", "adapter_config.json"),
                               ("adapter_model.safetensors", "adapter weights"),
                               ("settings.yaml", "settings.yaml")):
            with self.subTest(missing=name):
                path = c.adapter / name
                saved = path.read_bytes()
                path.unlink()
                problems, _, _ = self.check()
                self.assertTrue(any(fragment in p for p in problems), problems)
                path.write_bytes(saved)

        for text, fragment in (('{"r": 0}', "LoRA rank"), ("{not json", "LoRA rank")):
            with self.subTest(config=text):
                (c.adapter / "adapter_config.json").write_text(text)
                self.assertTrue(any(fragment in p for p in self.check()[0]))
        (c.adapter / "adapter_config.json").write_text('{"r": 8}')
        (c.adapter / "settings.yaml").write_text("lora_rank: 8\n")
        self.assertTrue(any("does not say which base_model" in p for p in self.check()[0]))

        c = FakeCluster(self.root / "elsewhere")
        not_repo = c.root / "not_a_repo"
        not_repo.mkdir()
        self.assertTrue(any("is not the repo folder" in p for p in self.check(repo=not_repo, cluster=c)[0]))
        a_file = c.root / "a_file"
        a_file.write_text("")
        self.assertTrue(any("is not a folder" in p for p in self.check(out=a_file, cluster=c)[0]))

        with mock.patch.object(preflight.importlib.util, "find_spec", lambda name: None), \
                mock.patch.object(preflight.shutil, "which", lambda cmd: None):
            problems = self.check(cluster=c)[0]
        for name in ("'openai'", "'numpy'", "'yaml'", "'vllm'", "'curl'"):
            self.assertTrue(any(name in p for p in problems), name)

    def test_adapter_base_model_checked(self):
        repo = self.cluster.root / "repo"
        (repo / "eval").mkdir(parents=True)
        (repo / "eval" / "run_eval.py").write_text("")
        (repo / "models").mkdir()
        os.symlink(self.cluster.model, repo / "models" / "Qwen3.8-27B")
        # The same model under another name is recorded as the adapter names it.
        problems, info, _ = self.check(base="models/Qwen3.8-27B", repo=repo)
        self.assertEqual(problems, [])
        self.assertEqual(info["BASE_MODEL_RECORD"], str(self.cluster.model))

        (self.cluster.adapter / "settings.yaml").write_text("base_model: models/Other-8B\n")
        self.assertTrue(any("trained on 'models/Other-8B'" in p for p in self.check()[0]))

    def test_output_inside_repo_refused(self):
        link = self.cluster.root / "repo_link"
        os.symlink(REPO, link)
        for out in (REPO / "runs", REPO, REPO / "test_set" / "x", link / "runs"):
            with self.subTest(out=out):
                self.assertTrue(any("inside the repo" in p for p in self.check(out=out)[0]))

    def test_run_args(self):
        self.assertEqual(self.check(run_args=["--test-type", "paraphrase", "--max-tokens", "1024"])[0], [])
        for args, fragment in ((["--model", "fine_tuned"], "sets --model itself"),
                               (["--out=/elsewhere"], "sets --out itself"),
                               (["--endpoint", "http://x"], "sets --endpoint itself"),
                               (["--topic", "no_such_topic"], "unknown topic"),
                               (["--max-tokens", "0"], "max_tokens"),
                               (["--n-boot", "many"], "does not accept")):
            with self.subTest(args=args):
                problems = self.check(run_args=args)[0]
                self.assertTrue(any(fragment in p for p in problems), problems)

    def test_output_is_safe_for_the_shell(self):
        weird = self.cluster.root / "out dir; rm -rf ~"
        with mock.patch("sys.stdout") as out, mock.patch("sys.stderr"):
            code = preflight.main(["--base-model", str(self.cluster.model), "--adapter", str(self.cluster.adapter),
                                   "--out", str(weird)])
        self.assertEqual(code, 0)
        printed = "".join(c.args[0] for c in out.write.call_args_list)
        self.assertIn("OUT='", printed)
        env = subprocess.run(["bash", "-c", printed + '\nprintf %s "$OUT"'], capture_output=True, text=True)
        self.assertEqual(env.stdout, str(weird.resolve()))


# --------------------------------------------------------------------------- the job script

@unittest.skipUnless(shutil.which("curl"), "curl not installed")
class JobScriptTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Two different questions, whatever the test set holds, to keep the fake jobs short.
        cases = dataset.load().cases
        cls.question = cases[0]["question_id"]
        cls.other_question = cases[-1]["question_id"]
        cls.question_size = sum(c["question_id"] == cls.question for c in cases)

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.clusters = 0
        self.files_before = eval_files()

    def tearDown(self):
        self.assertEqual(eval_files(), self.files_before, "the job wrote files into the repo")
        self._tmp.cleanup()

    def cluster(self, **kwargs):
        self.clusters += 1
        return FakeCluster(self.root / str(self.clusters), **kwargs)

    def test_check_mode_creates_nothing(self):
        c = self.cluster()
        r = c.run("--check", "--", "--test-type", "paraphrase")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("Checks passed (base_and_fine_tuned)", r.stdout)
        self.assertIn("Adapter training data: data/generated/skills/train.jsonl", r.stdout)
        self.assertFalse(c.out.exists())
        self.assertEqual(c.calls(), [])

    def test_check_mode_reports_problems(self):
        c = self.cluster(stubs=False)  # no openai stub; a missing openai shows only where it isn't installed
        shutil.rmtree(c.model)
        r = c.run("--check")
        self.assertEqual(r.returncode, 1)
        if importlib.util.find_spec("openai") is None:
            self.assertIn("'openai' is missing", r.stderr)
        self.assertIn("Preflight checks failed:", r.stderr)
        self.assertIn("no model found", r.stderr)
        r = c.run("--check", "--", "--model", "base")
        self.assertIn("sets --model itself", r.stderr)

        c = self.cluster()
        r = c.run("--check", VENV=str(c.root / "nowhere"))
        self.assertEqual(r.returncode, 1)
        self.assertIn("no Python environment", r.stdout)

    def test_full_job(self):
        c = self.cluster()
        r = c.run("--", "--question-id", self.question, "--n-boot", "50")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        root = c.out / "4242"
        (base_run,) = (root / "base").iterdir()
        (ft_run,) = (root / "fine_tuned").iterdir()
        (cmp,) = (root / "compare").iterdir()
        self.assertTrue((root / "vllm.log").exists())
        result = json.loads((cmp / "compare.json").read_text())
        self.assertTrue(result["provisional"])
        self.assertEqual(result["settings"]["n_boot"], 50)
        a = json.loads((base_run / "config.json").read_text())
        b = json.loads((ft_run / "config.json").read_text())
        self.assertEqual((a["status"], b["status"]), ("complete", "complete"))
        self.assertEqual(a["prompts_file"]["sha256"], b["prompts_file"]["sha256"])
        self.assertEqual(a["decoding"], b["decoding"])
        self.assertEqual(a["selection"]["selected_count"], self.question_size)
        self.assertEqual(b["model"]["adapter"]["path"], str(c.adapter.resolve()))
        self.assertEqual(a["model"]["base_model"], str(c.model))  # as the adapter's settings.yaml names it
        self.assertEqual(b["model"]["base_model"], str(c.model))

        calls = c.calls()
        argv = calls[0]["argv"]
        self.assertEqual(argv[:2], ["serve", str(c.model.resolve())])
        for flag in ("--enable-lora", "--host", "127.0.0.1", "--max-lora-rank", "16",
                     f"gradeai-ft={c.adapter.resolve()}", "qwen3.8-27b"):
            self.assertIn(flag, argv)
        requests = [x for x in calls if "request" in x]
        by_model = {}
        for x in requests:
            by_model.setdefault(x["request"]["model"], []).append(x)
        self.assertEqual(set(by_model), {"qwen3.8-27b", "gradeai-ft"})
        self.assertEqual([x["prompt_sha256"] for x in by_model["qwen3.8-27b"]],
                         [x["prompt_sha256"] for x in by_model["gradeai-ft"]])
        settings = {json.dumps({k: v for k, v in x["request"].items() if k != "model"}) for x in requests}
        self.assertEqual(len(settings), 1)
        sent = json.loads(settings.pop())
        self.assertEqual((sent["temperature"], sent["chat_template_kwargs"]), (0.0, {"enable_thinking": False}))
        self.assertFalse(c.vllm_alive(), "vLLM was left running")
        self.assertIn("provisional", r.stdout)
        self.assertIn("human-reviewed, but not independently TA-verified or frozen", r.stdout)

    def test_base_only_without_adapter(self):
        c = self.cluster(adapter=False)
        r = c.run("--", "--question-id", self.other_question, "--n-boot", "0")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        root = c.out / "4242"
        self.assertEqual(len(list((root / "base").iterdir())), 1)
        self.assertFalse((root / "fine_tuned").exists())
        self.assertFalse((root / "compare").exists())
        self.assertNotIn("--enable-lora", c.calls()[0]["argv"])
        self.assertIn("No adapter, so no comparison", r.stdout)
        self.assertFalse(c.vllm_alive())

    def test_server_failures_stop_cleanly(self):
        c = self.cluster()
        r = c.run(FAKE_VLLM_MODE="die")
        self.assertEqual(r.returncode, 1)
        self.assertIn("vLLM stopped while loading", r.stdout)
        self.assertIn("CUDA out of memory", r.stdout)
        self.assertIn("FAILED", r.stdout)

        c = self.cluster()
        r = c.run(FAKE_VLLM_MODE="hang", HEALTH_TIMEOUT="2")
        self.assertEqual(r.returncode, 1)
        self.assertIn("not ready after 2s", r.stdout)
        self.assertIn("Stopping vLLM", r.stdout)
        self.assertFalse(c.vllm_alive())

        # A failed base run ends the job: no fine-tuned run and no comparison.
        c = self.cluster()
        r = c.run(FAKE_VLLM_MODE="models_once")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("FAILED", r.stdout)
        self.assertNotIn("Fine-tuned run, started", r.stdout)
        self.assertFalse((c.out / "4242" / "compare").exists())
        self.assertFalse(c.vllm_alive())

    def test_stop_signal_stops_the_server(self):
        c = self.cluster()
        proc = subprocess.Popen(["bash", str(SCRIPT)], env=c.env(FAKE_VLLM_MODE="hang"), cwd=c.root,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        deadline = time.time() + 60
        while not c.pidfile.exists() and time.time() < deadline:
            time.sleep(0.2)
        self.assertTrue(c.vllm_alive())
        proc.send_signal(signal.SIGTERM)
        out, _ = proc.communicate(timeout=60)
        self.assertEqual(proc.returncode, 143)
        self.assertIn("Received a stop signal", out)
        self.assertFalse(c.vllm_alive())

    def test_cuda_failure_stops_before_loading_the_model(self):
        c = self.cluster()
        r = c.run(FAKE_CUDA="0")
        self.assertEqual(r.returncode, 1)
        self.assertIn("CUDA doesn't work", r.stdout)
        self.assertEqual(c.calls(), [])

    def test_existing_results_never_overwritten(self):
        c = self.cluster()
        (c.out / "4242").mkdir(parents=True)
        r = c.run()
        self.assertEqual(r.returncode, 1)
        self.assertIn("already exists", r.stdout)
        self.assertEqual(c.calls(), [])


if __name__ == "__main__":
    unittest.main()
