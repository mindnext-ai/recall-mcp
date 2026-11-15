"""Human-facing command line interface for recall-mcp.

Shares the same SQLite database as the MCP server, so cards you add
here are the same cards your agent reviews through MCP.

Examples:
    recall deck create cet4 --description "CET-4 vocabulary"
    recall card add cet4 --front "abandon" --back "v. 放弃；抛弃"
    recall import cet4 examples/cet4_sample.json
    recall due
    recall review 3 5        # card id 3, grade 5
    recall stats cet4
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .server import default_db_path
from .store import Store, StoreError


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="recall", description="Spaced-repetition flashcards")
    p.add_argument("--db", default=str(default_db_path()),
                   help="database file (default: %(default)s)")
    sub = p.add_subparsers(dest="group", required=True)

    deck = sub.add_parser("deck", help="deck operations").add_subparsers(
        dest="action", required=True)
    c = deck.add_parser("create")
    c.add_argument("name")
    c.add_argument("--description", default="")
    deck.add_parser("list")

    card = sub.add_parser("card", help="card operations").add_subparsers(
        dest="action", required=True)
    a = card.add_parser("add")
    a.add_argument("deck")
    a.add_argument("--front", required=True)
    a.add_argument("--back", required=True)
    a.add_argument("--tags", default="")
    lst = card.add_parser("list")
    lst.add_argument("deck")
    lst.add_argument("--limit", type=int, default=50)
    d = card.add_parser("delete")
    d.add_argument("card_id", type=int)

    imp = sub.add_parser("import", help="import cards from a JSON file")
    imp.add_argument("deck")
    imp.add_argument("file", help='JSON list of {"front": ..., "back": ..., "tags": ...}')

    due = sub.add_parser("due", help="show cards due today")
    due.add_argument("deck", nargs="?")
    due.add_argument("--limit", type=int, default=20)

    rev = sub.add_parser("review", help="record a review (grade 0-5)")
    rev.add_argument("card_id", type=int)
    rev.add_argument("grade", type=int)

    st = sub.add_parser("stats")
    st.add_argument("deck")
    return p


def _print(data) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2))


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    store = Store(Path(args.db))
    try:
        if args.group == "deck" and args.action == "create":
            _print(store.create_deck(args.name, args.description))
        elif args.group == "deck" and args.action == "list":
            _print(store.list_decks())
        elif args.group == "card" and args.action == "add":
            _print(store.add_card(args.deck, args.front, args.back, args.tags))
        elif args.group == "card" and args.action == "list":
            _print(store.list_cards(args.deck, args.limit))
        elif args.group == "card" and args.action == "delete":
            _print(store.delete_card(args.card_id))
        elif args.group == "import":
            items = json.loads(Path(args.file).read_text(encoding="utf-8"))
            added = [store.add_card(args.deck, it["front"], it["back"],
                                    it.get("tags", "")) for it in items]
            _print({"imported": len(added), "deck": args.deck})
        elif args.group == "due":
            _print(store.due_cards(args.deck, args.limit))
        elif args.group == "review":
            _print(store.review_card(args.card_id, args.grade))
        elif args.group == "stats":
            _print(store.deck_stats(args.deck))
    except StoreError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    finally:
        store.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
