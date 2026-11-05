"""Run the test set against the base or fine-tuned model and score the grades.

    python eval/run_eval.py --model base --out runs --endpoint http://localhost:8000/v1
    python eval/run_eval.py --model fine_tuned --adapter models/adapters/<name> --out runs \
        --endpoint http://localhost:8000/v1

Filters choose the cases a run is about (--test-type, --topic, --question-id). The parents of
selected variants are also graded, as references only (eval/dataset.py).

Each run builds its prompts with eval/prompt.py and saves them, complete (system and user
messages), with a hash per prompt. eval/compare.py then checks that both runs sent byte-identical
prompts with the same decoding settings.

Each run gets its own folder <out>/<timestamp>_<model>/ with:
  config.json         everything needed to reproduce the run, plus its status
  prompts.jsonl       the exact messages sent for each case, with their hashes
  raw_outputs.jsonl   each reply verbatim, written as it arrives
  parsed.jsonl        each reply parsed against its rubric
  metrics.json        all metrics, with definitions
  summary.md          a readable summary

Each request is sent once; a failed request is saved as a result. Replies are written as they
arrive, so a stopped run still shows what it got, but a run is only usable once its status is
"complete". A run that stopped (time limit, Ctrl+C, a crash) is simply started again in a new run
folder: 60 cases take minutes. Before any request, the runner checks that the server serves the
run's model.

Output folders must be outside the repo, including through symlinks: the outputs contain
test-set text.

Re-score a finished run with the current parser and metrics, without a model:

    python eval/run_eval.py --rescore runs/<run folder>

This writes a new rescore_<timestamp>/ folder inside the run and leaves the raw outputs alone.

Every result is provisional: the Group B labels are AI-drafted and human-reviewed, but not
independently TA-verified or frozen.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import platform
import socket
import subprocess
import sys
from pathlib import Path

if __package__ in (None, ""):  # run as `python eval/run_eval.py`
    sys.path[0] = str(Path(__file__).resolve().parent.parent)

from eval import backends, dataset, metrics, parse, prompt, report  # noqa: E402

PROMPTS = "prompts.jsonl"
CONFIG = "config.json"
RAW = "raw_outputs.jsonl"
PARSED = "parsed.jsonl"
METRICS = "metrics.json"
SUMMARY = "summary.md"
PROVISIONAL_NOTE = ("Scored against Group B AI-drafted labels, human-reviewed; provisional and not independently "
                    "TA-verified or frozen. Not answer-key results.")


class RunError(Exception):
    pass


# --------------------------------------------------------------------------- small helpers

def now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def write_json(path: Path, data) -> None:
    """Write via a temporary file, so a crash never leaves half a file."""
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def write_jsonl(path: Path, records) -> None:
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    os.replace(tmp, path)


def read_jsonl(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def git_info() -> dict:
    def git(*cmd):
        out = subprocess.run(["git", "-C", str(dataset.REPO), *cmd], capture_output=True, text=True, timeout=10)
        return out.stdout.strip() if out.returncode == 0 else None
    try:
        return {"git_commit": git("rev-parse", "HEAD"), "git_dirty": bool(git("status", "--porcelain"))}
    except (OSError, subprocess.SubprocessError):
        return {"git_commit": None, "git_dirty": None}


def environment() -> dict:
    return {"python": platform.python_version(), "platform": platform.platform(), "host": socket.gethostname()}


def check_out_dir(out: Path) -> None:
    """Refuse a folder inside the repo, also one reached through a symlink: outputs contain test-set
    text and must not end up in git."""
    target = Path(out).expanduser().resolve()
    repo = dataset.REPO.resolve()
    if target == repo or repo in target.parents:
        raise RunError(f"refusing to write output inside the repo ({target}); choose a folder outside it")


# --------------------------------------------------------------------------- saved replies

def _reply(line: bytes, where: str) -> backends.Generation:
    try:
        record = json.loads(line.decode("utf-8"))
        if not isinstance(record, dict) or not isinstance(record.get("test_id"), str) \
                or not isinstance(record.get("prompt_sha256"), str):
            raise ValueError("not a saved reply record")
        return backends.Generation.from_record(record)
    except (UnicodeDecodeError, ValueError, TypeError) as exc:
        raise RunError(f"{where} is not a valid saved reply ({exc}); the file was not changed") from None


def read_replies(path: Path) -> list[backends.Generation]:
    """Every saved reply in a raw_outputs.jsonl. Any bad line, or a case saved twice, is an
    error naming the line. Never changes the file."""
    replies, seen = [], {}
    for n, line in enumerate(Path(path).read_bytes().split(b"\n"), 1):
        if not line.strip():
            continue
        g = _reply(line, f"{path}, line {n}")
        if g.test_id in seen:
            raise RunError(f"{path}: {g.test_id} is saved twice (lines {seen[g.test_id]} and {n}); "
                           "the file was not changed")
        seen[g.test_id] = n
        replies.append(g)
    return replies


# --------------------------------------------------------------------------- prompts

def write_prompts(ds: dataset.Dataset, selection: dataset.Selection, run_dir: Path) -> tuple[dict, dict]:
    """Build the prompts for the run's cases and save them, complete, to prompts.jsonl."""
    wanted = {i.test_id for i in selection.items}
    records = [r for r in prompt.build_prompts(ds) if r["test_id"] in wanted]
    path = run_dir / PROMPTS
    write_jsonl(path, records)
    return ({r["test_id"]: r["messages"] for r in records},
            {"sha256": dataset.sha256_file(path), "records": len(records)})


def read_prompts(run_dir: Path, config: dict) -> dict[str, list[dict]]:
    """A run's saved prompts, checked: the file is the one the run recorded, and each prompt's
    messages still match its hash."""
    path = run_dir / PROMPTS
    if not path.exists():
        raise RunError(f"{path} is missing")
    if dataset.sha256_file(path) != config["prompts_file"]["sha256"]:
        raise RunError(f"{path} no longer matches the run's config (the file was changed)")
    out = {}
    for r in read_jsonl(path):
        if prompt.messages_sha256(r["messages"]) != r["prompt_sha256"]:
            raise RunError(f"{path}: the prompt for {r['test_id']} does not match its hash")
        out[r["test_id"]] = r["messages"]
    return out


# --------------------------------------------------------------------------- one run

def adapter_info(path: str | None) -> dict | None:
    if not path:
        return None
    info = {"path": path}
    settings = Path(path) / "settings.yaml"
    if settings.exists():
        info["settings_sha256"] = dataset.sha256_file(settings)
        try:
            import yaml
            with open(settings, encoding="utf-8") as f:
                info["settings"] = yaml.safe_load(f)
        except ImportError:
            info["settings"] = None
    else:
        info["settings_sha256"] = None
    return info


def make_backend(args, client=None):
    decoding = backends.Decoding(temperature=args.temperature, top_p=args.top_p,
                                 max_tokens=args.max_tokens, seed=args.seed)
    if not args.endpoint:
        raise RunError("a run needs --endpoint (the vLLM server)")
    return backends.make_backend(args.model, args.endpoint, decoding, served_model=args.served_model,
                                 client=client), decoding


def new_run_dir(out: Path, model: str) -> Path:
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d-%H%M%S")
    run_dir = out / f"{stamp}_{model}"
    n = 1
    while run_dir.exists():
        n += 1
        run_dir = out / f"{stamp}_{model}_{n}"
    run_dir.mkdir(parents=True)
    return run_dir


def check_server(server: dict, served_model: str) -> None:
    """Refuse to start when the server can't be reached or doesn't serve the model. Otherwise every
    request would fail and be saved as a request error."""
    if "served_models" not in server:
        raise RunError(f"can't list the server's models ({server.get('served_models_error')}); no request was sent")
    if served_model not in server["served_models"]:
        raise RunError(f"the server does not serve {served_model!r} (it serves {server['served_models']}); "
                       "no request was sent")


def score(ds, selection, raw: list[backends.Generation], n_boot: int, seed: int):
    """Parse every reply and compute the metrics. Needs a reply for every case in the selection."""
    by_id = ds.by_id()
    parsed = {g.test_id: parse.parse_generation(g, by_id[g.test_id]) for g in raw}
    return parsed, metrics.summarize(ds, selection, {i.test_id: parsed[i.test_id] for i in selection.items},
                                     n_boot=n_boot, seed=seed)


def write_results(run_dir: Path, config: dict, ds, selection, raw, n_boot, seed) -> dict:
    parsed, result = score(ds, selection, raw, n_boot, seed)
    order = [i.test_id for i in selection.items]
    records = [{**parsed[t].to_record(), "role": selection.role(t)} for t in order]
    write_jsonl(run_dir / PARSED, records)
    write_json(run_dir / METRICS, {"provisional": True, "note": PROVISIONAL_NOTE, "run": run_dir.name, **result})
    (run_dir / SUMMARY).write_text(report.render_summary(config, result, records), encoding="utf-8")
    return result


def run(args, client=None) -> tuple[Path, int]:
    ds = dataset.load(args.dataset, expected_sha256=args.expected_sha256)
    selection = dataset.select(ds, test_types=args.test_type, topics=args.topic, question_ids=args.question_id)
    backend, decoding = make_backend(args, client)
    served_model = backend.served_model
    # Before anything is created or sent.
    server = backend.server_info()
    check_server(server, served_model)

    out = Path(args.out)
    check_out_dir(out)
    out.mkdir(parents=True, exist_ok=True)
    run_dir = new_run_dir(out, args.model)
    messages, prompts_file = write_prompts(ds, selection, run_dir)

    warnings = []
    if decoding.temperature != 0:
        warnings.append(f"temperature is {decoding.temperature}, not 0: replies may differ between runs")
    config = {
        "tool": "eval/run_eval.py",
        "created_at": now(),
        "status": "running",
        "provisional": True,
        "labels_note": PROVISIONAL_NOTE,
        "dataset": ds.describe(),
        "prompt": prompt.describe(ds),
        "prompts_file": prompts_file,
        "model": {"role": args.model, "served_model": served_model,
                  "base_model": args.base_model, "adapter": adapter_info(args.adapter)},
        "backend": backend.describe(),
        "decoding": decoding.to_dict(),
        "selection": selection.describe(),
        "selection_headline": selection.headline(),
        "metrics_settings": {"n_boot": args.n_boot, "seed": args.boot_seed},
        "code": git_info(),
        "environment": environment(),
        "warnings": warnings,
    }
    config["server"] = server
    if config["model"]["base_model"] is None and config["model"]["adapter"]:
        config["model"]["base_model"] = (config["model"]["adapter"].get("settings") or {}).get("base_model")
    write_json(run_dir / CONFIG, config)

    done = {}

    def finish(status, detail, code):
        config["status"], config["status_detail"] = status, detail
        config["counts"] = {"cases_in_run": len(selection.items), "replies_saved": len(done),
                            "request_errors": sum(g.error is not None for g in done.values())}
        config["finished_at"] = now()
        write_json(run_dir / CONFIG, config)
        if status != "complete":
            (run_dir / SUMMARY).write_text(report.render_summary(config, None, None), encoding="utf-8")
        return run_dir, code

    with open(run_dir / RAW, "w", encoding="utf-8") as f:
        for item in selection.items:
            g = backend.generate(item.test_id, messages[item.test_id])
            f.write(json.dumps(g.to_record(), ensure_ascii=False) + "\n")
            f.flush()
            done[item.test_id] = g

    try:
        dataset.verify_unchanged(ds)
    except dataset.DatasetError as exc:
        finish("failed", str(exc), 1)
        raise
    raw = [done[i.test_id] for i in selection.items]
    finish("complete", f"{len(done)} replies saved", 0)
    try:
        write_results(run_dir, config, ds, selection, raw, args.n_boot, args.boot_seed)
    except Exception as exc:
        # The replies are all saved; fix the problem, then --rescore this run.
        finish("scoring_failed", f"all {len(done)} replies saved, but scoring failed: {type(exc).__name__}: {exc}", 1)
        raise
    return run_dir, 0


def rescore(run_dir: Path, n_boot: int | None = None, seed: int | None = None) -> Path:
    """Parse and score a finished run's saved replies again, with the current code."""
    check_out_dir(run_dir)
    config = json.loads((run_dir / CONFIG).read_text(encoding="utf-8"))
    if config.get("status") not in ("complete", "scoring_failed"):
        raise RunError(f"{run_dir} is not complete (status {config.get('status')}); start a new run instead")
    ds = dataset.load(config["dataset"]["path"], expected_sha256=config["dataset"]["sha256"])
    f = config["selection"]["filters"]
    selection = dataset.select(ds, test_types=f["test_type"], topics=f["topic"], question_ids=f["question_id"])
    if selection.describe() != config["selection"]:
        raise RunError("the selection rebuilt from the config does not match the original run")
    messages = read_prompts(run_dir, config)
    raw = {g.test_id: g for g in read_replies(run_dir / RAW)}
    missing = [i.test_id for i in selection.items if i.test_id not in raw]
    if missing:
        raise RunError(f"{run_dir}: no saved reply for {missing[:5]}")
    for i in selection.items:
        if raw[i.test_id].prompt_sha256 != prompt.messages_sha256(messages[i.test_id]):
            raise RunError(f"{i.test_id}: the saved reply was produced from a different prompt")
    n_boot = config["metrics_settings"]["n_boot"] if n_boot is None else n_boot
    seed = config["metrics_settings"]["seed"] if seed is None else seed
    out = run_dir / f"rescore_{dt.datetime.now(dt.timezone.utc).strftime('%Y%m%d-%H%M%S')}"
    n = 1
    while out.exists():
        n += 1
        out = run_dir / f"rescore_{dt.datetime.now(dt.timezone.utc).strftime('%Y%m%d-%H%M%S')}_{n}"
    out.mkdir()
    rescore_config = {**config, "rescore": {"created_at": now(), "of_run": run_dir.name,
                                            "raw_outputs_sha256": dataset.sha256_file(run_dir / RAW),
                                            "code": git_info()},
                      "metrics_settings": {"n_boot": n_boot, "seed": seed}}
    write_json(out / CONFIG, rescore_config)
    write_results(out, rescore_config, ds, selection, [raw[i.test_id] for i in selection.items], n_boot, seed)
    return out


# --------------------------------------------------------------------------- command line

def csv(value: str) -> list[str]:
    return [v.strip() for v in value.split(",") if v.strip()]


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--rescore", metavar="RUN_DIR", help="re-parse and re-score a finished run")
    p.add_argument("--model", choices=sorted(backends.SERVED_MODELS))
    p.add_argument("--out", help="folder for run folders")
    p.add_argument("--dataset", default=str(dataset.DEFAULT_DATASET))
    p.add_argument("--expected-sha256", default=dataset.EXPECTED_SHA256)
    p.add_argument("--test-type", type=csv, help="comma-separated: " + ",".join(dataset.TEST_TYPES))
    p.add_argument("--topic", type=csv, help="comma-separated topics")
    p.add_argument("--question-id", type=csv, help="comma-separated question ids")
    p.add_argument("--endpoint", help="vLLM server, e.g. http://localhost:8000/v1")
    p.add_argument("--served-model", help="override the served model name")
    p.add_argument("--adapter", help="adapter folder, recorded with its settings.yaml")
    p.add_argument("--base-model", help="base model path or name, recorded in the config")
    p.add_argument("--temperature", type=float, default=backends.DEFAULT_DECODING.temperature)
    p.add_argument("--top-p", type=float, default=backends.DEFAULT_DECODING.top_p)
    p.add_argument("--max-tokens", type=int, default=backends.DEFAULT_DECODING.max_tokens)
    p.add_argument("--seed", type=int, default=backends.DEFAULT_DECODING.seed)
    p.add_argument("--n-boot", type=int, default=metrics.N_BOOT)
    p.add_argument("--boot-seed", type=int, default=metrics.SEED)
    return p


def main(argv=None, client=None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.rescore:
            out = rescore(Path(args.rescore))
            print(f"Re-scored into {out}")
            return 0
        if not (args.model and args.out):
            raise RunError("a run needs --model and --out")
        run_dir, code = run(args, client=client)
        status = json.loads((run_dir / CONFIG).read_text(encoding="utf-8"))
        print(f"{status['status']}: {status['status_detail']} ({run_dir})")
        return code
    except (RunError, dataset.DatasetError, backends.BackendError, metrics.MetricsError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
