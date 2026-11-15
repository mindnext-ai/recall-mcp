"""A zero-dependency MCP server for spaced-repetition flashcards.

Implements the Model Context Protocol over stdio (newline-delimited
JSON-RPC 2.0) using only the Python standard library, so it runs
anywhere Python 3.10+ runs — no pip install of an SDK required.

Tools exposed:
    create_deck, list_decks, add_card, list_cards, due_cards,
    review_card, deck_stats, delete_card

Database location: $RECALL_MCP_DB, default ~/.recall-mcp/recall.db
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from .store import Store, StoreError

SERVER_NAME = "recall-mcp"
SERVER_VERSION = "0.1.0"
DEFAULT_PROTOCOL = "2024-11-05"


def default_db_path() -> Path:
    env = os.environ.get("RECALL_MCP_DB")
    if env:
        return Path(env)
    return Path.home() / ".recall-mcp" / "recall.db"


TOOLS = [
    {
        "name": "create_deck",
        "description": "Create a new flashcard deck.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Unique deck name"},
                "description": {"type": "string", "description": "Optional deck description"},
            },
            "required": ["name"],
        },
    },
    {
        "name": "list_decks",
        "description": "List all decks with card counts and how many cards are due today.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "add_card",
        "description": "Add a flashcard to a deck. New cards are due immediately.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "deck": {"type": "string"},
                "front": {"type": "string", "description": "Question / prompt side"},
                "back": {"type": "string", "description": "Answer side"},
                "tags": {"type": "string", "description": "Optional comma-separated tags"},
            },
            "required": ["deck", "front", "back"],
        },
    },
    {
        "name": "list_cards",
        "description": "List cards in a deck.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "deck": {"type": "string"},
                "limit": {"type": "integer", "description": "Max cards to return (default 50)"},
            },
            "required": ["deck"],
        },
    },
    {
        "name": "due_cards",
        "description": "Get cards due for review today, oldest due first. "
                       "Omit deck to get due cards across all decks.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "deck": {"type": "string"},
                "limit": {"type": "integer", "description": "Max cards to return (default 20)"},
            },
        },
    },
    {
        "name": "review_card",
        "description": "Record a review of a card and schedule its next appearance "
                       "with the SM-2 algorithm. Grade 0-5: 5 perfect recall, "
                       "3 barely recalled, below 3 forgotten.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "card_id": {"type": "integer"},
                "grade": {"type": "integer", "minimum": 0, "maximum": 5},
            },
            "required": ["card_id", "grade"],
        },
    },
    {
        "name": "deck_stats",
        "description": "Statistics for one deck: total cards, due today, new cards, average ease factor.",
        "inputSchema": {
            "type": "object",
            "properties": {"deck": {"type": "string"}},
            "required": ["deck"],
        },
    },
    {
        "name": "delete_card",
        "description": "Delete a card by id.",
        "inputSchema": {
            "type": "object",
            "properties": {"card_id": {"type": "integer"}},
            "required": ["card_id"],
        },
    },
]


class RecallServer:
    def __init__(self, store: Store):
        self.store = store

    # -- tool dispatch --------------------------------------------------

    def call_tool(self, name: str, args: dict):
        s = self.store
        if name == "create_deck":
            return s.create_deck(args["name"], args.get("description", ""))
        if name == "list_decks":
            return s.list_decks()
        if name == "add_card":
            return s.add_card(args["deck"], args["front"], args["back"],
                              args.get("tags", ""))
        if name == "list_cards":
            return s.list_cards(args["deck"], int(args.get("limit", 50)))
        if name == "due_cards":
            return s.due_cards(args.get("deck"), int(args.get("limit", 20)))
        if name == "review_card":
            return s.review_card(int(args["card_id"]), int(args["grade"]))
        if name == "deck_stats":
            return s.deck_stats(args["deck"])
        if name == "delete_card":
            return s.delete_card(int(args["card_id"]))
        raise StoreError(f"unknown tool: {name}")

    # -- JSON-RPC --------------------------------------------------------

    def handle(self, msg: dict) -> dict | None:
        method = msg.get("method", "")
        msg_id = msg.get("id")
        is_notification = msg_id is None

        if method == "initialize":
            params = msg.get("params") or {}
            protocol = params.get("protocolVersion", DEFAULT_PROTOCOL)
            return self._result(msg_id, {
                "protocolVersion": protocol,
                "capabilities": {"tools": {}},
                "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
            })
        if method in ("notifications/initialized", "notifications/cancelled"):
            return None
        if method == "ping":
            return self._result(msg_id, {})
        if method == "tools/list":
            return self._result(msg_id, {"tools": TOOLS})
        if method == "tools/call":
            params = msg.get("params") or {}
            try:
                data = self.call_tool(params.get("name", ""),
                                      params.get("arguments") or {})
                text = json.dumps(data, ensure_ascii=False, indent=2)
                return self._result(msg_id, {
                    "content": [{"type": "text", "text": text}],
                    "isError": False,
                })
            except (StoreError, ValueError, KeyError) as exc:
                return self._result(msg_id, {
                    "content": [{"type": "text", "text": f"error: {exc}"}],
                    "isError": True,
                })
        if is_notification:
            return None
        return self._error(msg_id, -32601, f"method not found: {method}")

    @staticmethod
    def _result(msg_id, result: dict) -> dict:
        return {"jsonrpc": "2.0", "id": msg_id, "result": result}

    @staticmethod
    def _error(msg_id, code: int, message: str) -> dict:
        return {"jsonrpc": "2.0", "id": msg_id,
                "error": {"code": code, "message": message}}


def main() -> None:
    store = Store(default_db_path())
    server = RecallServer(store)
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue
        response = server.handle(msg)
        if response is not None:
            sys.stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
