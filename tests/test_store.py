import tempfile
import unittest
from pathlib import Path

from recall_mcp.store import Store, StoreError


class TestStore(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.tmp.name) / "test.db")

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def test_deck_and_card_flow(self):
        self.store.create_deck("cet4", "vocabulary")
        card = self.store.add_card("cet4", "abandon", "v. 放弃")
        self.assertEqual(card["front"], "abandon")
        # New cards are due immediately.
        due = self.store.due_cards("cet4")
        self.assertEqual(len(due), 1)
        self.assertEqual(due[0]["id"], card["id"])

    def test_review_pushes_due_date_forward(self):
        self.store.create_deck("d")
        card = self.store.add_card("d", "q", "a")
        reviewed = self.store.review_card(card["id"], 5)
        self.assertEqual(reviewed["interval_days"], 1)
        self.assertEqual(self.store.due_cards("d"), [])

    def test_duplicate_deck_rejected(self):
        self.store.create_deck("d")
        with self.assertRaises(StoreError):
            self.store.create_deck("d")

    def test_missing_deck_rejected(self):
        with self.assertRaises(StoreError):
            self.store.add_card("nope", "q", "a")

    def test_stats(self):
        self.store.create_deck("d")
        self.store.add_card("d", "q1", "a1")
        self.store.add_card("d", "q2", "a2")
        stats = self.store.deck_stats("d")
        self.assertEqual(stats["total"], 2)
        self.assertEqual(stats["due"], 2)
        self.assertEqual(stats["new_cards"], 2)

    def test_delete_card(self):
        self.store.create_deck("d")
        card = self.store.add_card("d", "q", "a")
        self.store.delete_card(card["id"])
        self.assertEqual(self.store.list_cards("d"), [])


if __name__ == "__main__":
    unittest.main()
