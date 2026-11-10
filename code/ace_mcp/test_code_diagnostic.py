"""Fail-closed and opt-in contracts for the experimental diagnostic."""
import unittest
from unittest.mock import patch
from ace_mcp.bridge import ACEBridge, json_rpc
from ace_mcp.code_diagnostic import evaluate
from ace_mcp.server import main

class CodeDiagnosticTests(unittest.TestCase):
    def test_disabled_by_default(self):
        bridge = ACEBridge('/tmp/ace-diagnostic-test')
        self.assertNotIn('ace_code_diagnostic', [t['name'] for t in bridge.tools()])
        self.assertNotIn('ace_patch_diagnostic', [t['name'] for t in bridge.tools()])
        with self.assertRaises(ValueError):
            bridge.call('ace_code_diagnostic', {'source': 'x=1'})

    def test_patch_diagnostic_is_fixed_target_and_opt_in(self):
        bridge = ACEBridge('/tmp/ace-diagnostic-test', enable_code_diagnostic=True)
        with patch('ace_code_agent.patch_diagnostic.evaluate_patch', return_value={'promotion_authorized': False}) as run:
            result = bridge.call('ace_patch_diagnostic', {'snippet': '# test'})
        self.assertFalse(result['promotion_authorized'])
        self.assertEqual(run.call_args.args[1], 'code/ace_self_dev/strategy_repair.py')

    def test_sandbox_missing_fails_closed(self):
        with patch('ace_mcp.code_diagnostic.shutil.which', return_value=None):
            with self.assertRaisesRegex(RuntimeError, 'BLOCKED_ENVIRONMENT'):
                evaluate('def candidate_fn(w): return True')

    def test_untrusted_source_budget(self):
        for source in ('', 'a' * 4097, None):
            with self.assertRaises(ValueError):
                evaluate(source)

    def test_restricted_to_stdio(self):
        with self.assertRaises(SystemExit):
            main(['--workspace', '/tmp/ace-diagnostic-test', '--transport', 'http', '--enable-code-diagnostic'])

    def test_mcp_reports_sandbox_error(self):
        bridge = ACEBridge('/tmp/ace-diagnostic-test', enable_code_diagnostic=True)
        with patch('ace_mcp.code_diagnostic.shutil.which', return_value=None):
            result = json_rpc({'jsonrpc':'2.0','id':1,'method':'tools/call', 'params':{'name':'ace_code_diagnostic','arguments':{'source':'x=1'}}}, bridge)
        self.assertTrue(result['result']['isError'])
        self.assertIn('BLOCKED_ENVIRONMENT', result['result']['content'][0]['text'])
