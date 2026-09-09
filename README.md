# ClubGG MTT → GGPoker (PT4) converter

Rewrite ClubGG / PokerCraft **tournament** hand histories into official GGPoker text so PokerTracker 4 can import them.

This project is **mostly for Hebrew ClubGG exports** (reversed Hebrew tournament names, `NLH` / `PLO` labels, empty table names). The same converter also handles **global / English** ClubGG and official GGPoker MTT files: Hebrew is stripped when present, game types are normalized, and hands that are already in GGPoker form (`#TM` + `Hold'em No Limit` / `Omaha Pot Limit`) pass through unchanged.

Cash games and tournament-summary files are out of scope.

## Usage

Python 3, no extra packages.

1. Put ClubGG `.txt` files in `input/`
2. Run:

```text
python convert.py
```

3. Import the files in `output/` into PT4 via **Play Poker → Get Hands From Disk**

You can still pass other paths:

```text
python convert.py INPUT [-o OUTPUT]
```

- `INPUT` — one `.txt` file or a folder (default: `input/`)
- `OUTPUT` — file or folder (default: `output/`)

Hand histories under `input/`, `output/`, and `hands/` are gitignored recursively. Only the empty `input/` and `output/` folders are tracked. Do not force-add those files.

## What it fixes

- `#tour_…` → `#TM…`
- Hebrew (or other non-ASCII) tournament names → `ClubGG {id} Hold'em No Limit` / `Omaha Pot Limit`
- Missing ante in `Level(sb/bb)` from `posts the ante`
- Empty `Table ''`, `Seat #0` button, glued summary text (`Hero(small blind)`, `abcwon`)
- Missing `posts big blind` when the BB is already all-in on the ante
- Session filenames like `GG20240115-1800 - .txt` → `GG20240115-1800 - Tournament 1234567.txt`

## Limits

- **6-card Omaha** is rewritten but PT4 does not import that game type.
- MTT hand histories only.

## Disclaimer

This project is **not affiliated with** ClubGG, GGPoker, PokerCraft, or PokerTracker. It is provided for **educational and personal offline study** of hand histories you already exported.

Using converted files with a tracker, HUD, or any third-party tool may violate ClubGG, GGPoker, and/or PokerTracker terms. You are responsible for reading those terms and deciding whether your use is allowed. This converter does not grant permission to bypass site rules, enable live HUD play, or redistribute other players' hand data.

The software is provided as-is, without warranty. See [LICENSE](LICENSE).

## License

MIT. See [LICENSE](LICENSE).
