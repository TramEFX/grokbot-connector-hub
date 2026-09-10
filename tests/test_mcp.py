import tempfile
import unittest
from pathlib import Path

from hub import mailbox, mcp_protocol, ports
from hub.runtime import Runtime


class McpTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.port = ports.create("bot", adapter="mock", data_dir=self.root)
        self.rt = Runtime(self.root)
        self.rt.attach(self.port["id"])

    def tearDown(self):
        self.rt.stop()
        self.tmp.cleanup()

    def rpc(self, method, params=None, req_id=1):
        msg = {"jsonrpc": "2.0", "id": req_id, "method": method}
        if params is not None:
            msg["params"] = params
        return mcp_protocol.handle_rpc(msg, self.port, self.rt)

    def test_initialize_and_list(self):
        init = self.rpc("initialize", {"protocolVersion": "2025-03-26", "capabilities": {}, "clientInfo": {"name": "test"}})
        self.assertEqual(init["result"]["serverInfo"]["name"], "grokbot-connector-hub")
        listed = self.rpc("tools/list")
        names = {t["name"] for t in listed["result"]["tools"]}
        self.assertEqual(names, {"hub_whoami", "hub_inbox", "hub_reply", "hub_fail"})

    def test_inbox_reply_reaches_adapter(self):
        self.rt.inject_mock(self.port["id"], "Write as @bot.", job_id="t1")
        inbox = self.rpc("tools/call", {"name": "hub_inbox", "arguments": {}})
        payload = inbox["result"]["content"][0]["text"]
        self.assertIn("t1", payload)
        self.rpc("tools/call", {"name": "hub_reply", "arguments": {"job_id": "t1", "text": "here"}})
        adapter = self.rt.adapters[self.port["id"]]
        self.assertEqual(adapter.submitted, [("t1", "here")])
        self.assertEqual(mailbox.list_open(self.port["id"], self.root), [])


if __name__ == "__main__":
    unittest.main()
