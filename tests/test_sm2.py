import unittest

from recall_mcp.sm2 import CardState, review, MIN_EASE


class TestSM2(unittest.TestCase):
    def test_first_good_review_is_one_day(self):
        nxt = review(CardState(), 4)
        self.assertEqual(nxt.interval_days, 1)
        self.assertEqual(nxt.repetitions, 1)

    def test_second_good_review_is_six_days(self):
        state = review(CardState(), 4)
        nxt = review(state, 4)
        self.assertEqual(nxt.interval_days, 6)
        self.assertEqual(nxt.repetitions, 2)

    def test_third_interval_scales_with_ease(self):
        state = CardState(ease_factor=2.5, interval_days=6, repetitions=2)
        nxt = review(state, 4)
        self.assertEqual(nxt.interval_days, 15)  # round(6 * 2.5)
        self.assertEqual(nxt.repetitions, 3)

    def test_forgotten_card_restarts(self):
        state = CardState(ease_factor=2.5, interval_days=30, repetitions=5)
        nxt = review(state, 1)
        self.assertEqual(nxt.interval_days, 1)
        self.assertEqual(nxt.repetitions, 0)

    def test_perfect_grade_raises_ease(self):
        nxt = review(CardState(), 5)
        self.assertGreater(nxt.ease_factor, 2.5)

    def test_ease_never_below_minimum(self):
        state = CardState(ease_factor=MIN_EASE)
        nxt = review(state, 0)
        self.assertGreaterEqual(nxt.ease_factor, MIN_EASE)

    def test_invalid_grade_rejected(self):
        with self.assertRaises(ValueError):
            review(CardState(), 6)
        with self.assertRaises(ValueError):
            review(CardState(), -1)


if __name__ == "__main__":
    unittest.main()
