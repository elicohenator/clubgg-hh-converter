#!/usr/bin/env python3
"""Convert ClubGG PokerCraft MTT hand histories to official GGPoker format for PT4."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

__version__ = "1.0.0"

POT_EXTRAS = " | Rake 0 | Jackpot 0 | Bingo 0 | Fortune 0 | Tax 0"

HAND_SPLIT_RE = re.compile(r"(?=^Poker Hand #)", re.MULTILINE)
HEADER_RE = re.compile(
    r"^Poker Hand #(?P<prefix>tour_|TM|HD|RC)?(?P<hand_id>\d+):\s+"
    r"Tournament #(?P<tour_id>\d+),\s+"
    r"(?P<body>.+)$"
)
LEVEL_DT_RE = re.compile(
    r"^(?P<name>.+?)\s+-\s+"
    r"(?P<level>Level(?P<level_n>\d+)\((?P<blinds>[^)]+)\))\s+-\s+"
    r"(?P<dt>\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2})\s*$"
)
LEVEL_BLINDS_RE = re.compile(
    r"^(?P<sb>[\d,]+)/(?P<bb>[\d,]+)(?:\((?P<ante>[\d,]+)\))?$"
)
TABLE_RE = re.compile(
    r"^Table '(?P<name>[^']*)' (?P<max>\d+-max) Seat #(?P<button>\d+) is the button\s*$"
)
SEAT_RE = re.compile(
    r"^Seat (?P<seat>\d+): (?P<name>\S+) \((?P<stack>[\d,]+) in chips\)"
)
DEALT_CARDS_RE = re.compile(r"^Dealt to \S+ \[(?P<cards>[^\]]+)\]\s*$")
ANTE_RE = re.compile(r"^(\S+): posts the ante ([\d,]+)")
SB_RE = re.compile(r"^(\S+): posts small blind ")
BB_RE = re.compile(r"^(\S+): posts big blind ")
SUMMARY_SEAT_RE = re.compile(r"^Seat (?P<seat>\d+): (?P<rest>.+)$")
ROLE_PREFIX_RE = re.compile(
    r"^\s*\((?P<role>button|small blind|big blind)\)\s*"
)
GG_DATE_PREFIX_RE = re.compile(r"^(GG\d{8}-\d{4})\s*-\s*(.*)$")

KNOWN_GAMES = (
    (re.compile(r"6\s*Card\s+Omaha\s+Pot\s+Limit", re.I), "6card"),
    (re.compile(r"5\s*Card\s+Omaha\s+Pot\s+Limit", re.I), "5card"),
    (re.compile(r"Omaha\s+Pot\s+Limit", re.I), "omaha"),
    (re.compile(r"PLO-?6\s+Pot\s+Limit", re.I), "6card"),
    (re.compile(r"PLO-?5\s+Pot\s+Limit", re.I), "5card"),
    (re.compile(r"PLO\s+Pot\s+Limit", re.I), "omaha"),
    (re.compile(r"Hold'?em\s+No\s+Limit", re.I), "holdem"),
    (re.compile(r"NLH\s+No\s+Limit", re.I), "holdem"),
)


class Stats:
    def __init__(self) -> None:
        self.files = 0
        self.rewritten = 0
        self.skipped_gg = 0
        self.errors = 0


def split_hands(text: str) -> list[str]:
    parts = [p for p in HAND_SPLIT_RE.split(text) if p.strip()]
    return parts


def is_already_gg(hand: str) -> bool:
    first = next((line for line in hand.splitlines() if line.strip()), "")
    if not first.startswith("Poker Hand #TM"):
        return False
    return "Hold'em No Limit" in first or "Omaha Pot Limit" in first


def hole_card_count(lines: list[str]) -> int:
    for line in lines:
        m = DEALT_CARDS_RE.match(line)
        if m:
            return len(m.group("cards").split())
    return 0


def detect_game_key(header_name: str, card_count: int) -> str:
    if card_count == 2:
        return "holdem"
    if card_count == 5:
        return "5card"
    if card_count == 6:
        return "6card"
    if card_count == 4:
        return "omaha"
    for pattern, key in KNOWN_GAMES:
        if pattern.search(header_name):
            return key
    return "holdem"


def game_label(key: str) -> str:
    return {
        "holdem": "Hold'em No Limit",
        "omaha": "Omaha Pot Limit",
        "5card": "5 Card Omaha Pot Limit",
        "6card": "6 Card Omaha Pot Limit",
    }[key]


def parse_amount(raw: str) -> str:
    return raw.replace(",", "")


def format_amount(raw: str) -> str:
    digits = parse_amount(raw)
    if not digits.isdigit():
        return raw
    return f"{int(digits):,}"


def find_player_map(
    lines: list[str],
) -> tuple[dict[str, int], dict[int, str], dict[str, int]]:
    name_to_seat: dict[str, int] = {}
    seat_to_name: dict[int, str] = {}
    stacks: dict[str, int] = {}
    for line in lines:
        if line.startswith("*** HOLE CARDS ***"):
            break
        m = SEAT_RE.match(line)
        if m:
            seat = int(m.group("seat"))
            name = m.group("name")
            name_to_seat[name] = seat
            seat_to_name[seat] = name
            stacks[name] = int(parse_amount(m.group("stack")))
    return name_to_seat, seat_to_name, stacks


def first_match_name(pattern: re.Pattern[str], lines: list[str]) -> str | None:
    for line in lines:
        m = pattern.match(line)
        if m:
            return m.group(1)
    return None


def player_antes(lines: list[str]) -> dict[str, int]:
    antes: dict[str, int] = {}
    for line in lines:
        m = ANTE_RE.match(line)
        if m:
            antes[m.group(1)] = int(parse_amount(m.group(2)))
    return antes


def summary_bb_name(lines: list[str], seat_to_name: dict[int, str]) -> str | None:
    in_summary = False
    for line in lines:
        if line.strip() == "*** SUMMARY ***":
            in_summary = True
            continue
        if not in_summary:
            continue
        m = SUMMARY_SEAT_RE.match(line)
        if not m:
            continue
        rest = m.group("rest")
        if "(big blind)" in rest:
            return seat_to_name.get(int(m.group("seat")))
    return None


def next_player(seat_to_name: dict[int, str], after_seat: int | None) -> str | None:
    seats = sorted(seat_to_name)
    if not seats:
        return None
    if after_seat is None or after_seat not in seats:
        return seat_to_name[seats[0]]
    nxt = seats[(seats.index(after_seat) + 1) % len(seats)]
    return seat_to_name[nxt]


def insert_missing_big_blind(
    lines: list[str],
    bb_name: str,
    stacks: dict[str, int],
    antes: dict[str, int],
    full_bb: int | None,
) -> None:
    leftover = max(0, stacks.get(bb_name, 0) - antes.get(bb_name, 0))
    amount = f"{leftover:,}"
    suffix = ""
    if full_bb is not None and leftover < full_bb:
        suffix = " and is all-in"
    post = f"{bb_name}: posts big blind {amount}{suffix}"
    hole = next(
        (i for i, line in enumerate(lines) if line.startswith("*** HOLE CARDS ***")),
        None,
    )
    if hole is None:
        return
    lines.insert(hole, post)


def infer_button(occupied: list[int], sb_seat: int | None) -> int:
    seats = sorted(occupied)
    if not seats:
        return 0
    if sb_seat is None or sb_seat not in seats:
        return seats[-1]
    return seats[seats.index(sb_seat) - 1]


def rewrite_level(level_n: str, blinds: str, ante: str | None) -> str:
    m = LEVEL_BLINDS_RE.match(blinds.strip())
    if not m:
        if ante and "(" not in blinds:
            return f"Level{level_n}({blinds}({ante}))"
        return f"Level{level_n}({blinds})"
    sb = format_amount(m.group("sb"))
    bb = format_amount(m.group("bb"))
    existing_ante = m.group("ante")
    if existing_ante:
        return f"Level{level_n}({sb}/{bb}({format_amount(existing_ante)}))"
    if ante:
        return f"Level{level_n}({sb}/{bb}({format_amount(ante)}))"
    return f"Level{level_n}({sb}/{bb})"


def role_for(seat: int, button: int, sb: int | None, bb: int | None) -> str | None:
    if seat == button:
        return "button"
    if sb is not None and seat == sb:
        return "small blind"
    if bb is not None and seat == bb:
        return "big blind"
    return None


def rewrite_summary_seat(
    line: str,
    seat_to_name: dict[int, str],
    button: int,
    sb: int | None,
    bb: int | None,
) -> str:
    m = SUMMARY_SEAT_RE.match(line)
    if not m:
        return line
    seat = int(m.group("seat"))
    rest = m.group("rest")
    name = seat_to_name.get(seat)
    if name and rest.startswith(name):
        rest = rest[len(name) :]
    else:
        name_m = re.match(
            r"^(?P<name>.+?)(?=(?:\(|won|showed|folded|collected|\s))",
            rest,
        )
        if name_m:
            name = name_m.group("name")
            rest = rest[len(name) :]
        elif name is None:
            return line

    rest = re.sub(r"^(won|showed|folded|collected)\b", r" \1", rest)
    role_m = ROLE_PREFIX_RE.match(rest)
    if role_m:
        rest = rest[role_m.end() :]
    rest = rest.lstrip()
    rest = re.sub(r"^(won|showed|folded|collected)\b", r"\1", rest)

    role = role_for(seat, button, sb, bb)
    if role:
        return f"Seat {seat}: {name} ({role}) {rest}"
    return f"Seat {seat}: {name} {rest}"


def rewrite_hand(hand: str, stats: Stats) -> str:
    text = hand.replace("\r\n", "\n").replace("\r", "\n").strip("\n")
    if not text.strip():
        return hand
    if is_already_gg(text):
        stats.skipped_gg += 1
        return text

    lines = text.split("\n")
    header_m = HEADER_RE.match(lines[0])
    if not header_m:
        stats.errors += 1
        return text

    body_m = LEVEL_DT_RE.match(header_m.group("body"))
    if not body_m:
        stats.errors += 1
        return text

    tour_id = header_m.group("tour_id")
    hand_id = header_m.group("hand_id")
    card_count = hole_card_count(lines)
    game = game_label(detect_game_key(body_m.group("name"), card_count))

    ante = None
    for line in lines:
        ante_m = ANTE_RE.match(line)
        if ante_m:
            ante = ante_m.group(2)
            break

    level = rewrite_level(body_m.group("level_n"), body_m.group("blinds"), ante)
    lines[0] = (
        f"Poker Hand #TM{hand_id}: Tournament #{tour_id}, "
        f"ClubGG {tour_id} {game} - {level} - {body_m.group('dt')}"
    )

    name_to_seat, seat_to_name, stacks = find_player_map(lines)
    sb_name = first_match_name(SB_RE, lines)
    bb_name = first_match_name(BB_RE, lines)
    if not bb_name:
        bb_name = summary_bb_name(lines, seat_to_name)
        if not bb_name and sb_name:
            bb_name = next_player(seat_to_name, name_to_seat.get(sb_name))
        if bb_name:
            blinds_m = LEVEL_BLINDS_RE.match(body_m.group("blinds").strip())
            full_bb = int(parse_amount(blinds_m.group("bb"))) if blinds_m else None
            insert_missing_big_blind(
                lines, bb_name, stacks, player_antes(lines), full_bb
            )
    sb_seat = name_to_seat.get(sb_name) if sb_name else None
    bb_seat = name_to_seat.get(bb_name) if bb_name else None

    table_idx = next((i for i, line in enumerate(lines) if line.startswith("Table ")), None)
    button = 0
    if table_idx is not None:
        table_m = TABLE_RE.match(lines[table_idx])
        if table_m:
            table_name = table_m.group("name") or tour_id
            button = int(table_m.group("button"))
            if button == 0:
                button = infer_button(list(seat_to_name), sb_seat)
            lines[table_idx] = (
                f"Table '{table_name}' {table_m.group('max')} "
                f"Seat #{button} is the button"
            )
        else:
            stats.errors += 1

    in_summary = False
    for i, line in enumerate(lines):
        if line.strip() == "*** SUMMARY ***":
            in_summary = True
            continue
        if not in_summary:
            continue
        if line.startswith("Total pot ") and " | Rake " not in line:
            lines[i] = line.rstrip() + POT_EXTRAS
        elif line.startswith("Seat "):
            lines[i] = rewrite_summary_seat(line, seat_to_name, button, sb_seat, bb_seat)

    stats.rewritten += 1
    return "\n".join(lines)


def convert_text(text: str, stats: Stats) -> tuple[str, str | None]:
    hands = split_hands(text)
    if not hands:
        stats.errors += 1
        return text, None
    converted = [rewrite_hand(hand, stats) for hand in hands]
    tour_id = None
    first = converted[0].splitlines()[0] if converted and converted[0].strip() else ""
    header_m = HEADER_RE.match(first)
    if header_m:
        tour_id = header_m.group("tour_id")
    return "\n\n\n".join(converted).rstrip() + "\n", tour_id


def safe_filename(name: str) -> str:
    cleaned = name.replace("\\", "/").split("/")[-1].replace("\x00", "")
    if not cleaned or cleaned in {".", ".."}:
        return "hand.txt"
    return cleaned


def output_filename(src_name: str, tour_id: str | None) -> str:
    stem = Path(src_name).stem
    match = GG_DATE_PREFIX_RE.match(stem)
    if not match:
        base = src_name if src_name.lower().endswith(".txt") else f"{src_name}.txt"
        return safe_filename(base)
    prefix, rest = match.group(1), match.group(2).strip()
    if not rest or re.fullmatch(r"\(\d+\)", rest):
        rest = f"Tournament {tour_id}" if tour_id else "ClubGG"
    rest = safe_filename(rest).removesuffix(".txt")
    return safe_filename(f"{prefix} - {rest}.txt")


def read_text(path: Path) -> str:
    data = path.read_bytes()
    for enc in ("utf-8-sig", "utf-8", "cp1255", "cp1252"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def collect_inputs(src: Path) -> list[Path]:
    if src.is_symlink():
        return []
    if src.is_file():
        return [src]
    found: list[Path] = []
    for path in src.rglob("*.txt"):
        if path.is_symlink() or not path.is_file():
            continue
        found.append(path)
    return sorted(found)


def dest_for(src: Path, root: Path, out: Path, tour_id: str | None) -> Path:
    name = output_filename(src.name, tour_id)
    if out.suffix.lower() == ".txt" and root.is_file():
        dest = out
    elif root.is_file():
        dest = out / name
    else:
        dest = out / src.relative_to(root).with_name(name)
    out_root = out.parent.resolve() if out.suffix.lower() == ".txt" else out.resolve()
    resolved = dest.resolve()
    try:
        resolved.relative_to(out_root)
    except ValueError as exc:
        raise OSError(f"Refusing to write outside output folder: {dest}") from exc
    return dest


def convert_path(src: Path, out: Path, stats: Stats) -> None:
    inputs = collect_inputs(src)
    if not inputs:
        print(f"No .txt files found in {src}", file=sys.stderr)
        return
    for path in inputs:
        try:
            text = read_text(path)
            converted, tour_id = convert_text(text, stats)
            dest = dest_for(path, src, out, tour_id)
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(converted, encoding="utf-8", newline="\n")
            stats.files += 1
            print(f"Wrote {dest}")
        except OSError as exc:
            stats.errors += 1
            print(f"Error: {path}: {exc}", file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Convert ClubGG MTT hand histories to GGPoker/PT4 format."
    )
    parser.add_argument(
        "-V",
        "--version",
        action="version",
        version=f"clubgg-hh-converter {__version__}",
    )
    parser.add_argument(
        "input",
        nargs="?",
        type=Path,
        default=Path("input"),
        help="A .txt file or a folder of .txt files (default: ./input)",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path("output"),
        help="Output file or folder (default: ./output)",
    )
    args = parser.parse_args(argv)
    src = args.input
    if not src.exists():
        if src == Path("input"):
            src.mkdir(parents=True, exist_ok=True)
            print(
                f"Created {src.resolve()}. Drop ClubGG .txt files there and run again.",
                file=sys.stderr,
            )
            return 2
        print(f"Input not found: {src}", file=sys.stderr)
        return 2
    stats = Stats()
    convert_path(src, args.output, stats)
    print(
        f"Files: {stats.files}  Hands rewritten: {stats.rewritten}  "
        f"Already GG: {stats.skipped_gg}  Errors: {stats.errors}"
    )
    return 1 if stats.errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
