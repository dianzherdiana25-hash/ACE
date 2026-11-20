"""Uji rencana cutover dan rollback dengan konfigurasi sintetis."""
import shlex
import unittest

from tools.bridge_home import markdown, plan_home


CONFIG = {"repo": "/tmp/fixture repo", "helpers": "/tmp/fixture helpers", "port": 8090,
          "budget_state": "/tmp/new state.json", "call_log": "/tmp/calls.jsonl",
          "stdout_log": "/tmp/fixture stdout", "pid_file": "/tmp/fixture pid",
          "current_bridge_url": "http://127.0.0.1:19999"}


class BridgeHomeTests(unittest.TestCase):
    def test_launch_and_health_precede_cutover(self):
        result = plan_home(CONFIG)
        steps = {step["id"]: step for step in result["steps"]}
        self.assertEqual(list(steps), ["preflight", "launch", "health", "cutover"])
        command = steps["launch"]["action"]
        argv = shlex.split(command.partition(" > ")[0])
        self.assertEqual(argv[:3], ["nohup", "python3", "/tmp/fixture repo/tools/brain_bridge.py"])
        self.assertEqual(argv[argv.index("--state") + 1], CONFIG["budget_state"])
        self.assertIn("http://127.0.0.1:8090/health", steps["health"]["action"])
        self.assertIn("Verifikasi", markdown(result))

    def test_rollback_names_old_url_and_health(self):
        result = plan_home(CONFIG)
        text = markdown(result)
        self.assertIn("## Langkah mundur", text)
        self.assertIn("ACE_BRAIN_BRIDGE_URL=http://127.0.0.1:19999", text)
        self.assertIn("http://127.0.0.1:19999/health", text)

    def test_invalid_or_equal_targets_refused(self):
        for change in ({"port": True}, {"current_bridge_url": "http://127.0.0.1:8090"},
                       {"repo": "relative"}, {"pid_file": CONFIG["call_log"]}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                plan_home({**CONFIG, **change})


if __name__ == "__main__":
    unittest.main()
