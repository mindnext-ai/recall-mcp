import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class TestServerProtocol(unittest.TestCase):
    """Drive the server over stdio exactly like an MCP client would."""

    def run_session(self, messages):
        tmp = tempfile.TemporaryDirectory()
        env = dict(os.environ)
        env["RECALL_MCP_DB"] = str(Path(tmp.name) / "srv.db")
        proc = subprocess.run(
            [sys.executable, "-m", "recall_mcp"],
            input="\n".join(json.dumps(m) for m in messages) + "\n",
            capture_output=True, text=True, env=env, timeout=30,
        )
        self.addCleanup(tmp.cleanup)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return [json.loads(line) for line in proc.stdout.splitlines() if line.strip()]

    def test_initialize_and_tools_list(self):
        responses = self.run_session([
            {"jsonrpc": "2.0", "id": 1, "method": "initialize",
             "params": {"protocolVersion": "2024-11-05"}},
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
        ])
        self.assertEqual(responses[0]["result"]["serverInfo"]["name"], "recall-mcp")
        tool_names = {t["name"] for t in responses[1]["result"]["tools"]}
        self.assertIn("add_card", tool_names)
        self.assertIn("review_card", tool_names)

    def test_full_review_flow_over_mcp(self):
        def call(idx, name, args):
            return {"jsonrpc": "2.0", "id": idx, "method": "tools/call",
                    "params": {"name": name, "arguments": args}}

        responses = self.run_session([
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
            call(2, "create_deck", {"name": "cet4"}),
            call(3, "add_card", {"deck": "cet4", "front": "abandon",
                                 "back": "v. 放弃"}),
            call(4, "due_cards", {"deck": "cet4"}),
            call(5, "review_card", {"card_id": 1, "grade": 5}),
            call(6, "due_cards", {"deck": "cet4"}),
            call(7, "review_card", {"card_id": 999, "grade": 5}),
        ])

        def payload(resp):
            return json.loads(resp["result"]["content"][0]["text"])

        due = payload(responses[3])
        self.assertEqual(len(due), 1)
        self.assertEqual(due[0]["front"], "abandon")
        # Grade 5 schedules the card one day out, so nothing is due anymore.
        reviewed = payload(responses[4])
        self.assertEqual(reviewed["interval_days"], 1)
        self.assertEqual(payload(responses[5]), [])
        # Reviewing a missing card fails gracefully instead of crashing.
        self.assertTrue(responses[6]["result"]["isError"])

    def test_unknown_method_returns_error(self):
        responses = self.run_session([
            {"jsonrpc": "2.0", "id": 9, "method": "no/such"},
        ])
        self.assertEqual(responses[0]["error"]["code"], -32601)


if __name__ == "__main__":
    unittest.main()
