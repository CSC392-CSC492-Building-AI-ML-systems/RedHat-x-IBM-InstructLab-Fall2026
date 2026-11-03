"""Send evaluation prompts to a model.

VLLMBackend talks to the vLLM server started by jobs/serve_model.sh, or by eval/jobs with the
fine-tuned LoRA, through its OpenAI-compatible API. The base and fine-tuned models differ only in
the served model name: the same Decoding goes with every request, and the messages are passed on
as given (eval/prompt.py builds them).

Each request is sent once. A request that fails is recorded as a failure, never retried, because a
retry can return a different answer. The model's reply is kept verbatim: nothing is stripped or
repaired here. Saved replies are re-scored without a model by `run_eval.py --rescore`.
"""

from __future__ import annotations

import json
import time
import urllib.request
from dataclasses import asdict, dataclass, field

from eval import prompt

# The names the models are served under. qwen3.8-27b is set in jobs/serve_model.sh; gradeai-ft is
# the --lora-modules name the eval job gives the adapter.
SERVED_MODELS = {"base": "qwen3.8-27b", "fine_tuned": "gradeai-ft"}


class BackendError(Exception):
    pass


@dataclass(frozen=True)
class Decoding:
    """Settings sent with every request, the same for both models."""
    temperature: float = 0.0       # 0 always picks the most likely token, so a rerun gives the same answer
    top_p: float = 1.0
    max_tokens: int = 2048
    seed: int = 0
    enable_thinking: bool = False  # the training answers have no thinking (training/compare_adapter.py)

    def __post_init__(self):
        if self.temperature < 0:
            raise BackendError("temperature must be >= 0")
        if not 0 < self.top_p <= 1:
            raise BackendError("top_p must be in (0, 1]")
        if self.max_tokens <= 0:
            raise BackendError("max_tokens must be positive")

    def to_dict(self) -> dict:
        return asdict(self)

    def request_kwargs(self) -> dict:
        return {"temperature": self.temperature, "top_p": self.top_p, "max_tokens": self.max_tokens,
                "seed": self.seed,
                "extra_body": {"chat_template_kwargs": {"enable_thinking": self.enable_thinking}}}


DEFAULT_DECODING = Decoding()


@dataclass
class Generation:
    """One model reply, as saved in raw_outputs.jsonl."""
    test_id: str
    prompt_sha256: str
    text: str | None                  # the reply verbatim; None if there was none
    error: str | None = None          # set when the request failed
    finish_reason: str | None = None  # "length" means the reply hit max_tokens
    reasoning: str | None = None      # thinking text, if the server returned it separately
    served_model: str | None = None   # the model name the server reported
    usage: dict | None = None
    latency_s: float | None = None
    extra: dict = field(default_factory=dict)

    def to_record(self) -> dict:
        return asdict(self)

    @classmethod
    def from_record(cls, record: dict) -> "Generation":
        known = {k: record[k] for k in cls.__dataclass_fields__ if k in record}
        return cls(**known)


def served_model_for(model: str, override: str | None = None) -> str:
    if model not in SERVED_MODELS:
        raise BackendError(f"unknown model {model!r}; choose from {sorted(SERVED_MODELS)}")
    return override or SERVED_MODELS[model]


class VLLMBackend:
    name = "vllm"

    def __init__(self, endpoint: str, served_model: str, decoding: Decoding = DEFAULT_DECODING,
                 client=None, timeout: float = 600.0):
        self.endpoint = endpoint.rstrip("/")
        self.served_model = served_model
        self.decoding = decoding
        self.timeout = timeout
        self.client = client if client is not None else self._make_client()

    def _make_client(self):
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise BackendError("VLLMBackend needs the openai package, which env/model has. "
                               "Run inside env/model.") from exc
        # max_retries=0: the SDK would otherwise resend a failed request on its own.
        return OpenAI(base_url=self.endpoint, api_key="EMPTY", max_retries=0, timeout=self.timeout)

    def describe(self) -> dict:
        return {"backend": self.name, "endpoint": self.endpoint, "served_model": self.served_model,
                "decoding": self.decoding.to_dict(), "retries": 0, "timeout_s": self.timeout}

    def generate(self, test_id: str, messages: list[dict]) -> Generation:
        prompt_sha256 = prompt.messages_sha256(messages)
        start = time.monotonic()
        try:
            response = self.client.chat.completions.create(
                model=self.served_model, messages=messages, **self.decoding.request_kwargs())
        except Exception as exc:  # noqa: BLE001 - every failure is recorded, none is retried
            return Generation(test_id, prompt_sha256, text=None, error=f"{type(exc).__name__}: {exc}",
                              latency_s=time.monotonic() - start)
        latency = time.monotonic() - start
        try:
            choice = response.choices[0]
            message = choice.message
        except (AttributeError, IndexError, TypeError) as exc:
            return Generation(test_id, prompt_sha256, text=None, error=f"malformed response: {exc}",
                              latency_s=latency)
        usage = getattr(response, "usage", None)
        return Generation(
            test_id, prompt_sha256,
            text=getattr(message, "content", None),
            finish_reason=getattr(choice, "finish_reason", None),
            reasoning=getattr(message, "reasoning_content", None),
            served_model=getattr(response, "model", None),
            usage=({k: getattr(usage, k, None) for k in ("prompt_tokens", "completion_tokens", "total_tokens")}
                   if usage is not None else None),
            latency_s=latency)

    def server_info(self, fetch=None) -> dict:
        """vLLM version and the model names being served, for the run config. Never raises."""
        fetch = fetch or self._fetch_json
        root = self.endpoint.removesuffix("/v1")
        info = {}
        try:
            info["vllm_version"] = fetch(root + "/version").get("version")
        except Exception as exc:  # noqa: BLE001
            info["vllm_version_error"] = f"{type(exc).__name__}: {exc}"
        try:
            info["served_models"] = [m.get("id") for m in fetch(self.endpoint + "/models").get("data", [])]
        except Exception as exc:  # noqa: BLE001
            info["served_models_error"] = f"{type(exc).__name__}: {exc}"
        return info

    def _fetch_json(self, url: str) -> dict:
        with urllib.request.urlopen(url, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))


def make_backend(model: str, endpoint: str, decoding: Decoding = DEFAULT_DECODING,
                 served_model: str | None = None, client=None) -> VLLMBackend:
    """A VLLMBackend for "base" or "fine_tuned". Only the served model name differs between them."""
    name = served_model_for(model, served_model)
    if model == "fine_tuned" and name == SERVED_MODELS["base"]:
        raise BackendError(f"the fine-tuned model can't be served as {name!r}, the base model's name")
    return VLLMBackend(endpoint, name, decoding, client=client)
