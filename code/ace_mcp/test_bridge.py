"""MCP bridge integration and JSON-RPC safety tests using real ACE runtime."""
import io
import json
from pathlib import Path
import tempfile
import unittest

from .bridge import ACEBridge, TOOL_SPECS, PROTOCOL, ToolInputError, json_rpc
from .server import stdio


def request(id, method, params=None):
    value={"jsonrpc":"2.0","id":id,"method":method}
    if params is not None:
        value["params"]=params
    return value


class BridgeTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root=Path(tmp.name)/"ace-work"
        self.readonly=ACEBridge(self.root)
        self.writable=ACEBridge(self.root,allow_writes=True)

    def test_initialize_and_six_bounded_tools(self):
        init=json_rpc(request(1,"initialize",{"protocolVersion":PROTOCOL}),self.readonly)
        self.assertEqual(PROTOCOL,init["result"]["protocolVersion"])
        tools=json_rpc(request(2,"tools/list"),self.readonly)["result"]["tools"]
        self.assertEqual(6,len(tools))
        self.assertEqual({x["name"] for x in TOOL_SPECS},{x["name"] for x in tools})
        self.assertTrue(all(x["inputSchema"]["additionalProperties"] is False for x in tools))

    def test_readonly_rejects_all_mutations(self):
        for name,args in (("ace_submit_task",{"name":"x","train":[],"validation":[]}),
                          ("ace_run_tasks",{"max_tasks":1}),
                          ("ace_evaluate",{"task_id":"0"*64,"rows":[]})):
            result=json_rpc(request(3,"tools/call",{"name":name,"arguments":args}),self.readonly)
            self.assertIs(result["result"]["isError"],True)
            self.assertIn("disabled",result["result"]["content"][0]["text"])

    def test_run_budget_and_argument_validation(self):
        for args in ({"max_tasks":True},{"max_tasks":0},{"max_tasks":17},
                     {"max_tasks":1,"extra":"unexpected"},{"max_tasks":"2"}):
            with self.assertRaises((ValueError,ToolInputError)):
                self.writable.call("ace_run_tasks",args)
        self.assertEqual(0,self.writable.call("ace_status",{})["pending"])

    def test_invalid_method_and_tool(self):
        self.assertEqual(-32601,json_rpc(request(7,"unknown"),self.readonly)["error"]["code"])
        result=json_rpc(request(8,"tools/call",{
            "name":"ace_unlisted","arguments":{}}),self.readonly)
        self.assertTrue(result["result"]["isError"])
        self.assertNotIn("Traceback",result["result"]["content"][0]["text"])

    def test_stdio_notifications_and_parse_errors(self):
        items=[json.dumps(request(1,"initialize",{"protocolVersion":PROTOCOL})),
               json.dumps({"jsonrpc":"2.0","method":"notifications/initialized"}),
               json.dumps(request(2,"tools/list")),"{invalid"]
        sink=io.StringIO()
        stdio(self.readonly,io.StringIO("\n".join(items)+"\n"),sink)
        responses=[json.loads(line) for line in sink.getvalue().splitlines()]
        self.assertEqual(3,len(responses))
        self.assertEqual([1,2,None],[x["id"] for x in responses])
        self.assertEqual(-32700,responses[-1]["error"]["code"])

    def test_bool_rpc_id_rejected(self):
        self.assertEqual(-32600,json_rpc(request(True,"ping"),self.readonly)["error"]["code"])

    def test_real_runtime_end_to_end_resume_and_terminal_receipt(self):
        from ace_capability_evolution.compositional import bank
        train,validation,terminal=bank("equal",20261106)
        args={"name":"mcp_equal","train":train,"validation":validation}
        task_id=self.writable.call("ace_submit_task",args)["task_id"]
        self.assertEqual(task_id,self.writable.call("ace_submit_task",args)["task_id"])
        outcome=self.writable.call("ace_run_tasks",{"max_tasks":1})["outcomes"]
        self.assertEqual(1,len(outcome))
        self.assertTrue(outcome[0]["staged"])
        self.assertTrue(self.readonly.call("ace_predict",{"task_id":task_id,"word":"aabb"})["prediction"])
        self.assertFalse(self.readonly.call("ace_predict",{"task_id":task_id,"word":"aaab"})["prediction"])
        result=self.writable.call("ace_evaluate",{"task_id":task_id,"rows":terminal})
        self.assertEqual(128,result["evaluation"]["correct"])
        self.assertEqual(128,self.writable.call("ace_evaluate",{
            "task_id":task_id,"rows":terminal})["evaluation"]["correct"])
        self.assertEqual(task_id,self.readonly.call("ace_get_report",{
            "task_id":task_id})["task_id"])
        fresh=ACEBridge(self.root)
        self.assertEqual(1,fresh.call("ace_status",{})["completed"])
        altered=list(terminal)
        altered[0]=[altered[0][0],not altered[0][1]]
        with self.assertRaises(ValueError):
            self.writable.call("ace_evaluate",{"task_id":task_id,"rows":altered})

    def test_invalid_rows_and_words(self):
        with self.assertRaises(ToolInputError):
            self.readonly.call("ace_predict",{"task_id":"0"*64,"word":"unsupported/word"})
        with self.assertRaises(ToolInputError):
            self.readonly.call("ace_get_report",{"task_id":True})
        with self.assertRaises(ValueError):
            self.writable.call("ace_submit_task",{
                "name":"bad","train":[["a",1]],"validation":[["b",False]]})
        with self.assertRaises(ValueError):
            self.writable.call("ace_submit_task",{
                "name":"overlap","train":[["a",True]],"validation":[["a",False]]})


if __name__=="__main__":
    unittest.main()
