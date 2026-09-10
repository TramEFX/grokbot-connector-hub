import json
import unittest
from unittest.mock import patch

from hub.adapters import agensis as ag


class FakeResp:
    def __init__(self, payload):
        self._payload = json.dumps(payload).encode("utf-8")

    def read(self):
        return self._payload

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class AgensisClientTests(unittest.TestCase):
    def test_unwraps_text_json_content(self):
        adapter = ag.AgensisAdapter(
            {"id": "p_x", "adapter_config": {"mcp_url": "https://example.test/backend/mcp", "token": "aga_x"}},
            None,
            lambda job: None,
        )
        body = {
            "jsonrpc": "2.0",
            "id": 1,
            "result": {"content": [{"type": "text", "text": json.dumps({"job": None})}]},
        }
        with patch("hub.adapters.agensis.urllib.request.urlopen", return_value=FakeResp(body)):
            out = adapter.call("claim_job")
        self.assertEqual(out, {"job": None})

    def test_job_id_or_jobId(self):
        ingested = []
        adapter = ag.AgensisAdapter(
            {"id": "p_x", "adapter_config": {"mcp_url": "https://example.test/backend/mcp", "token": "aga_x"}},
            None,
            ingested.append,
        )
        with patch("hub.adapters.agensis.mailbox.put", side_effect=lambda *a, **k: {"id": "abc", "port_id": "p_x", "prompt": "hi"}):
            adapter._ingest({"jobId": "abc", "prompt": "hi"})
        self.assertEqual(ingested[0]["id"], "abc")

    def test_rejects_unsafe_id(self):
        failed = []
        adapter = ag.AgensisAdapter(
            {"id": "p_x", "adapter_config": {"mcp_url": "https://example.test/backend/mcp", "token": "aga_x"}},
            None,
            lambda job: None,
        )
        adapter.fail = lambda job_id, error: failed.append((job_id, error))
        adapter._ingest({"id": "../root", "prompt": "x"})
        self.assertEqual(failed[0][0], "../root")


if __name__ == "__main__":
    unittest.main()
