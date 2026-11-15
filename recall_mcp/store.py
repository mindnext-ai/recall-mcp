"""SQLite storage for decks and flashcards.

Single-file database, standard library only. All scheduling state lives
on the card row; SM-2 transitions are computed in :mod:`recall_mcp.sm2`.
"""

from __future__ import annotations

import sqlite3
from datetime import date, timedelta
from pathlib import Path

from .sm2 import CardState, review

SCHEMA = """
CREATE TABLE IF NOT EXISTS decks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    description TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS cards (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    deck_id INTEGER NOT NULL REFERENCES decks(id) ON DELETE CASCADE,
    front TEXT NOT NULL,
    back TEXT NOT NULL,
    tags TEXT NOT NULL DEFAULT '',
    ease_factor REAL NOT NULL DEFAULT 2.5,
    interval_days INTEGER NOT NULL DEFAULT 0,
    repetitions INTEGER NOT NULL DEFAULT 0,
    due_date TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_cards_due ON cards(deck_id, due_date);
"""


class StoreError(Exception):
    pass


class Store:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        if self.db_path.parent != Path(""):
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    # -- decks ---------------------------------------------------------

    def create_deck(self, name: str, description: str = "") -> dict:
        name = name.strip()
        if not name:
            raise StoreError("deck name must not be empty")
        try:
            cur = self.conn.execute(
                "INSERT INTO decks (name, description, created_at) VALUES (?, ?, ?)",
                (name, description, date.today().isoformat()),
            )
            self.conn.commit()
        except sqlite3.IntegrityError:
            raise StoreError(f"deck already exists: {name}") from None
        return self.get_deck(name) | {"id": cur.lastrowid}

    def get_deck(self, name: str) -> dict:
        row = self.conn.execute(
            "SELECT * FROM decks WHERE name = ?", (name,)
        ).fetchone()
        if row is None:
            raise StoreError(f"deck not found: {name}")
        return dict(row)

    def list_decks(self) -> list[dict]:
        rows = self.conn.execute(
            """SELECT d.*, COUNT(c.id) AS card_count,
                      SUM(CASE WHEN c.due_date <= ? THEN 1 ELSE 0 END) AS due_count
               FROM decks d LEFT JOIN cards c ON c.deck_id = d.id
               GROUP BY d.id ORDER BY d.name""",
            (date.today().isoformat(),),
        ).fetchall()
        return [dict(r) for r in rows]

    # -- cards ---------------------------------------------------------

    def add_card(self, deck: str, front: str, back: str, tags: str = "") -> dict:
        d = self.get_deck(deck)
        front, back = front.strip(), back.strip()
        if not front or not back:
            raise StoreError("card front and back must not be empty")
        today = date.today().isoformat()
        cur = self.conn.execute(
            """INSERT INTO cards (deck_id, front, back, tags, due_date, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (d["id"], front, back, tags.strip(), today, today),
        )
        self.conn.commit()
        return self.get_card(cur.lastrowid)

    def get_card(self, card_id: int) -> dict:
        row = self.conn.execute(
            """SELECT c.*, d.name AS deck FROM cards c
               JOIN decks d ON d.id = c.deck_id WHERE c.id = ?""",
            (card_id,),
        ).fetchone()
        if row is None:
            raise StoreError(f"card not found: {card_id}")
        return dict(row)

    def list_cards(self, deck: str, limit: int = 50) -> list[dict]:
        d = self.get_deck(deck)
        rows = self.conn.execute(
            """SELECT c.*, d.name AS deck FROM cards c
               JOIN decks d ON d.id = c.deck_id
               WHERE c.deck_id = ? ORDER BY c.id LIMIT ?""",
            (d["id"], limit),
        ).fetchall()
        return [dict(r) for r in rows]

    def due_cards(self, deck: str | None = None, limit: int = 20) -> list[dict]:
        today = date.today().isoformat()
        if deck is not None:
            d = self.get_deck(deck)
            rows = self.conn.execute(
                """SELECT c.*, d.name AS deck FROM cards c
                   JOIN decks d ON d.id = c.deck_id
                   WHERE c.deck_id = ? AND c.due_date <= ?
                   ORDER BY c.due_date, c.id LIMIT ?""",
                (d["id"], today, limit),
            ).fetchall()
        else:
            rows = self.conn.execute(
                """SELECT c.*, d.name AS deck FROM cards c
                   JOIN decks d ON d.id = c.deck_id
                   WHERE c.due_date <= ?
                   ORDER BY c.due_date, c.id LIMIT ?""",
                (today, limit),
            ).fetchall()
        return [dict(r) for r in rows]

    def review_card(self, card_id: int, grade: int) -> dict:
        card = self.get_card(card_id)
        state = CardState(
            ease_factor=card["ease_factor"],
            interval_days=card["interval_days"],
            repetitions=card["repetitions"],
        )
        nxt = review(state, grade)
        due = (date.today() + timedelta(days=nxt.interval_days)).isoformat()
        self.conn.execute(
            """UPDATE cards SET ease_factor = ?, interval_days = ?,
                   repetitions = ?, due_date = ? WHERE id = ?""",
            (nxt.ease_factor, nxt.interval_days, nxt.repetitions, due, card_id),
        )
        self.conn.commit()
        return self.get_card(card_id)

    def delete_card(self, card_id: int) -> dict:
        card = self.get_card(card_id)
        self.conn.execute("DELETE FROM cards WHERE id = ?", (card_id,))
        self.conn.commit()
        return {"deleted": card_id, "deck": card["deck"], "front": card["front"]}

    def deck_stats(self, deck: str) -> dict:
        d = self.get_deck(deck)
        today = date.today().isoformat()
        row = self.conn.execute(
            """SELECT COUNT(*) AS total,
                      SUM(CASE WHEN due_date <= ? THEN 1 ELSE 0 END) AS due,
                      SUM(CASE WHEN repetitions = 0 AND interval_days = 0
                               THEN 1 ELSE 0 END) AS new_cards,
                      AVG(ease_factor) AS avg_ease
               FROM cards WHERE deck_id = ?""",
            (today, d["id"]),
        ).fetchone()
        stats = dict(row)
        stats["deck"] = deck
        stats["due"] = stats["due"] or 0
        stats["new_cards"] = stats["new_cards"] or 0
        if stats["avg_ease"] is not None:
            stats["avg_ease"] = round(stats["avg_ease"], 3)
        return stats
