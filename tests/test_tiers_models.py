import json
import unittest
from types import SimpleNamespace
from unittest import mock

from bf.models import AnthropicModel, FakeModel, ModelError, TierBModel, TierViolation, select_model
from bf.tiers import TierError, classify

from .helpers import TempDirCase


class TierTests(unittest.TestCase):
    def test_default_is_b(self):
        self.assertEqual(classify("An ordinary tender.").tier, "B")

    def test_declared_public_is_a(self):
        self.assertEqual(classify("An ordinary tender.", declared_public=True).tier, "A")

    def test_confidential_marker_beats_public_declaration(self):
        r = classify("This RFP is confidential.", declared_public=True)
        self.assertEqual(r.tier, "B")
        self.assertTrue(any("confidential" in x.lower() for x in r.reasons))

    def test_third_party_prohibition_is_c(self):
        self.assertEqual(classify("Third-party processing is strictly prohibited.").tier, "C")
        self.assertEqual(classify("These documents must not be shared with any third party.").tier, "C")

    def test_tier_can_be_raised_not_lowered(self):
        self.assertEqual(classify("plain", declared_public=True, requested="B").tier, "B")
        with self.assertRaises(TierError):
            classify("This RFP is confidential.", requested="A")

    def test_solution_residency_does_not_raise_tier(self):
        r = classify("All data must be hosted within the Kingdom of Saudi Arabia.", declared_public=True)
        self.assertEqual(r.tier, "A")
        self.assertTrue(r.residency_mentions)


def _response(text, stop="end_turn"):
    return SimpleNamespace(content=[SimpleNamespace(type="text", text=text)], stop_reason=stop,
                           usage=SimpleNamespace(input_tokens=11, output_tokens=7))


class RouterTests(TempDirCase):
    def test_non_resident_model_refused_for_tier_b(self):
        with self.assertRaises(TierViolation):
            select_model("anthropic", "B")

    def test_tier_c_refused_even_for_rules(self):
        with self.assertRaises(TierViolation):
            select_model("rules", "C")

    def test_auto_without_configuration_runs_on_rules(self):
        self.assertIsNone(select_model("auto", "A"))
        self.assertIsNone(select_model("auto", "B"))

    def test_fake_model_refuses_tier_c(self):
        with self.assertRaises(TierViolation):
            FakeModel(lambda *a: {}).json(task="t", system="s", user="u", schema={}, tier="C")

    def test_anthropic_request_shape_and_log_has_no_content(self):
        client = mock.MagicMock()
        client.beta.messages.create.return_value = _response('{"ok": true}')
        log = self.tmp / "calls.jsonl"
        m = AnthropicModel(client=client, model="claude-opus-5-5", log_path=log)
        out = m.json(task="matrix_judgement", system="sys", user="SECRET USER TEXT", schema={"type": "object"}, tier="A")
        self.assertEqual(out, {"ok": True})
        kwargs = client.beta.messages.create.call_args.kwargs
        self.assertEqual(kwargs["betas"], ["server-side-fallback-2026-07-01"])
        self.assertEqual(kwargs["fallbacks"], "default")
        self.assertEqual(kwargs["output_config"]["format"]["type"], "json_schema")
        self.assertEqual(kwargs["model"], "claude-opus-5-5")
        entry = json.loads(log.read_text().strip())
        self.assertEqual(entry["provider"], "anthropic")
        self.assertEqual(entry["input_tokens"], 11)
        self.assertNotIn("SECRET", log.read_text())

    def test_other_models_use_plain_messages_endpoint(self):
        client = mock.MagicMock()
        client.messages.create.return_value = _response("## Section\n\nText")
        m = AnthropicModel(client=client, model="claude-haiku-5-5")
        self.assertTrue(m.text(task="draft", system="s", user="u", tier="A").startswith("## Section"))
        client.beta.messages.create.assert_not_called()

    def test_anthropic_refuses_tier_b_before_any_call(self):
        client = mock.MagicMock()
        m = AnthropicModel(client=client)
        with self.assertRaises(TierViolation):
            m.json(task="t", system="s", user="u", schema={}, tier="B")
        client.beta.messages.create.assert_not_called()
        client.messages.create.assert_not_called()

    def test_refusal_and_truncation_raise(self):
        client = mock.MagicMock()
        client.beta.messages.create.return_value = _response("{}", stop="refusal")
        with self.assertRaises(ModelError):
            AnthropicModel(client=client).json(task="t", system="s", user="u", schema={}, tier="A")

    def test_tier_b_endpoint_request(self):
        seen = {}

        class Resp:
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def read(self):
                return json.dumps({"choices": [{"message": {"content": '```json\n{"a": 1}\n```'}}],
                                   "usage": {"prompt_tokens": 3, "completion_tokens": 2}}).encode()

        def opener(req, timeout):
            seen["url"] = req.full_url
            seen["body"] = json.loads(req.data)
            return Resp()

        m = TierBModel(url="https://llm.example.sa/v1", model="local-70b", key="k", opener=opener)
        self.assertEqual(m.json(task="t", system="s", user="u", schema={"type": "object"}, tier="B"), {"a": 1})
        self.assertEqual(seen["url"], "https://llm.example.sa/v1/chat/completions")
        self.assertEqual(seen["body"]["response_format"]["type"], "json_schema")
        with self.assertRaises(TierViolation):
            m.text(task="t", system="s", user="u", tier="C")


if __name__ == "__main__":
    unittest.main()
