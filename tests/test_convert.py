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
        self.assertEqual(__version__, "1.0.2")
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

    def test_heads_up_walk_uses_2max_and_uncalled_bb(self):
        src = """\
Poker Hand #tour_2002: Tournament #999, Sample Event NLH No Limit - Level1(50/100) - 2024/01/15 18:00:00
Table '' 8-max Seat #8 is the button
Seat 8: Hero (1,000 in chips)
Seat 7: Villain (1,000 in chips)
Hero: posts the ante 10
Villain: posts the ante 10
Hero: posts small blind 50
Villain: posts big blind 100
*** HOLE CARDS ***
Dealt to Hero [Ah Kd]
Dealt to Villain 
Hero: folds
*** SHOWDOWN ***
Villain collected 170 from pot
*** SUMMARY ***
Total pot 170
Seat 8: Hero(button) folded before Flop
Seat 7: Villain(big blind)won (170)
"""
        out, _ = convert_text(src, Stats())
        self.assertIn("Table '999' 2-max Seat #8 is the button", out)
        self.assertIn("Seat 8: Hero (button) (small blind) folded before Flop", out)
        self.assertIn("Uncalled bet (100) returned to Villain", out)
        self.assertIn("Villain collected 70 from pot", out)
        self.assertIn("Total pot 70 | Rake 0 | Jackpot 0 | Bingo 0 | Fortune 0 | Tax 0", out)
        self.assertIn("Seat 7: Villain (big blind) won (70)", out)

    def test_same_winner_side_pots_are_merged(self):
        src = """\
Poker Hand #tour_2003: Tournament #999, Sample Event NLH No Limit - Level1(50/100) - 2024/01/15 18:00:00
Table '' 6-max Seat #1 is the button
Seat 1: Alice (300 in chips)
Seat 2: Bob (200 in chips)
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
Alice: raises 190 to 290 and is all-in
Bob: calls 140 and is all-in
Hero: folds
Alice: shows [Qs Qc]
Bob: shows [Kd Kh]
*** FLOP *** [2c 3d 8s]
*** TURN *** [2c 3d 8s] [9h]
*** RIVER *** [2c 3d 8s 9h] [4c]
*** SHOWDOWN ***
Bob collected 400 from pot
Bob collected 100 from pot
*** SUMMARY ***
Total pot 500
Seat 1: Alice showed [Qs Qc] and lost
Seat 2: Bob(small blind) showed [Kd Kh] and won (400)
Seat 3: Hero(big blind) folded before Flop
"""
        out, _ = convert_text(src, Stats())
        self.assertIn("Bob collected 500 from pot", out)
        self.assertNotIn("from main pot", out)
        self.assertIn("Seat 2: Bob (small blind) showed [Kd Kh] and won (500)", out)

    def test_split_pots_use_main_and_side_labels(self):
        src = """\
Poker Hand #tour_2004: Tournament #999, Sample Event NLH No Limit - Level1(50/100) - 2024/01/15 18:00:00
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
Alice: raises 200 to 300
Bob: calls 250
Hero: calls 200
*** FLOP *** [2c 3d 8s]
*** TURN *** [2c 3d 8s] [9h]
*** RIVER *** [2c 3d 8s 9h] [4c]
Alice: shows [As Ac]
Bob: shows [Ad Ah]
*** SHOWDOWN ***
Alice collected 460 from pot
Bob collected 460 from pot
*** SUMMARY ***
Total pot 920
Seat 1: Alice showed [As Ac] and won (460)
Seat 2: Bob(small blind) showed [Ad Ah] and won (460)
Seat 3: Hero(big blind) folded before Flop
"""
        out, _ = convert_text(src, Stats())
        self.assertIn("Alice collected 460 from main pot", out)
        self.assertIn("Bob collected 460 from side pot-1", out)


if __name__ == "__main__":
    unittest.main()
