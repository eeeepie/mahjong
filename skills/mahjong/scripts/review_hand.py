from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter

from mahjong_cli import (
    ALL_TILES,
    best_discard,
    can_win,
    compact_tiles,
    evaluate_hand,
    normalize_lang,
    pick,
    tile_input_aliases,
    ting_discard_options,
    winning_tiles_for_ready_hand,
)


def parse_tile_token(raw: str) -> str:
    lowered = raw.strip().lower()
    for tile in ALL_TILES:
        aliases = {alias.lower() for alias in tile_input_aliases(tile)}
        if lowered in aliases:
            return tile
    raise ValueError(f"Unknown tile token: {raw}")


def parse_tiles(raw: str) -> list[str]:
    if not raw.strip():
        return []
    tokens = [token for token in re.split(r"[\s,，/]+", raw.strip()) if token]
    return [parse_tile_token(token) for token in tokens]


def remaining_wait_count(wait_tile: str, hand_after_discard: list[str], visible_counts: Counter[str]) -> int:
    return max(0, 4 - visible_counts[wait_tile] - hand_after_discard.count(wait_tile))


def build_ting_rows(hand: list[str], visible: list[str], meld_count: int) -> list[dict[str, object]]:
    visible_counts = Counter(visible)
    rows: list[dict[str, object]] = []
    for discard, waits in ting_discard_options(hand, meld_count).items():
        trial = hand.copy()
        trial.remove(discard)
        remaining = {tile: remaining_wait_count(tile, trial, visible_counts) for tile in waits}
        rows.append(
            {
                "discard": discard,
                "waits": waits,
                "remaining": remaining,
                "remaining_total": sum(remaining.values()),
                "shape_score": evaluate_hand(trial),
            }
        )
    rows.sort(key=lambda row: (row["remaining_total"], len(row["waits"]), row["shape_score"]), reverse=True)
    return rows


def render_rows(rows: list[dict[str, object]], lang: str, limit: int) -> list[str]:
    lines: list[str] = []
    for index, row in enumerate(rows[:limit], start=1):
        discard = row["discard"]
        waits = row["waits"]
        remaining = row["remaining"]
        total = row["remaining_total"]
        wait_summary = compact_tiles(waits, lang, False)
        remaining_summary = ", ".join(f"{tile}:{count}" for tile, count in remaining.items())
        lines.append(
            pick(
                lang,
                f"{index}. 打 {compact_tiles([discard], lang, False)} -> 听 {wait_summary} | 余张约 {total} | {remaining_summary}",
                f"{index}. Discard {compact_tiles([discard], lang, False)} -> wait on {wait_summary} | about {total} live | {remaining_summary}",
            )
        )
    return lines


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Review a Mahjong hand and suggest discard/ting options.")
    parser.add_argument("--hand", required=True, help='concealed hand, e.g. "1m 2m 3m 东风 白板"')
    parser.add_argument("--visible", default="", help='known discards / exposed tiles, e.g. "1m 1m 9p 东风"')
    parser.add_argument("--meld-count", type=int, default=0, help="number of already-fixed melds")
    parser.add_argument("--lang", default="zh", choices=["zh", "ch", "en"], help="output language")
    parser.add_argument("--limit", type=int, default=5, help="max number of ting options to print")
    parser.add_argument("--json", action="store_true", help="emit JSON instead of text")
    args = parser.parse_args(argv)

    lang = normalize_lang(args.lang)

    try:
        hand = parse_tiles(args.hand)
        visible = parse_tiles(args.visible)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    result: dict[str, object] = {
        "lang": lang,
        "hand": hand,
        "visible": visible,
        "meld_count": args.meld_count,
        "can_win_now": can_win(hand, args.meld_count),
    }

    if len(hand) % 3 == 2:
        result["best_discard"] = best_discard(hand, args.meld_count)
        result["ting_options"] = build_ting_rows(hand, visible, args.meld_count)
    elif len(hand) % 3 == 1:
        waits = winning_tiles_for_ready_hand(hand, args.meld_count)
        visible_counts = Counter(visible)
        result["direct_waits"] = {
            tile: remaining_wait_count(tile, hand, visible_counts) for tile in waits
        }
    else:
        result["warning"] = "irregular_hand_size"

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    print(pick(lang, f"手牌: {compact_tiles(hand, lang, False)}", f"Hand: {compact_tiles(hand, lang, False)}"))
    if visible:
        print(pick(lang, f"已见牌: {compact_tiles(visible, lang, False)}", f"Visible: {compact_tiles(visible, lang, False)}"))

    if result["can_win_now"]:
        print(pick(lang, "状态: 已成胡。", "Status: already complete."))
    elif "warning" in result:
        print(pick(lang, "状态: 手牌张数不规则，建议确认输入。", "Status: irregular tile count; check the input."))
    elif "direct_waits" in result:
        direct_waits = result["direct_waits"]
        wait_tiles = list(direct_waits.keys())
        summary = ", ".join(f"{tile}:{count}" for tile, count in direct_waits.items())
        print(pick(lang, f"状态: 当前已在听牌。听口 {compact_tiles(wait_tiles, lang, False)}", f"Status: already in ready state. Waits: {compact_tiles(wait_tiles, lang, False)}"))
        print(pick(lang, f"余张估计: {summary}", f"Approx live tiles: {summary}"))
    else:
        best = result["best_discard"]
        print(pick(lang, f"建议: 优先打 {compact_tiles([best], lang, False)}", f"Suggestion: discard {compact_tiles([best], lang, False)} first"))
        rows = result["ting_options"]
        if rows:
            print(pick(lang, "可形成的听牌出路:", "Ready-hand discard options:"))
            for line in render_rows(rows, lang, args.limit):
                print(line)
        else:
            print(pick(lang, "当前还没有一打即听的出路。", "No immediate ready-hand discard is available."))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
