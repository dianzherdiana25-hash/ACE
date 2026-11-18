"""EVO 0009 bridge transport tests for brain_endpoints.

Bridge mode (ACE_BRAIN_BRIDGE_URL set) routes every organ through
the brain bridge by ROLE: proposers keep their names, the pair's
validator becomes the bridge cross-validator role, embedding goes
to the bridge embedding role, and the serving organ comes back as
brain_of_origin provenance. Local-slate behaviour is unchanged
when the variable is unset. All transport is mocked at
brain_endpoints._request; nothing here touches a network.
"""
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from ace_operational import brain_endpoints as be  # noqa: E402

BRIDGE = "http://127.0.0.1:18931"


def bridge_env():
    return mock.patch.dict(os.environ,
                           {be.BRIDGE_ENV_VAR: BRIDGE})


class BridgeModeDetectionTests(unittest.TestCase):
    def test_unset_means_local_mode(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertFalse(be.bridge_mode())
            self.assertIsNone(be.bridge_url())

    def test_set_means_bridge_mode(self):
        with bridge_env():
            self.assertTrue(be.bridge_mode())
            self.assertEqual(be.bridge_url(), BRIDGE)

    def test_validator_organ_is_bridge_only(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(ValueError):
                be.organ_url("validator")
        with bridge_env():
            self.assertEqual(be.organ_url("validator"), BRIDGE)

    def test_all_organs_route_to_bridge(self):
        with bridge_env():
            for organ in ("front", "coder", "embedding", "a3b"):
                self.assertEqual(be.organ_url(organ), BRIDGE)


class BridgePairTests(unittest.TestCase):
    def test_code_pair(self):
        with bridge_env():
            pair = be.proposer_validator_pair("code")
            self.assertEqual(pair.proposer, "coder")
            self.assertEqual(pair.validator, "validator")

    def test_language_pair(self):
        with bridge_env():
            pair = be.proposer_validator_pair("language")
            self.assertEqual(pair.proposer, "front")
            self.assertEqual(pair.validator, "validator")

    def test_pair_record_names_the_transport(self):
        with bridge_env():
            record = be.proposer_validator_pair("code").as_dict()
            self.assertEqual(record["transport"], "bridge")
            self.assertEqual(record["bridge_roles"]["validator"],
                             "validator")

    def test_local_pair_unchanged(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            pair = be.proposer_validator_pair("code")
            self.assertEqual((pair.proposer, pair.validator),
                             ("coder", "front"))
            self.assertNotIn("transport", pair.as_dict())


class BridgeChatTests(unittest.TestCase):
    def _canned(self, url, payload, timeout):
        self.seen_url = url
        self.seen_payload = payload
        return {"choices": [{"message": {"content": "answer"}}],
                "brain_of_origin": "groq/openai/gpt-oss-120b"}

    def test_chat_posts_role_and_returns_origin(self):
        with bridge_env(), mock.patch.object(
                be, "_request", self._canned), mock.patch.object(
                be, "health", return_value=True):
            result = be.chat("validator",
                             [{"role": "user", "content": "hi"}],
                             max_tokens=64)
        self.assertEqual(self.seen_url,
                         BRIDGE + "/v1/chat/completions")
        self.assertEqual(self.seen_payload["role"], "validator")
        self.assertEqual(result.content, "answer")
        self.assertEqual(result.brain_of_origin,
                         "groq/openai/gpt-oss-120b")
        self.assertFalse(result.organ_woke)

    def test_a3b_has_no_bridge_role(self):
        with bridge_env(), mock.patch.object(
                be, "health", return_value=True):
            with self.assertRaises(be.BrainUnavailable):
                be.chat("a3b", [{"role": "user", "content": "hi"}])

    def test_ensure_organ_bridge_semantics(self):
        with bridge_env():
            with mock.patch.object(be, "health", return_value=True):
                self.assertFalse(be.ensure_organ("front"))
            with mock.patch.object(be, "health", return_value=False):
                with self.assertRaises(be.BrainUnavailable):
                    be.ensure_organ("front")


class BridgeEmbedTests(unittest.TestCase):
    def test_embed_posts_per_text(self):
        calls = []

        def canned(url, payload, timeout):
            calls.append((url, payload))
            return {"data": [{"embedding": [0.1, 0.2]}]}

        with bridge_env(), mock.patch.object(
                be, "_request", canned), mock.patch.object(
                be, "health", return_value=True):
            vectors = be.embed(["one", "two"])
        self.assertEqual(vectors, [[0.1, 0.2], [0.1, 0.2]])
        self.assertEqual([c[1]["role"] for c in calls],
                         ["embedding", "embedding"])
        self.assertTrue(all(
            c[0] == BRIDGE + "/v1/embeddings" for c in calls))

    def test_embed_malformed_shape_fails_closed(self):
        with bridge_env(), mock.patch.object(
                be, "_request", return_value={"nope": 1}), \
                mock.patch.object(be, "health", return_value=True):
            with self.assertRaises(be.BrainUnavailable):
                be.embed(["one"])


if __name__ == "__main__":
    unittest.main()
