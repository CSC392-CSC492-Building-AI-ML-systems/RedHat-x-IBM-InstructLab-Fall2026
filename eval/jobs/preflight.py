"""Checks for eval/jobs/run_eval.sh that need no GPU, run before any model is loaded.

    python -m eval.jobs.preflight --base-model models/Qwen3.8-27B [--adapter DIR] --out DIR [-- RUN ARGS]

Checks:
- the repo and the test set (by hash);
- the Python packages the evaluation needs;
- the vllm and curl commands;
- the base model folder;
- the adapter, when given: PEFT files, its settings.yaml from training/train_lora.py, and that it
  was trained on this base model;
- that the output folder is outside the repo;
- that the extra run_eval.py options are ones the job may pass on, with valid values.

The adapter is optional: without one, the job runs the base model only. Every problem is listed,
then the script exits 1. On success it prints shell assignments for the job script to `eval`, with
every value quoted.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import shlex
import shutil
import sys
from pathlib import Path

from eval import backends, dataset, run_eval

PACKAGES = ("openai", "numpy", "yaml")
COMMANDS = ("vllm", "curl")
WEIGHTS = ("adapter_model.safetensors", "adapter_model.bin")
# run_eval.py options the job may pass on to both runs. The job sets the rest itself, so that
# both models get the same prompts, outputs and server.
PASSTHROUGH = ("--test-type", "--topic", "--question-id", "--temperature", "--top-p", "--max-tokens",
               "--seed", "--n-boot", "--boot-seed")


def resolve(path: str, repo: Path) -> Path:
    p = Path(path).expanduser()
    return (p if p.is_absolute() else repo / p).resolve()


def inside(path: Path, folder: Path) -> bool:
    return path == folder or folder in path.parents


def check_run_args(args: list[str], ds) -> list[str]:
    problems = []
    for a in args:
        if a.startswith("--") and a.split("=", 1)[0] not in PASSTHROUGH:
            problems.append(f"the job sets {a.split('=', 1)[0]} itself; options it can pass on: {', '.join(PASSTHROUGH)}")
    if problems:
        return problems
    try:
        with open(os.devnull, "w") as devnull, _stderr_to(devnull):
            parsed = run_eval.parser().parse_args(["--model", "base", "--out", "x", *args])
    except SystemExit:
        return [f"run_eval.py does not accept these options: {' '.join(args)}"]
    try:
        dataset.select(ds, test_types=parsed.test_type, topics=parsed.topic, question_ids=parsed.question_id)
        backends.Decoding(temperature=parsed.temperature, top_p=parsed.top_p, max_tokens=parsed.max_tokens,
                          seed=parsed.seed)
    except (dataset.DatasetError, backends.BackendError) as exc:
        problems.append(str(exc))
    return problems


class _stderr_to:
    def __init__(self, stream):
        self.stream = stream

    def __enter__(self):
        self.old, sys.stderr = sys.stderr, self.stream

    def __exit__(self, *exc):
        sys.stderr = self.old


def check_adapter(adapter: Path, base_model: str, base_resolved: Path, repo: Path) -> tuple[list[str], dict, list[str]]:
    problems, info, warnings = [], {}, []
    if not adapter.is_dir():
        return [f"no adapter folder at {adapter}"], info, warnings
    config_path = adapter / "adapter_config.json"
    if not config_path.exists():
        problems.append(f"{adapter} has no adapter_config.json, so it is not a saved PEFT adapter")
    else:
        try:
            rank = json.loads(config_path.read_text(encoding="utf-8")).get("r")
        except json.JSONDecodeError:
            rank = None
        if not isinstance(rank, int) or rank <= 0:
            problems.append(f"{config_path} has no positive LoRA rank 'r'")
        else:
            info["LORA_RANK"] = str(rank)
    if not any((adapter / w).exists() for w in WEIGHTS):
        problems.append(f"{adapter} has no adapter weights ({' or '.join(WEIGHTS)})")
    settings_path = adapter / "settings.yaml"
    if not settings_path.exists():
        problems.append(f"{adapter} has no settings.yaml (training/train_lora.py saves one), so its base model "
                        "can't be checked")
        return problems, info, warnings
    try:
        import yaml
        settings = yaml.safe_load(settings_path.read_text(encoding="utf-8")) or {}
    except Exception as exc:  # noqa: BLE001 - a missing yaml package is reported with the packages
        return problems + [f"can't read {settings_path}: {exc}"], info, warnings
    trained_on = settings.get("base_model")
    if not trained_on:
        problems.append(f"{settings_path} does not say which base_model the adapter was trained on")
    elif resolve(str(trained_on), repo) != base_resolved:
        problems.append(f"the adapter was trained on {trained_on!r}, but the job serves {base_model!r}")
    else:
        # Record the base model the way the adapter names it, so compare.py sees the same string.
        info["BASE_MODEL_RECORD"] = str(trained_on)
    data = settings.get("data")
    info["ADAPTER_DATA"] = str(data or "")
    warnings.append(f"the adapter was trained on {data or 'unrecorded data'}; make sure that includes the grading "
                    "skills before reading the comparison as a grading result")
    return problems, info, warnings


def check(repo: Path, base_model: str, adapter: str | None, out: str, run_args: list[str]) -> tuple[list[str], dict, list[str]]:
    problems, warnings = [], []
    info = {"REPO": str(repo), "BASE_MODEL_RECORD": base_model, "BASE_NAME": backends.SERVED_MODELS["base"],
            "FT_NAME": backends.SERVED_MODELS["fine_tuned"], "MODE": "base_and_fine_tuned" if adapter else "base_only"}

    if not (repo / "eval" / "run_eval.py").exists():
        problems.append(f"{repo} is not the repo folder (no eval/run_eval.py); submit the job from the repo folder")
    ds = None
    try:
        ds = dataset.load()
        info["DATASET_SHA256"] = ds.sha256
    except dataset.DatasetError as exc:
        problems.append(str(exc))
    for name in PACKAGES:
        if importlib.util.find_spec(name) is None:
            problems.append(f"Python package {name!r} is missing from this environment (env/model has it)")
    for cmd in COMMANDS:
        if shutil.which(cmd) is None:
            problems.append(f"command {cmd!r} not found")

    base_resolved = resolve(base_model, repo)
    if not (base_resolved / "config.json").exists():
        problems.append(f"no model found at {base_resolved} (no config.json)")
    info["BASE_MODEL_PATH"] = str(base_resolved)

    if adapter:
        adapter_resolved = resolve(adapter, repo)
        info["ADAPTER_PATH"] = str(adapter_resolved)
        p, i, w = check_adapter(adapter_resolved, base_model, base_resolved, repo)
        problems, warnings = problems + p, warnings + w
        info.update(i)
    else:
        warnings.append("no ADAPTER given: only the base model will be evaluated, with no comparison")

    out_resolved = resolve(out, Path.cwd())
    if inside(out_resolved, repo.resolve()):
        problems.append(f"the output folder {out_resolved} is inside the repo; choose one outside it "
                        "(the outputs contain test-set text)")
    elif out_resolved.exists() and not out_resolved.is_dir():
        problems.append(f"{out_resolved} exists and is not a folder")
    info["OUT"] = str(out_resolved)

    if ds is not None:
        problems += check_run_args(run_args, ds)
    return problems, info, warnings


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--repo", default=str(dataset.REPO))
    p.add_argument("--base-model", required=True)
    p.add_argument("--adapter", default="")
    p.add_argument("--out", required=True)
    p.add_argument("run_args", nargs="*", help="run_eval.py options for both runs (after --)")
    args = p.parse_args(argv)
    problems, info, warnings = check(Path(args.repo).resolve(), args.base_model, args.adapter or None, args.out,
                                     args.run_args)
    for w in warnings:
        print(f"Note: {w}", file=sys.stderr)
    if problems:
        print("Preflight checks failed:", file=sys.stderr)
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        return 1
    for key, value in info.items():
        print(f"{key}={shlex.quote(value)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
