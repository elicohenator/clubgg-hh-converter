import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from convert import Stats, __version__, convert_text

SAMPLE = """\
Poker Hand #tour_1001: Tournament #999, Sample Event NLH No Limit - Level1(50/100) - 2024/01/15 18:00:00
Table '' 6-max Seat #1 is the button
Seat 1: Alice (1,000 in chips)
Seat 2: Bob (1,000 in chips)
Seat 3: Hero (1,000 in chips)
Alice: posts the ante 10
Bob: posts the ante 10
Hero: posts the ante 10
Bob: posts small blind 50
Hero: posts big blind 100
*** HOLE CARDS ***
Dealt to Alice 
Dealt to Bob 
Dealt to Hero [Ah Kd]
Alice: folds
Bob: folds
Uncalled bet (50) returned to Hero
*** SHOWDOWN ***
Hero collected 120 from pot
*** SUMMARY ***
Total pot 120
Seat 1: Alice folded before Flop
Seat 2: Bob(small blind) folded before Flop
Seat 3: Hero(big blind)won (120)
"""


class ConvertTest(unittest.TestCase):
    def test_rewrites_clubgg_mtt_to_ggpoker(self):
        stats = Stats()
        out, tour_id = convert_text(SAMPLE, stats)
        self.assertEqual(__version__, "1.0.0")
        self.assertEqual(tour_id, "999")
        self.assertEqual(stats.rewritten, 1)
        self.assertEqual(stats.errors, 0)
        self.assertIn("Poker Hand #TM1001:", out)
        self.assertIn("ClubGG 999 Hold'em No Limit", out)
        self.assertIn("Level1(50/100(10))", out)
        self.assertIn("Table '999' 6-max Seat #1 is the button", out)
        self.assertIn(
            "Total pot 120 | Rake 0 | Jackpot 0 | Bingo 0 | Fortune 0 | Tax 0",
            out,
        )
        self.assertIn("Seat 3: Hero (big blind) won (120)", out)


if __name__ == "__main__":
    unittest.main()
