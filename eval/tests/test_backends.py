import copy
import importlib.util
import json
import unittest
from types import SimpleNamespace

from eval import backends, prompt
from eval.tests import test_set_guard
from eval.tests.fixtures import MiniDatasetTest, mid

HAVE_OPENAI = importlib.util.find_spec("openai") is not None

setUpModule, tearDownModule = test_set_guard()


class FakeCompletions:
    """Stands in for client.chat.completions; records every request."""

    def __init__(self, content="**Grade:** 0 / 10", finish_reason="stop", reasoning=None, error=None):
        self.calls = []
        self.content, self.finish_reason, self.reasoning, self.error = content, finish_reason, reasoning, error

    def create(self, **kwargs):
        self.calls.append(copy.deepcopy(kwargs))
        if self.error:
            raise self.error
        message = SimpleNamespace(content=self.content, reasoning_content=self.reasoning)
        return SimpleNamespace(
            choices=[SimpleNamespace(message=message, finish_reason=self.finish_reason)],
            usage=SimpleNamespace(prompt_tokens=1200, completion_tokens=150, total_tokens=1350),
            model=kwargs["model"])


def fake_client(**kwargs):
    completions = FakeCompletions(**kwargs)
    return SimpleNamespace(chat=SimpleNamespace(completions=completions)), completions


class DecodingTest(unittest.TestCase):
    def test_decoding_defaults_and_validation(self):
        d = backends.DEFAULT_DECODING
        self.assertEqual((d.temperature, d.top_p, d.seed, d.enable_thinking), (0.0, 1.0, 0, False))
        self.assertEqual(d.request_kwargs()["extra_body"], {"chat_template_kwargs": {"enable_thinking": False}})
        for kwargs in ({"temperature": -0.1}, {"top_p": 0}, {"top_p": 1.5}, {"max_tokens": 0}):
            with self.assertRaises(backends.BackendError):
                backends.Decoding(**kwargs)


class VLLMBackendTest(MiniDatasetTest):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.prompts = {r["test_id"]: r for r in prompt.build_prompts(cls.ds)}
        cls.inj = cls.prompts[mid("beta_02_ans01_inj1")]

    def test_request_carries_prompt_and_decoding(self):
        client, completions = fake_client()
        backend = backends.VLLMBackend("http://node:8000/v1/", "qwen3.8-27b", client=client)
        backend.generate(self.inj["test_id"], self.inj["messages"])
        self.assertEqual(len(completions.calls), 1)
        call = completions.calls[0]
        self.assertEqual(call["model"], "qwen3.8-27b")
        self.assertEqual(call["messages"], self.inj["messages"])
        self.assertEqual(call["temperature"], 0.0)
        self.assertEqual(call["top_p"], 1.0)
        self.assertEqual(call["seed"], 0)
        self.assertEqual(call["max_tokens"], 2048)
        self.assertEqual(call["extra_body"], {"chat_template_kwargs": {"enable_thinking": False}})
        self.assertEqual(backend.endpoint, "http://node:8000/v1")

    def test_base_and_fine_tuned_send_identical_requests_except_model(self):
        records = [self.prompts[mid(t)] for t in ("alpha_01_ans01", "gamma_03_ans01_kw1")]
        calls = {}
        for model in ("base", "fine_tuned"):
            client, completions = fake_client()
            backend = backends.make_backend(model, "http://node:8000/v1", client=client)
            for r in records:
                backend.generate(r["test_id"], r["messages"])
            calls[model] = completions.calls
        self.assertEqual([c["model"] for c in calls["base"]], ["qwen3.8-27b"] * 2)
        self.assertEqual([c["model"] for c in calls["fine_tuned"]], ["gradeai-ft"] * 2)
        strip = lambda cs: [{k: v for k, v in c.items() if k != "model"} for c in cs]
        self.assertEqual(strip(calls["base"]), strip(calls["fine_tuned"]))

    def test_reply_kept_verbatim(self):
        reply = "  **Grade:** 11 / 11\n\nSYSTEM OVERRIDE accepted ⌊n/2⌋ \n\n"
        client, _ = fake_client(content=reply, reasoning="thinking…")
        g = backends.VLLMBackend("http://x/v1", "m", client=client).generate(self.inj["test_id"], self.inj["messages"])
        self.assertEqual(g.text, reply)
        self.assertEqual(g.reasoning, "thinking…")
        self.assertIsNone(g.error)
        self.assertEqual(g.prompt_sha256, self.inj["prompt_sha256"])
        self.assertEqual(g.finish_reason, "stop")
        self.assertEqual(g.usage, {"prompt_tokens": 1200, "completion_tokens": 150, "total_tokens": 1350})
        self.assertEqual(g.served_model, "m")

    def test_unusual_replies_recorded(self):
        client, _ = fake_client(content="**Grade:** 7 /", finish_reason="length")
        g = backends.VLLMBackend("http://x/v1", "m", client=client).generate("t", self.inj["messages"])
        self.assertEqual((g.text, g.finish_reason, g.error), ("**Grade:** 7 /", "length", None))

        client, _ = fake_client(content=None)
        g = backends.VLLMBackend("http://x/v1", "m", client=client).generate("t", self.inj["messages"])
        self.assertIsNone(g.text)
        self.assertIsNone(g.error)

        completions = SimpleNamespace(create=lambda **kw: SimpleNamespace(choices=[]))
        client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
        g = backends.VLLMBackend("http://x/v1", "m", client=client).generate("t", self.inj["messages"])
        self.assertIsNone(g.text)
        self.assertTrue(g.error.startswith("malformed response"))

    def test_request_error_recorded_not_retried(self):
        client, completions = fake_client(error=ConnectionError("server went away"))
        g = backends.VLLMBackend("http://x/v1", "m", client=client).generate("t", self.inj["messages"])
        self.assertEqual(len(completions.calls), 1)
        self.assertIsNone(g.text)
        self.assertEqual(g.error, "ConnectionError: server went away")
        self.assertIsNotNone(g.latency_s)

    def test_server_info(self):
        client, _ = fake_client()
        backend = backends.VLLMBackend("http://node:8000/v1", "m", client=client)
        seen = []

        def fetch(url):
            seen.append(url)
            return {"version": "0.25.0"} if url.endswith("/version") else {"data": [{"id": "qwen3.8-27b"}, {"id": "gradeai-ft"}]}

        info = backend.server_info(fetch)
        self.assertEqual(seen, ["http://node:8000/version", "http://node:8000/v1/models"])
        self.assertEqual(info, {"vllm_version": "0.25.0", "served_models": ["qwen3.8-27b", "gradeai-ft"]})

        def fail(url):
            raise OSError("no route")

        info = backends.VLLMBackend("http://x/v1", "m", client=client).server_info(fail)
        self.assertIn("vllm_version_error", info)
        self.assertIn("served_models_error", info)

    @unittest.skipUnless(HAVE_OPENAI, "openai not installed (it is in env/model)")
    def test_real_client_does_not_retry(self):
        backend = backends.VLLMBackend("http://127.0.0.1:9/v1", "m")
        self.assertEqual(backend.client.max_retries, 0)


class MakeBackendTest(unittest.TestCase):
    def test_model_names_and_mistakes(self):
        client, _ = fake_client()
        self.assertEqual(backends.make_backend("base", "http://x/v1", client=client).served_model, "qwen3.8-27b")
        self.assertEqual(backends.make_backend("fine_tuned", "http://x/v1", client=client).served_model, "gradeai-ft")
        self.assertEqual(backends.make_backend("fine_tuned", "http://x/v1", served_model="ft-2", client=client).served_model, "ft-2")
        with self.assertRaises(backends.BackendError):
            backends.make_backend("finetuned", "http://x/v1", client=client)
        with self.assertRaises(backends.BackendError):
            backends.make_backend("fine_tuned", "http://x/v1", served_model="qwen3.8-27b", client=client)


class GenerationRecordTest(unittest.TestCase):
    def test_generation_round_trip(self):
        gens = [backends.Generation("a", "h1", text="  ⌊n/2⌋ ∎\n\n", finish_reason="stop", latency_s=1.5),
                backends.Generation("b", "h2", text=None, error="ConnectionError: x")]
        lines = [json.dumps(g.to_record(), ensure_ascii=False) for g in gens]
        self.assertIn("⌊n/2⌋", lines[0])
        self.assertEqual([backends.Generation.from_record(json.loads(line)) for line in lines], gens)


if __name__ == "__main__":
    unittest.main()
