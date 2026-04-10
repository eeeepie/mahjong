from __future__ import annotations

import argparse
import random
import sys
import textwrap
import time
from collections import Counter, deque
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Deque


RESET = "\033[0m"
BOLD = "\033[1m"
CLEAR = "\033[2J\033[H"

COLOR_MAP = {
    "m": "\033[38;5;160m",
    "p": "\033[38;5;39m",
    "s": "\033[38;5;34m",
    "wind": "\033[38;5;250m",
    "dragon": "\033[38;5;208m",
    "joker": "\033[38;5;226m",
    "accent": "\033[38;5;45m",
    "muted": "\033[38;5;246m",
    "good": "\033[38;5;82m",
    "bad": "\033[38;5;203m",
}

START_POINTS = 100
SCORE_CAP = 100
DEFAULT_DEMO_ROUNDS = 4
SEAT_WIND_TILES = ["E", "S", "W", "N"]

ALL_TILES = [f"{rank}{suit}" for suit in "mps" for rank in range(1, 10)] + [
    "E",
    "S",
    "W",
    "N",
    "C",
    "F",
    "J",
]
NON_JOKER_TILES = [tile for tile in ALL_TILES if tile != "J"]
TILE_ORDER = {tile: index for index, tile in enumerate(ALL_TILES)}
BOT_NAMES = [
    "黑焰龙王",
    "终焉裁决",
    "月蚀零式",
    "绯红夜鸦",
    "天锁残响",
    "白夜断罪",
    "深渊王座",
    "逆命十三",
    "虚空咏叹",
    "星灭使徒",
]

ZH_NUMERAL = {1: "一", 2: "二", 3: "三", 4: "四", 5: "五", 6: "六", 7: "七", 8: "八", 9: "九"}
ZH_SUIT = {"m": "万", "p": "筒", "s": "条"}
EN_SUIT_COMPACT = {"m": "Wan", "p": "Dot", "s": "Bam"}
EN_SUIT_FACE = {"m": "WAN ", "p": "DOT ", "s": "BAM "}
HONOR_ZH = {
    "E": ("东风", "东", "风"),
    "S": ("南风", "南", "风"),
    "W": ("西风", "西", "风"),
    "N": ("北风", "北", "风"),
    "C": ("红中", "红", "中"),
    "F": ("发财", "发", "财"),
    "J": ("白板", "白", "板"),
}
HONOR_EN = {
    "E": ("East", "EAST", "WIND"),
    "S": ("South", "SOUT", "WIND"),
    "W": ("West", "WEST", "WIND"),
    "N": ("North", "NORT", "WIND"),
    "C": ("Red", "RED ", "DRGN"),
    "F": ("Green", "GRN ", "DRGN"),
    "J": ("White", "WHT ", "WILD"),
}


def normalize_lang(value: str | None) -> str:
    if not value:
        return "zh"
    lowered = value.lower()
    if lowered in {"zh", "ch"}:
        return "zh"
    return "en"


def pick(lang: str, zh: str, en: str) -> str:
    return zh if lang == "zh" else en


def ansi(text: str, color: str | None, enabled: bool) -> str:
    if not enabled or not color:
        return text
    return f"{color}{text}{RESET}"


def tile_color(tile: str) -> str:
    if tile == "J":
        return COLOR_MAP["joker"]
    if len(tile) == 2:
        return COLOR_MAP[tile[1]]
    if tile in {"E", "S", "W", "N"}:
        return COLOR_MAP["wind"]
    return COLOR_MAP["dragon"]


def sort_tiles(tiles: list[str]) -> list[str]:
    return sorted(tiles, key=lambda tile: TILE_ORDER[tile])


def is_suited(tile: str) -> bool:
    return len(tile) == 2 and tile[1] in {"m", "p", "s"}


def is_terminal_or_honor(tile: str) -> bool:
    if tile in {"E", "S", "W", "N", "C", "F", "J"}:
        return True
    return is_suited(tile) and tile[0] in {"1", "9"}


def next_seat(seat: int) -> int:
    return (seat + 1) % 4


def wrap_tokens(tokens: list[str], width: int = 8) -> list[str]:
    if not tokens:
        return ["-"]
    rows: list[str] = []
    for start in range(0, len(tokens), width):
        rows.append(" ".join(tokens[start : start + width]))
    return rows


def compact_label(tile: str, lang: str) -> str:
    if tile in HONOR_ZH:
        return HONOR_ZH[tile][0] if lang == "zh" else HONOR_EN[tile][0]
    rank = int(tile[0])
    suit = tile[1]
    if lang == "zh":
        return f"{ZH_NUMERAL[rank]}{ZH_SUIT[suit]}"
    return f"{rank}{EN_SUIT_COMPACT[suit]}"


def tile_face_lines(tile: str, lang: str, hidden: bool = False) -> tuple[str, str]:
    if hidden:
        return " ?? ", " ?? "
    if tile in HONOR_ZH:
        if lang == "zh":
            _, first, second = HONOR_ZH[tile]
            return f" {first} ", f" {second} "
        _, first, second = HONOR_EN[tile]
        return first, second
    rank = int(tile[0])
    suit = tile[1]
    if lang == "zh":
        return f" {ZH_NUMERAL[rank]} ", f" {ZH_SUIT[suit]} "
    return f"{rank:^4}", EN_SUIT_FACE[suit]


def mini_tile(tile: str, lang: str, use_color: bool, hidden: bool = False) -> str:
    label = "??" if hidden else compact_label(tile, lang)
    color = COLOR_MAP["muted"] if hidden else tile_color(tile)
    return f"[{ansi(label, color, use_color)}]"


def compact_tiles(tiles: list[str], lang: str, use_color: bool, hidden: bool = False) -> str:
    if not tiles:
        return "-"
    return " ".join(mini_tile(tile, lang, use_color, hidden) for tile in tiles)


def render_hand_tiles(
    tiles: list[str],
    lang: str,
    use_color: bool,
    hidden: bool = False,
    show_indices: bool = False,
) -> str:
    if not tiles:
        return pick(lang, "(空手牌)", "(empty hand)")
    top = []
    upper = []
    lower = []
    bottom = []
    indices = []
    for index, tile in enumerate(tiles, start=1):
        line_one, line_two = tile_face_lines(tile, lang, hidden)
        color = COLOR_MAP["muted"] if hidden else tile_color(tile)
        top.append("┌────┐")
        upper.append(f"│{ansi(line_one, color, use_color)}│")
        lower.append(f"│{ansi(line_two, color, use_color)}│")
        bottom.append("└────┘")
        if show_indices:
            indices.append(f"{index:^6}")
    rows = [" ".join(top), " ".join(upper), " ".join(lower), " ".join(bottom)]
    if show_indices:
        rows.append(" ".join(indices))
    return "\n".join(rows)


def remove_tiles_from_hand(hand: list[str], tiles_to_remove: list[str]) -> list[str]:
    updated = hand.copy()
    for tile in tiles_to_remove:
        updated.remove(tile)
    return updated


def pick_matching_tiles(hand: list[str], target: str, needed: int) -> list[str] | None:
    if target == "J":
        return None
    counts = Counter(hand)
    if counts[target] < needed:
        return None
    return [target] * needed


def tile_input_aliases(tile: str) -> set[str]:
    aliases = {
        tile.lower(),
        compact_label(tile, "zh"),
        compact_label(tile, "zh").lower(),
        compact_label(tile, "en").lower(),
    }
    honor_words = {
        "E": {"east", "dong", "东", "东风"},
        "S": {"south", "nan", "南", "南风"},
        "W": {"west", "xi", "西", "西风"},
        "N": {"north", "bei", "北", "北风"},
        "C": {"red", "zhong", "红", "红中"},
        "F": {"green", "fa", "发", "发财"},
        "J": {"white", "bai", "白", "白板", "joker", "wild"},
    }
    aliases.update(honor_words.get(tile, set()))
    return aliases


def match_tile_input(hand: list[str], raw: str) -> str | None:
    lowered = raw.strip().lower()
    for tile in sort_tiles(hand):
        if lowered in tile_input_aliases(tile):
            return tile
    return None


@lru_cache(maxsize=None)
def can_form_melds_target(counts_tuple: tuple[int, ...], jokers: int, melds_needed: int) -> bool:
    if melds_needed == 0:
        return sum(counts_tuple) == 0 and jokers == 0
    if sum(counts_tuple) + jokers != melds_needed * 3:
        return False

    first = next((index for index, count in enumerate(counts_tuple) if count), None)
    if first is None:
        return jokers == melds_needed * 3

    counts = list(counts_tuple)
    natural_triplet = min(3, counts[first])
    missing_for_triplet = 3 - natural_triplet
    if missing_for_triplet <= jokers:
        counts[first] -= natural_triplet
        if can_form_melds_target(tuple(counts), jokers - missing_for_triplet, melds_needed - 1):
            return True

    tile = NON_JOKER_TILES[first]
    if is_suited(tile):
        rank = int(tile[0])
        suit = tile[1]
        if rank <= 7:
            indices = [first, first + 1, first + 2]
            sequence_tiles = [NON_JOKER_TILES[index] for index in indices]
            if all(is_suited(candidate) and candidate[1] == suit for candidate in sequence_tiles):
                counts = list(counts_tuple)
                missing = 0
                for index in indices:
                    if counts[index] > 0:
                        counts[index] -= 1
                    else:
                        missing += 1
                if missing <= jokers and can_form_melds_target(tuple(counts), jokers - missing, melds_needed - 1):
                    return True

    return False


@lru_cache(maxsize=None)
def can_form_all_triplets_target(counts_tuple: tuple[int, ...], jokers: int, melds_needed: int) -> bool:
    if melds_needed == 0:
        return sum(counts_tuple) == 0 and jokers == 0
    if sum(counts_tuple) + jokers != melds_needed * 3:
        return False

    first = next((index for index, count in enumerate(counts_tuple) if count), None)
    if first is None:
        return jokers == melds_needed * 3

    counts = list(counts_tuple)
    natural_triplet = min(3, counts[first])
    missing_for_triplet = 3 - natural_triplet
    if missing_for_triplet > jokers:
        return False
    counts[first] -= natural_triplet
    return can_form_all_triplets_target(tuple(counts), jokers - missing_for_triplet, melds_needed - 1)


@lru_cache(maxsize=None)
def find_meld_decomposition(
    counts_tuple: tuple[int, ...],
    jokers: int,
    melds_needed: int,
) -> tuple[tuple[str, str, int], ...] | None:
    if melds_needed == 0:
        return () if sum(counts_tuple) == 0 and jokers == 0 else None
    if sum(counts_tuple) + jokers != melds_needed * 3:
        return None

    first = next((index for index, count in enumerate(counts_tuple) if count), None)
    if first is None:
        if jokers == melds_needed * 3:
            return tuple(("triplet", "J", 3) for _ in range(melds_needed))
        return None

    counts = list(counts_tuple)
    natural_triplet = min(3, counts[first])
    missing_for_triplet = 3 - natural_triplet
    if missing_for_triplet <= jokers:
        counts[first] -= natural_triplet
        result = find_meld_decomposition(tuple(counts), jokers - missing_for_triplet, melds_needed - 1)
        if result is not None:
            return (("triplet", NON_JOKER_TILES[first], missing_for_triplet),) + result

    tile = NON_JOKER_TILES[first]
    if is_suited(tile):
        rank = int(tile[0])
        suit = tile[1]
        if rank <= 7:
            indices = [first, first + 1, first + 2]
            sequence_tiles = [NON_JOKER_TILES[index] for index in indices]
            if all(is_suited(candidate) and candidate[1] == suit for candidate in sequence_tiles):
                counts = list(counts_tuple)
                missing = 0
                missing_mask = 0
                for offset, index in enumerate(indices):
                    if counts[index] > 0:
                        counts[index] -= 1
                    else:
                        missing += 1
                        missing_mask |= 1 << offset
                if missing <= jokers:
                    result = find_meld_decomposition(tuple(counts), jokers - missing, melds_needed - 1)
                    if result is not None:
                        return (("sequence", tile, missing_mask),) + result

    return None


@dataclass(frozen=True)
class WinProfile:
    can_win: bool
    concealed_all_triplets: bool = False


@dataclass(frozen=True)
class WinDecomposition:
    pair_tile: str | None
    pair_missing: int
    melds: tuple[tuple[str, str, int], ...]
    concealed_all_triplets: bool


def analyze_win(tiles: list[str], fixed_meld_count: int = 0) -> WinProfile:
    concealed_melds_needed = 4 - fixed_meld_count
    required_tiles = concealed_melds_needed * 3 + 2
    if concealed_melds_needed < 0 or len(tiles) != required_tiles:
        return WinProfile(False, False)

    counts = Counter(tiles)
    jokers = counts.pop("J", 0)
    base = [counts.get(tile, 0) for tile in NON_JOKER_TILES]

    found_win = False
    found_all_triplets = False

    for index, count in enumerate(base):
        if count >= 2:
            trial = base.copy()
            trial[index] -= 2
            melds_ok = can_form_melds_target(tuple(trial), jokers, concealed_melds_needed)
            if melds_ok:
                found_win = True
                if can_form_all_triplets_target(tuple(trial), jokers, concealed_melds_needed):
                    found_all_triplets = True
        if count >= 1 and jokers >= 1:
            trial = base.copy()
            trial[index] -= 1
            melds_ok = can_form_melds_target(tuple(trial), jokers - 1, concealed_melds_needed)
            if melds_ok:
                found_win = True
                if can_form_all_triplets_target(tuple(trial), jokers - 1, concealed_melds_needed):
                    found_all_triplets = True
        if found_win and found_all_triplets:
            return WinProfile(True, True)

    if jokers >= 2 and can_form_melds_target(tuple(base), jokers - 2, concealed_melds_needed):
        found_win = True
        if can_form_all_triplets_target(tuple(base), jokers - 2, concealed_melds_needed):
            found_all_triplets = True

    return WinProfile(found_win, found_all_triplets)


def find_win_decomposition(tiles: list[str], fixed_meld_count: int = 0) -> WinDecomposition | None:
    concealed_melds_needed = 4 - fixed_meld_count
    required_tiles = concealed_melds_needed * 3 + 2
    if concealed_melds_needed < 0 or len(tiles) != required_tiles:
        return None

    counts = Counter(tiles)
    jokers = counts.pop("J", 0)
    base = [counts.get(tile, 0) for tile in NON_JOKER_TILES]

    for index, count in enumerate(base):
        if count >= 2:
            trial = base.copy()
            trial[index] -= 2
            melds = find_meld_decomposition(tuple(trial), jokers, concealed_melds_needed)
            if melds is not None:
                return WinDecomposition(
                    pair_tile=NON_JOKER_TILES[index],
                    pair_missing=0,
                    melds=melds,
                    concealed_all_triplets=all(meld[0] == "triplet" for meld in melds),
                )
        if count >= 1 and jokers >= 1:
            trial = base.copy()
            trial[index] -= 1
            melds = find_meld_decomposition(tuple(trial), jokers - 1, concealed_melds_needed)
            if melds is not None:
                return WinDecomposition(
                    pair_tile=NON_JOKER_TILES[index],
                    pair_missing=1,
                    melds=melds,
                    concealed_all_triplets=all(meld[0] == "triplet" for meld in melds),
                )

    if jokers >= 2:
        melds = find_meld_decomposition(tuple(base), jokers - 2, concealed_melds_needed)
        if melds is not None:
            return WinDecomposition(
                pair_tile="J",
                pair_missing=2,
                melds=melds,
                concealed_all_triplets=all(meld[0] == "triplet" for meld in melds),
            )

    return None


def can_win(tiles: list[str], fixed_meld_count: int = 0) -> bool:
    return analyze_win(tiles, fixed_meld_count).can_win


def winning_tiles_for_ready_hand(tiles: list[str], fixed_meld_count: int = 0) -> list[str]:
    waits: list[str] = []
    for tile in ALL_TILES:
        if can_win(sort_tiles(tiles + [tile]), fixed_meld_count):
            waits.append(tile)
    return sort_tiles(list(dict.fromkeys(waits)))


def ting_discard_options(tiles: list[str], fixed_meld_count: int = 0) -> dict[str, list[str]]:
    options: dict[str, list[str]] = {}
    for discard in sort_tiles(list(dict.fromkeys(tiles))):
        trial = tiles.copy()
        trial.remove(discard)
        waits = winning_tiles_for_ready_hand(trial, fixed_meld_count)
        if waits:
            options[discard] = waits
    return options


def evaluate_hand(tiles: list[str]) -> float:
    counts = Counter(tiles)
    jokers = counts.pop("J", 0)
    score = jokers * 7.0

    for tile, count in counts.items():
        score += count * count
        if count >= 2:
            score += 2.5
        if count >= 3:
            score += 4.0
        if tile in {"E", "S", "W", "N", "C", "F"} and count == 1:
            score -= 0.2

    for suit in "mps":
        values = [counts.get(f"{rank}{suit}", 0) for rank in range(1, 10)]
        for index in range(9):
            if index < 8:
                score += min(values[index], values[index + 1]) * 1.4
            if index < 7:
                score += min(values[index], values[index + 2]) * 0.8
                score += min(values[index], values[index + 1], values[index + 2]) * 2.2

    return score


def best_discard(tiles: list[str], fixed_meld_count: int = 0) -> str:
    unique_tiles = sort_tiles(list(dict.fromkeys(tiles)))
    best_tile = unique_tiles[0]
    best_score = float("-inf")
    for tile in unique_tiles:
        trial = tiles.copy()
        trial.remove(tile)
        score = evaluate_hand(trial)
        if can_win(trial, fixed_meld_count):
            score += 50
        score -= TILE_ORDER[tile] * 0.001
        if score > best_score:
            best_score = score
            best_tile = tile
    return best_tile


def triplet_hu(tile: str, concealed: bool) -> int:
    if concealed:
        return 8 if is_terminal_or_honor(tile) else 4
    return 4 if is_terminal_or_honor(tile) else 2


def kong_hu(tile: str, concealed: bool) -> int:
    if concealed:
        return 32 if is_terminal_or_honor(tile) else 16
    return 16 if is_terminal_or_honor(tile) else 8


def sequence_middle_tile(start_tile: str) -> str:
    rank = int(start_tile[0]) + 1
    return f"{rank}{start_tile[1]}"


def exposed_triplet_base(meld_tiles: list[str]) -> str | None:
    if "J" in meld_tiles:
        return None
    if len(set(meld_tiles)) == 1:
        return meld_tiles[0]
    return None


@dataclass
class Meld:
    kind: str
    tiles: list[str]
    from_seat: int | None = None

    def render(self, lang: str, use_color: bool) -> str:
        kind_label = {
            "chi": pick(lang, "吃", "Chi"),
            "peng": pick(lang, "碰", "Pung"),
            "gang": pick(lang, "杠", "Kong"),
        }.get(self.kind, self.kind)
        return f"{kind_label}:{compact_tiles(self.tiles, lang, use_color)}"


@dataclass
class Player:
    seat: int
    name: str
    is_bot: bool
    hand: list[str] = field(default_factory=list)
    melds: list[Meld] = field(default_factory=list)
    discards: list[str] = field(default_factory=list)
    points: int = START_POINTS


@dataclass
class ClaimOption:
    seat: int
    kind: str
    hand_tiles: list[str]
    meld_tiles: list[str]
    summary: str


@dataclass
class ScoreProfile:
    hu_extra: int
    tai: int
    total: int
    hu_lines: list[str] = field(default_factory=list)
    tai_lines: list[str] = field(default_factory=list)
    limit_lines: list[str] = field(default_factory=list)


@dataclass
class Settlement:
    summary_lines: list[str] = field(default_factory=list)
    deltas: dict[int, int] = field(default_factory=dict)
    total: int = 0
    score_profile: ScoreProfile | None = None


class TaizhouMahjongGame:
    def __init__(
        self,
        rng: random.Random,
        lang: str,
        use_color: bool,
        no_delay: bool,
        auto_user: bool,
        max_turns: int,
        match_rounds: int,
    ):
        self.rng = rng
        self.lang = normalize_lang(lang)
        self.use_color = use_color
        self.no_delay = no_delay
        self.auto_user = auto_user
        self.max_turns = max_turns
        self.match_rounds = match_rounds
        self.user_seat = 0
        self.table_id = self.rng.randint(100000, 999999)
        bot_pool = self.rng.sample(BOT_NAMES, 3)
        self.players = [
            Player(0, pick(self.lang, "你", "You"), False),
            Player(1, bot_pool[0], True),
            Player(2, bot_pool[1], True),
            Player(3, bot_pool[2], True),
        ]
        self.logs: Deque[str] = deque(maxlen=8)
        self.wall: list[str] = []
        self.current_seat = 0
        self.pending_draw = False
        self.pending_gang_draw_seat: int | None = None
        self.last_draw_was_gang = False
        self.last_drawn_tile: str | None = None
        self.last_drawn_by: int | None = None
        self.last_discard: str | None = None
        self.last_discarder: int | None = None
        self.winner_seat: int | None = None
        self.win_reason = ""
        self.turn_counter = 0
        self.settlement = Settlement()
        self.round_index = 0
        self.dealer_seat = 0
        self.user_requested_exit = False
        self.user_trustee = False

    def t(self, zh: str, en: str) -> str:
        return pick(self.lang, zh, en)

    def sleep(self, seconds: float) -> None:
        if not self.no_delay:
            time.sleep(seconds)

    def log(self, message: str) -> None:
        self.logs.appendleft(message)

    def dealer_name(self) -> str:
        return self.players[self.dealer_seat].name

    def seat_wind_tile(self, seat: int) -> str:
        return SEAT_WIND_TILES[seat]

    def seat_wind_label(self, seat: int) -> str:
        return compact_label(self.seat_wind_tile(seat), self.lang)

    def fresh_wall(self) -> list[str]:
        wall: list[str] = []
        for tile in ALL_TILES:
            wall.extend([tile] * 4)
        self.rng.shuffle(wall)
        return wall

    def action_label(self, kind: str) -> str:
        return {
            "chi": self.t("吃", "Chi"),
            "peng": self.t("碰", "Pung"),
            "gang": self.t("杠", "Kong"),
            "hu": self.t("胡", "Hu"),
        }.get(kind, kind)

    def setup_round(self) -> None:
        self.round_index += 1
        self.wall = self.fresh_wall()
        self.logs.clear()
        self.current_seat = self.dealer_seat
        self.pending_draw = False
        self.pending_gang_draw_seat = None
        self.last_draw_was_gang = False
        self.last_drawn_tile = None
        self.last_drawn_by = None
        self.last_discard = None
        self.last_discarder = None
        self.winner_seat = None
        self.win_reason = ""
        self.turn_counter = 0
        self.settlement = Settlement()
        self.user_trustee = False
        for player in self.players:
            player.hand.clear()
            player.melds.clear()
            player.discards.clear()
        for _ in range(13):
            for player in self.players:
                player.hand.append(self.wall.pop())
        dealer_draw = self.wall.pop()
        self.players[self.dealer_seat].hand.append(dealer_draw)
        self.last_drawn_tile = dealer_draw
        self.last_drawn_by = self.dealer_seat
        for player in self.players:
            player.hand = sort_tiles(player.hand)
        self.log(self.t(f"第 {self.round_index} 局开始，{self.dealer_name()} 坐庄。", f"Round {self.round_index} begins. Dealer: {self.dealer_name()}."))
        self.log(self.t("规则: 白板万能 / 无花 / 连打多局 / 台州风味计分。", "Rules: white wildcard / no flowers / multi-round session / Taizhou-style scoring."))

    def seat_state(self, seat: int) -> str:
        player = self.players[seat]
        meld_line = " / ".join(meld.render(self.lang, self.use_color) for meld in player.melds) if player.melds else self.t("无副露", "No melds")
        dealer_marker = self.t("庄", "D") if seat == self.dealer_seat else self.seat_wind_label(seat)
        hand_label = self.t("手牌", "Hand")
        status = f"{dealer_marker} · {player.name} · {player.points} pt · {hand_label} {len(player.hand)}"
        if self.lang == "zh":
            status += " 张"
        status += f" · {meld_line}"
        if seat == self.user_seat and self.user_trustee:
            status += self.t(" · 托管中", " · Auto")
        if seat == self.current_seat:
            marker = ansi(self.t(" < 当前行动", " < Active"), COLOR_MAP["accent"], self.use_color)
            if self.pending_draw:
                marker += ansi(self.t(" / 待摸牌", " / draw"), COLOR_MAP["muted"], self.use_color)
            status += marker
        return status

    def ready_options_for_user(self) -> dict[str, list[str]]:
        user = self.players[self.user_seat]
        return ting_discard_options(user.hand, len(user.melds))

    def remaining_wait_count(self, hand_after_discard: list[str], wait_tile: str) -> int:
        counter = self.visible_counter()
        return max(0, 4 - counter[wait_tile] - hand_after_discard.count(wait_tile))

    def best_ready_choice(self) -> tuple[str, list[str]] | None:
        options = self.ready_options_for_user()
        if not options:
            return None

        best_discard: str | None = None
        best_waits: list[str] = []
        best_score: tuple[int, int, float] | None = None
        user = self.players[self.user_seat]
        for discard, waits in options.items():
            trial = user.hand.copy()
            trial.remove(discard)
            remain_total = sum(self.remaining_wait_count(trial, tile) for tile in waits)
            score = (remain_total, len(waits), evaluate_hand(trial))
            if best_score is None or score > best_score:
                best_score = score
                best_discard = discard
                best_waits = waits

        if best_discard is None:
            return None
        return best_discard, best_waits

    def ready_option_lines(self, options: dict[str, list[str]]) -> list[str]:
        lines: list[str] = []
        for discard, waits in sorted(options.items(), key=lambda item: (TILE_ORDER[item[0]], len(item[1]))):
            trial = self.players[self.user_seat].hand.copy()
            trial.remove(discard)
            wait_labels = compact_tiles(waits, self.lang, self.use_color)
            remain_total = sum(self.remaining_wait_count(trial, tile) for tile in waits)
            lines.append(
                self.t(
                    f"打 {compact_tiles([discard], self.lang, self.use_color)} 听 {wait_labels}，剩余约 {remain_total} 张。",
                    f"Discard {compact_tiles([discard], self.lang, self.use_color)} to wait on {wait_labels}, about {remain_total} left.",
                )
            )
        return lines

    def visible_counter(self) -> Counter[str]:
        counter: Counter[str] = Counter()
        for player in self.players:
            counter.update(player.discards)
            for meld in player.melds:
                counter.update(meld.tiles)
        return counter

    def visible_summary_lines(self) -> list[str]:
        counter = self.visible_counter()
        if not counter:
            return [self.t("暂无已见牌。", "No visible tiles yet.")]
        tokens = [
            f"{mini_tile(tile, self.lang, self.use_color)}{counter[tile]}/4"
            for tile in sort_tiles(list(counter.keys()))
        ]
        return wrap_tokens(tokens, width=6)

    def point_table_lines(self) -> list[str]:
        ordered = sorted(self.players, key=lambda player: player.points, reverse=True)
        return [f"{index}. {player.name}: {player.points} pt" for index, player in enumerate(ordered, start=1)]

    def render_river(self, tiles: list[str]) -> list[str]:
        return wrap_tokens([mini_tile(tile, self.lang, self.use_color) for tile in tiles], width=8)

    def round_label(self) -> str:
        if self.match_rounds:
            return f"{self.round_index}/{self.match_rounds}"
        return str(self.round_index)

    def render_table(self, prompt: str | None = None, extra_lines: list[str] | None = None) -> None:
        sys.stdout.write(CLEAR)
        title = self.t("台州麻将 · CLI 线上大厅", "Taizhou Mahjong · CLI Lobby")
        header = (
            f"{self.t('房间', 'Room')} {self.table_id} | "
            f"{self.t('语言', 'Lang')} {self.lang.upper()} | "
            f"{self.t('局数', 'Round')} {self.round_label()} | "
            f"{self.t('庄家', 'Dealer')} {self.dealer_name()} | "
            f"{self.t('牌墙', 'Wall')} {len(self.wall)} | "
            f"{self.t('回合', 'Turn')} {self.turn_counter}/{self.max_turns}"
        )
        sys.stdout.write(f"{BOLD}╔════════════════════════════════ {title} ════════════════════════════════╗{RESET}\n")
        sys.stdout.write(f"║ {header:<83} ║\n")
        sys.stdout.write("╚═════════════════════════════════════════════════════════════════════════════════════════╝\n\n")

        sys.stdout.write(f"{self.t('北家', 'North')}: {self.seat_state(2)}\n")
        for row in self.render_river(self.players[2].discards):
            sys.stdout.write(f"      {self.t('河牌', 'River')} {row}\n")
        sys.stdout.write("\n")

        sys.stdout.write(f"{self.t('左家', 'Left')}: {self.seat_state(1)}\n")
        for row in self.render_river(self.players[1].discards):
            sys.stdout.write(f"      {self.t('河牌', 'River')} {row}\n")
        sys.stdout.write("\n")

        sys.stdout.write(f"{self.t('右家', 'Right')}: {self.seat_state(3)}\n")
        for row in self.render_river(self.players[3].discards):
            sys.stdout.write(f"      {self.t('河牌', 'River')} {row}\n")
        sys.stdout.write("\n")

        sys.stdout.write(f"{BOLD}{self.t('系统播报', 'System Feed')}{RESET}\n")
        for entry in list(self.logs)[:6]:
            sys.stdout.write(f"- {entry}\n")
        if self.last_discard and self.last_discarder is not None:
            discarder = self.players[self.last_discarder]
            last_label = compact_tiles([self.last_discard], self.lang, self.use_color)
            sys.stdout.write(f"- {self.t('最新打出', 'Latest discard')}: {discarder.name} -> {last_label}\n")
        sys.stdout.write("\n")

        sys.stdout.write(f"{BOLD}{self.t('已见牌情报', 'Visible Tiles')}{RESET}\n")
        for row in self.visible_summary_lines():
            sys.stdout.write(f"- {row}\n")
        sys.stdout.write("\n")

        user = self.players[self.user_seat]
        sys.stdout.write(f"{self.t('你的位置', 'Your seat')}: {self.seat_state(self.user_seat)}\n")
        meld_text = " / ".join(meld.render(self.lang, self.use_color) for meld in user.melds) if user.melds else self.t("暂无", "None")
        sys.stdout.write(f"{self.t('你的副露', 'Your melds')}: {meld_text}\n")
        sys.stdout.write(f"{self.t('你的河牌', 'Your river')}: {compact_tiles(user.discards, self.lang, self.use_color)}\n")
        sys.stdout.write(f"{self.t('你的手牌', 'Your hand')}:\n")
        sys.stdout.write(render_hand_tiles(sort_tiles(user.hand), self.lang, self.use_color, show_indices=True))
        sys.stdout.write("\n")

        if extra_lines:
            for line in extra_lines:
                sys.stdout.write(f"{line}\n")
        if prompt:
            sys.stdout.write(f"\n{ansi(prompt, COLOR_MAP['accent'], self.use_color)}\n")
        sys.stdout.flush()

    def show_rules(self) -> None:
        sys.stdout.write(CLEAR)
        rules = self.t(
            """
            台州麻将原型规则

            1. 四人麻将，无花牌，白板为万能牌，但不参与吃、碰、杠。
            2. 支持吃、碰、杠、自摸胡、点炮胡，并支持同桌连续多局。
            3. 胡牌按标准结构判断，并会把已有副露一起计入。
            4. 每位玩家入桌默认 100 point，局间累计，不会每局重置。
            5. 庄家胡牌连庄；闲家胡牌或流局，则下家接庄。
            6. 听牌后可输入 `auto` / `托管` 开启自动托管，系统会自动胡牌并自动过非胡副露。
            7. 计分原型更接近台州/椒江一带常见的“胡数 + 台数”思路：
               - 10 底胡起算
               - 刻子、杠子、门风对子、自摸、碰碰胡、嵌张、边张等加胡
               - 门风刻、红中/发财刻、混一色、杠开、无白板等加台
               - 清一色、字一色、四风齐聚按封顶大牌处理
               - 按 `(10底胡 + 附加胡) x 2^台数` 结算，封顶 100
               - 点炮时只有放铳者付整份；自摸时其余三家都付整份
            """,
            """
            Taizhou Mahjong Prototype

            1. Four players, no flowers, White Dragon acts as a wildcard, but it is not used for chi, pung, or kong claims.
            2. Supports chi, pung, kong, self-draw wins, discard wins, and multi-round sessions.
            3. Win validation counts both concealed tiles and exposed melds.
            4. Every player starts with 100 points and keeps them across rounds.
            5. Dealer stays on a dealer win; otherwise the deal passes to the next seat.
            6. Once you reach ready range, `auto` enables trustee mode: it auto-wins and auto-passes non-win claims.
            7. Scoring is now closer to common Taizhou/Jiaojiang-style hu/tai logic:
               - 10 base hu
               - extra hu from triplets, kongs, seat-wind pair, self-draw, all triplets, closed waits, edge waits, etc.
               - extra tai from seat-wind pungs, dragon pungs, half flush, kong-draw, no wildcard, etc.
               - full flush, all honors, and four-winds hands are treated as local limit hands
               - settlement uses `(10 base hu + extra hu) x 2^tai`, capped at 100
               - discard wins only charge the discarder; self-draw charges all three losers a full share
            """,
        ).strip()
        sys.stdout.write(f"{rules}\n\n")
        self.safe_input(self.t("按回车返回大厅...", "Press Enter to return to lobby..."))

    def safe_input(self, prompt: str) -> str:
        try:
            return input(prompt).strip()
        except EOFError:
            return ""

    def join_room_sequence(self) -> None:
        sys.stdout.write(CLEAR)
        steps = [
            self.t("系统: 正在呼叫牌友...", "System: calling players..."),
            self.t(f"系统: 匹配完成，房间号 {self.table_id}。", f"System: matched. Room #{self.table_id}."),
            self.t(f"{self.players[1].name}: 已就位。", f"{self.players[1].name}: ready."),
            self.t(f"{self.players[2].name}: 已就位。", f"{self.players[2].name}: ready."),
            self.t(f"{self.players[3].name}: 已就位。", f"{self.players[3].name}: ready."),
            self.t("系统: 台州麻将连打规则已载入。", "System: multi-round Taizhou rules loaded."),
        ]
        for line in steps:
            sys.stdout.write(f"{line}\n")
            sys.stdout.flush()
            self.sleep(0.45)
        self.sleep(0.25)

    def draw_tile(self, seat: int) -> str | None:
        if not self.wall:
            return None
        tile = self.wall.pop()
        player = self.players[seat]
        player.hand.append(tile)
        player.hand = sort_tiles(player.hand)
        self.last_drawn_tile = tile
        self.last_drawn_by = seat
        self.last_draw_was_gang = self.pending_gang_draw_seat == seat
        self.pending_gang_draw_seat = None
        if seat == self.user_seat:
            self.log(self.t(f"你摸到 {compact_tiles([tile], self.lang, self.use_color)}。", f"You drew {compact_tiles([tile], self.lang, self.use_color)}."))
        else:
            self.log(self.t(f"{player.name} 摸牌。", f"{player.name} draws."))
        return tile

    def discard_tile(self, seat: int, tile: str) -> None:
        player = self.players[seat]
        player.hand.remove(tile)
        player.hand = sort_tiles(player.hand)
        player.discards.append(tile)
        self.last_discard = tile
        self.last_discarder = seat
        self.last_draw_was_gang = False
        label = compact_tiles([tile], self.lang, self.use_color)
        if seat == self.user_seat:
            self.log(self.t(f"你打出 {label}。", f"You discarded {label}."))
        else:
            self.log(self.t(f"{player.name} 打出 {label}。", f"{player.name} discarded {label}."))

    def chi_options(self, hand: list[str], discard: str) -> list[ClaimOption]:
        if not is_suited(discard):
            return []
        rank = int(discard[0])
        suit = discard[1]
        candidates: list[ClaimOption] = []
        for offsets in [(-2, -1), (-1, 1), (1, 2)]:
            numbers = [rank + offset for offset in offsets]
            if min(numbers) < 1 or max(numbers) > 9:
                continue
            temp_hand = hand.copy()
            chosen: list[str] = []
            valid = True
            for number in numbers:
                needed_tile = f"{number}{suit}"
                if needed_tile in temp_hand:
                    temp_hand.remove(needed_tile)
                    chosen.append(needed_tile)
                else:
                    valid = False
                    break
            if not valid:
                continue
            meld_tiles = sort_tiles(chosen + [discard])
            summary = compact_tiles(meld_tiles, self.lang, self.use_color)
            candidates.append(ClaimOption(-1, "chi", chosen, meld_tiles, summary))
        return candidates

    def claim_candidates_for_seat(self, seat: int, discard: str, discarder: int) -> list[ClaimOption]:
        player = self.players[seat]
        options: list[ClaimOption] = []

        if can_win(player.hand + [discard], len(player.melds)):
            options.append(ClaimOption(seat, "hu", [], [discard], compact_tiles([discard], self.lang, self.use_color)))

        peng_tiles = pick_matching_tiles(player.hand, discard, 2)
        if peng_tiles:
            options.append(
                ClaimOption(
                    seat,
                    "peng",
                    peng_tiles,
                    sort_tiles(peng_tiles + [discard]),
                    compact_tiles(sort_tiles(peng_tiles + [discard]), self.lang, self.use_color),
                )
            )

        gang_tiles = pick_matching_tiles(player.hand, discard, 3)
        if gang_tiles:
            options.append(
                ClaimOption(
                    seat,
                    "gang",
                    gang_tiles,
                    sort_tiles(gang_tiles + [discard]),
                    compact_tiles(sort_tiles(gang_tiles + [discard]), self.lang, self.use_color),
                )
            )

        if seat == next_seat(discarder):
            for option in self.chi_options(player.hand, discard):
                options.append(ClaimOption(seat, option.kind, option.hand_tiles, option.meld_tiles, option.summary))

        return options

    def bot_wants_claim(self, player: Player, option: ClaimOption) -> bool:
        if option.kind == "hu":
            return True
        current_score = evaluate_hand(player.hand) + len(player.melds) * 3.0
        future_hand = remove_tiles_from_hand(player.hand, option.hand_tiles)
        future_score = evaluate_hand(future_hand) + (len(player.melds) + 1) * 4.0
        threshold = {"chi": 0.8, "peng": 0.4, "gang": 1.0}[option.kind]
        return future_score >= current_score + threshold

    def pass_aliases(self) -> set[str]:
        return {"", "pass", "p", "过", "過"}

    def kind_aliases(self, kind: str) -> set[str]:
        aliases = {kind}
        if kind == "hu":
            aliases.update({"h", "胡"})
        elif kind == "chi":
            aliases.update({"吃"})
        elif kind == "peng":
            aliases.update({"碰"})
        elif kind == "gang":
            aliases.update({"杠"})
        return aliases

    def ask_user_claim(self, kind: str, options: list[ClaimOption]) -> ClaimOption | None:
        if self.auto_user or self.user_trustee:
            if kind == "hu":
                return options[0]
            return None

        extra = [self.t(f"你可以 {self.action_label(kind)}。", f"You can {self.action_label(kind)}.")]
        if kind == "chi":
            for index, option in enumerate(options, start=1):
                extra.append(f"chi{index}: {option.summary}")
            prompt = self.t("输入 chi1 / chi2 / pass > ", "Enter chi1 / chi2 / pass > ")
        else:
            extra.append(f"{kind}: {options[0].summary}")
            prompt = self.t(f"输入 {kind} / pass > ", f"Enter {kind} / pass > ")

        self.render_table(prompt=self.t("你有可操作的副露/胡牌机会。", "You can claim this tile."), extra_lines=extra)
        while True:
            command = self.safe_input(prompt).lower()
            if command in self.pass_aliases():
                return None
            if kind == "chi":
                normalized = command.replace("吃", "chi")
                if normalized.startswith("chi"):
                    suffix = normalized[3:]
                    if suffix.isdigit():
                        choice = int(suffix) - 1
                        if 0 <= choice < len(options):
                            return options[choice]
                    if normalized == "chi" and len(options) == 1:
                        return options[0]
            if command in self.kind_aliases(kind):
                return options[0]
            self.render_table(prompt=self.t("输入无效，重新选择。", "Invalid input. Try again."), extra_lines=extra)

    def choose_bot_claim(self, player: Player, options: list[ClaimOption]) -> ClaimOption | None:
        ranked = {"hu": 100, "gang": 20, "peng": 15, "chi": 10}
        options = sorted(options, key=lambda option: ranked[option.kind], reverse=True)
        for option in options:
            if self.bot_wants_claim(player, option):
                return option
        return None

    def apply_claim(self, option: ClaimOption, discarder: int) -> None:
        if option.kind == "hu":
            self.settle_win(option.seat, self.last_discard or option.meld_tiles[0], False, discarder)
            return

        discarder_player = self.players[discarder]
        if discarder_player.discards and discarder_player.discards[-1] == self.last_discard:
            discarder_player.discards.pop()

        claimant = self.players[option.seat]
        claimant.hand = remove_tiles_from_hand(claimant.hand, option.hand_tiles)
        claimant.melds.append(Meld(option.kind, option.meld_tiles, discarder))
        action = self.action_label(option.kind)
        self.log(
            self.t(
                f"{claimant.name} {action} 了 {compact_tiles([self.last_discard], self.lang, self.use_color)}。",
                f"{claimant.name} called {action} on {compact_tiles([self.last_discard], self.lang, self.use_color)}.",
            )
        )
        self.current_seat = option.seat
        self.pending_draw = option.kind == "gang"
        self.pending_gang_draw_seat = option.seat if option.kind == "gang" else None
        self.last_discard = None
        self.last_discarder = None

    def resolve_claims(self, discarder: int, discard: str) -> bool:
        claim_order = [next_seat(discarder), next_seat(next_seat(discarder)), next_seat(next_seat(next_seat(discarder)))]
        options_by_priority: dict[str, list[ClaimOption]] = {"hu": [], "gang": [], "peng": [], "chi": []}
        for seat in claim_order:
            for option in self.claim_candidates_for_seat(seat, discard, discarder):
                options_by_priority[option.kind].append(option)

        for kind in ["hu", "gang", "peng", "chi"]:
            options = options_by_priority[kind]
            if not options:
                continue

            human_options = [option for option in options if option.seat == self.user_seat]
            if human_options:
                selected = self.ask_user_claim(kind, human_options)
                if selected:
                    self.apply_claim(selected, discarder)
                    return True
                options = [option for option in options if option.seat != self.user_seat]

            for seat in claim_order:
                seat_options = [option for option in options if option.seat == seat]
                if not seat_options:
                    continue
                selected = self.choose_bot_claim(self.players[seat], seat_options)
                if selected:
                    self.apply_claim(selected, discarder)
                    return True

        self.last_discard = None
        self.last_discarder = None
        return False

    def score_profile(self, winner_seat: int, winning_tile: str, self_draw: bool) -> ScoreProfile:
        winner = self.players[winner_seat]
        seat_wind = self.seat_wind_tile(winner_seat)
        concealed_tiles = winner.hand.copy() if self_draw else sort_tiles(winner.hand + [winning_tile])
        decomposition = find_win_decomposition(concealed_tiles, len(winner.melds))

        hu_extra = 0
        tai = 0
        hu_lines: list[str] = []
        tai_lines: list[str] = []

        for meld in winner.melds:
            if meld.kind not in {"peng", "gang"}:
                continue
            base_tile = exposed_triplet_base(meld.tiles)
            if base_tile is None:
                continue
            hu_value = kong_hu(base_tile, concealed=False) if meld.kind == "gang" else triplet_hu(base_tile, concealed=False)
            hu_extra += hu_value
            hu_lines.append(f"{self.action_label(meld.kind)} {compact_label(base_tile, self.lang)} {hu_value}{self.t('胡', ' hu')}")
            if base_tile in {"C", "F"} or base_tile == seat_wind:
                tai += 1
                tai_lines.append(f"{compact_label(base_tile, self.lang)}{self.t('刻/杠 1台', ' set 1 tai')}")

        if decomposition is not None:
            if decomposition.pair_missing == 0 and decomposition.pair_tile in {"C", "F", seat_wind}:
                hu_extra += 2
                hu_lines.append(f"{compact_label(decomposition.pair_tile, self.lang)}{self.t('将 2胡', ' pair 2 hu')}")

            for kind, base_tile, meta in decomposition.melds:
                if kind == "triplet" and meta == 0 and base_tile != "J":
                    hu_value = triplet_hu(base_tile, concealed=True)
                    hu_extra += hu_value
                    hu_lines.append(f"{self.t('暗刻', 'concealed triplet')} {compact_label(base_tile, self.lang)} {hu_value}{self.t('胡', ' hu')}")
                    if base_tile in {"C", "F"} or base_tile == seat_wind:
                        tai += 1
                        tai_lines.append(f"{compact_label(base_tile, self.lang)}{self.t('暗刻 1台', ' concealed set 1 tai')}")

            all_triplets = decomposition.concealed_all_triplets and all(meld.kind in {"peng", "gang"} for meld in winner.melds)
            if all_triplets:
                hu_extra += 2
                hu_lines.append(self.t("碰碰胡 2胡", "All triplets 2 hu"))

            if is_suited(winning_tile):
                for kind, base_tile, meta in decomposition.melds:
                    if kind != "sequence":
                        continue
                    if sequence_middle_tile(base_tile) == winning_tile and not (meta & 0b010):
                        hu_extra += 2
                        hu_lines.append(self.t("嵌张 2胡", "Closed wait 2 hu"))
                        break
                    if base_tile[0] == "1" and winning_tile == f"3{base_tile[1]}" and not (meta & 0b100):
                        hu_extra += 2
                        hu_lines.append(self.t("边张 2胡", "Edge wait 2 hu"))
                        break
                    if base_tile[0] == "7" and winning_tile == base_tile and not (meta & 0b001):
                        hu_extra += 2
                        hu_lines.append(self.t("边张 2胡", "Edge wait 2 hu"))
                        break

        if self_draw:
            hu_extra += 2
            hu_lines.append(self.t("自摸 2胡", "Self-draw 2 hu"))

        all_tiles = concealed_tiles + [tile for meld in winner.melds for tile in meld.tiles]
        visible_tiles = [tile for tile in all_tiles if tile != "J"]
        suits_used = {tile[1] for tile in visible_tiles if is_suited(tile)}
        has_honors = any(tile in {"E", "S", "W", "N", "C", "F"} for tile in visible_tiles)
        if len(suits_used) == 1 and visible_tiles:
            if has_honors:
                tai += 2
                tai_lines.append(self.t("混一色 2台", "Half flush 2 tai"))
            else:
                tai_lines.append(self.t("清一色 封顶", "Full flush limit"))

        if visible_tiles and all(tile in {"E", "S", "W", "N", "C", "F"} for tile in visible_tiles):
            tai_lines.append(self.t("字一色 封顶", "All honors limit"))

        all_tile_counts = Counter(visible_tiles)
        if all(all_tile_counts[wind] >= 3 for wind in {"E", "S", "W", "N"}):
            tai_lines.append(self.t("四风齐聚 封顶", "Four winds limit"))

        if "J" not in all_tiles:
            tai += 1
            tai_lines.append(self.t("无白板 1台", "No wildcard 1 tai"))

        if self_draw and self.last_draw_was_gang:
            tai += 1
            tai_lines.append(self.t("杠开 1台", "Kong draw 1 tai"))

        limit_lines = [line for line in tai_lines if self.t("封顶", "limit") in line]
        tai_lines = [line for line in tai_lines if line not in limit_lines]

        raw_total = (10 + hu_extra) * (2 ** tai)
        if limit_lines:
            raw_total = max(raw_total, SCORE_CAP)
        total = min(SCORE_CAP, raw_total)
        if total == SCORE_CAP and raw_total > SCORE_CAP:
            tai_lines.append(self.t("封顶 100", "Capped at 100"))

        return ScoreProfile(
            hu_extra=hu_extra,
            tai=tai,
            total=total,
            hu_lines=hu_lines,
            tai_lines=tai_lines,
            limit_lines=limit_lines,
        )

    def settle_win(self, winner_seat: int, winning_tile: str, self_draw: bool, source_seat: int | None = None) -> None:
        winner = self.players[winner_seat]
        profile = self.score_profile(winner_seat, winning_tile, self_draw)
        deltas = {seat: 0 for seat in range(4)}

        for seat in range(4):
            if seat == winner_seat:
                continue
            if self_draw:
                pay = profile.total
            else:
                pay = profile.total if seat == source_seat else 0
            deltas[seat] -= pay
            deltas[winner_seat] += pay

        for seat, delta in deltas.items():
            self.players[seat].points += delta

        if self_draw:
            reason = self.t(
                f"{winner.name} 自摸胡 {compact_tiles([winning_tile], self.lang, self.use_color)}。",
                f"{winner.name} wins by self-draw {compact_tiles([winning_tile], self.lang, self.use_color)}.",
            )
        else:
            source = self.players[source_seat] if source_seat is not None else None
            reason = self.t(
                f"{winner.name} 点炮胡 {compact_tiles([winning_tile], self.lang, self.use_color)}，放铳者是 {source.name if source else '?'}。",
                f"{winner.name} wins on {compact_tiles([winning_tile], self.lang, self.use_color)} from {source.name if source else '?'}.",
            )

        summary_lines = [
            ansi(self.t(f"本局结束: {winner.name} 获胜", f"Round over: {winner.name} wins"), COLOR_MAP["good"], self.use_color),
            reason,
            f"{self.t('庄家', 'Dealer')}: {self.dealer_name()}",
            f"{self.t('胡数', 'Hu')}: 10 + {profile.hu_extra} = {10 + profile.hu_extra}",
            f"{self.t('台数', 'Tai')}: {profile.tai}",
            f"{self.t('本局计分', 'Round value')}: {profile.total}",
        ]
        if profile.limit_lines:
            summary_lines.append(f"{self.t('封顶牌型', 'Limit hands')}: " + " / ".join(profile.limit_lines))
        if profile.hu_lines:
            summary_lines.append(f"{self.t('胡数细项', 'Hu breakdown')}: " + " / ".join(profile.hu_lines))
        if profile.tai_lines:
            summary_lines.append(f"{self.t('台数细项', 'Tai breakdown')}: " + " / ".join(profile.tai_lines))
        summary_lines.append(f"{self.t('点数结算', 'Point settlement')}:")
        for seat in range(4):
            player = self.players[seat]
            delta = deltas[seat]
            sign = f"+{delta}" if delta > 0 else str(delta)
            color = COLOR_MAP["good"] if delta > 0 else COLOR_MAP["bad"] if delta < 0 else COLOR_MAP["muted"]
            summary_lines.append(f"{player.name}: {ansi(f'{sign} pt', color, self.use_color)} -> {player.points} pt")

        self.winner_seat = winner_seat
        self.win_reason = reason
        self.settlement = Settlement(summary_lines=summary_lines, deltas=deltas, total=profile.total, score_profile=profile)
        self.log(reason)

    def declare_self_draw(self, seat: int) -> None:
        player = self.players[seat]
        winning_tile = self.last_drawn_tile if self.last_drawn_by == seat and self.last_drawn_tile else player.hand[-1]
        self.settle_win(seat, winning_tile, True, None)

    def user_turn(self) -> str | None:
        player = self.players[self.user_seat]
        ready_options = self.ready_options_for_user()
        if can_win(player.hand, len(player.melds)):
            self.render_table(prompt=self.t("你已成胡，可输入 hu 自摸，或继续打牌。", "You are ready to win. Type hu or keep discarding."))
        elif ready_options:
            self.render_table(
                prompt=self.t(
                    "你已接近听牌，可输入 ting 查看听口，或输入 auto 开启听牌托管。",
                    "You can enter ready state. Use ting to inspect waits, or auto to enable ready-hand auto-play.",
                )
            )
        while True:
            command = self.safe_input(
                self.t(
                    "出牌指令 (数字 / d 九万 / d 1m / hu / hint / ting / auto / quit) > ",
                    "Discard command (number / d 1Wan / d 1m / hu / hint / ting / auto / quit) > ",
                )
            ).strip()
            lowered = command.lower()
            if lowered in {"quit", "q", "退出"}:
                self.log(self.t("你提前结束了整场牌局。", "You ended the whole match early."))
                self.user_requested_exit = True
                self.win_reason = self.t("牌局被玩家中止。", "The match was aborted by the player.")
                self.settlement = Settlement(
                    summary_lines=[
                        ansi(self.t("本局结束: 中止", "Round over: aborted"), COLOR_MAP["muted"], self.use_color),
                        self.win_reason,
                        f"{self.t('当前总榜', 'Current standings')}:",
                    ]
                    + self.point_table_lines()
                )
                return None
            if lowered in {"hu", "h", "胡"} and can_win(player.hand, len(player.melds)):
                self.declare_self_draw(self.user_seat)
                return None
            if lowered in {"hint", "t", "提示"}:
                suggested = best_discard(player.hand, len(player.melds))
                self.render_table(prompt=self.t(f"建议打出 {compact_tiles([suggested], self.lang, self.use_color)}。", f"Suggested discard: {compact_tiles([suggested], self.lang, self.use_color)}."))
                continue
            if lowered in {"ting", "listen", "听", "听牌"}:
                if not ready_options:
                    self.render_table(prompt=self.t("当前还没有形成听牌的出牌选择。", "No ready-hand discard is available yet."))
                    continue
                self.render_table(
                    prompt=self.t("当前听口如下。", "Current ready-hand options."),
                    extra_lines=self.ready_option_lines(ready_options),
                )
                continue
            if lowered in {"auto", "a", "托管"}:
                choice = self.best_ready_choice()
                if choice is None:
                    self.render_table(prompt=self.t("当前还没听牌，不能开启托管。", "You are not in ready range yet, so auto-play is unavailable."))
                    continue
                discard, waits = choice
                self.user_trustee = True
                self.log(
                    self.t(
                        f"你已开启听牌托管，自动打出 {compact_tiles([discard], self.lang, self.use_color)}，听 {compact_tiles(waits, self.lang, self.use_color)}。",
                        f"Ready-hand auto-play enabled. Auto-discard {compact_tiles([discard], self.lang, self.use_color)} and wait on {compact_tiles(waits, self.lang, self.use_color)}.",
                    )
                )
                self.discard_tile(self.user_seat, discard)
                return discard

            parts = lowered.split()
            index: int | None = None
            if lowered.isdigit():
                index = int(lowered) - 1
            elif len(parts) == 2 and parts[0] == "d" and parts[1].isdigit():
                index = int(parts[1]) - 1
            elif len(parts) == 2 and parts[0] == "d":
                matched_tile = match_tile_input(player.hand, parts[1])
                if matched_tile:
                    self.discard_tile(self.user_seat, matched_tile)
                    return matched_tile
            elif match_tile_input(player.hand, lowered):
                matched_tile = match_tile_input(player.hand, lowered)
                if matched_tile:
                    self.discard_tile(self.user_seat, matched_tile)
                    return matched_tile

            if index is not None and 0 <= index < len(player.hand):
                tile = sort_tiles(player.hand)[index]
                self.discard_tile(self.user_seat, tile)
                return tile

            self.render_table(
                prompt=self.t(
                    "指令无效。可输入 3、d 九万、d 1m、hu、hint、ting、auto、quit。",
                    "Invalid command. Try 3, d 1Wan, d 1m, hu, hint, ting, auto, or quit.",
                )
            )

    def bot_turn(self, seat: int) -> str | None:
        player = self.players[seat]
        if can_win(player.hand, len(player.melds)):
            self.declare_self_draw(seat)
            return None
        if seat == self.user_seat and self.user_trustee:
            choice = self.best_ready_choice()
            if choice is not None:
                discard, waits = choice
                self.log(
                    self.t(
                        f"听牌托管打出 {compact_tiles([discard], self.lang, self.use_color)}，继续听 {compact_tiles(waits, self.lang, self.use_color)}。",
                        f"Ready-hand auto-play discards {compact_tiles([discard], self.lang, self.use_color)} and keeps waiting on {compact_tiles(waits, self.lang, self.use_color)}.",
                    )
                )
                self.discard_tile(seat, discard)
                return discard
        tile = best_discard(player.hand, len(player.melds))
        self.discard_tile(seat, tile)
        return tile

    def round_draw(self, reason: str) -> None:
        self.win_reason = reason
        self.settlement = Settlement(
            summary_lines=[
                ansi(self.t("本局结束: 流局", "Round over: draw"), COLOR_MAP["muted"], self.use_color),
                reason,
                f"{self.t('当前总榜', 'Current standings')}:",
            ]
            + self.point_table_lines()
        )

    def take_turn(self) -> bool:
        if self.turn_counter >= self.max_turns:
            self.round_draw(self.t("达到回合上限，按流局处理。", "Reached turn limit. Round ends in draw."))
            return False

        player = self.players[self.current_seat]
        self.turn_counter += 1

        if self.pending_draw:
            drawn = self.draw_tile(self.current_seat)
            if drawn is None:
                self.round_draw(self.t("牌墙摸空，流局。", "The wall is empty. Round ends in draw."))
                return False
            self.pending_draw = False
            if self.current_seat == self.user_seat and not self.auto_user:
                self.render_table(prompt=self.t(f"你摸到了 {compact_tiles([drawn], self.lang, self.use_color)}。", f"You drew {compact_tiles([drawn], self.lang, self.use_color)}."))
            self.sleep(0.35)

        if player.is_bot or (self.auto_user or self.user_trustee) and self.current_seat == self.user_seat:
            discard = self.bot_turn(self.current_seat)
        else:
            self.render_table(prompt=self.t("轮到你出牌。", "Your turn to discard."))
            discard = self.user_turn()

        if self.winner_seat is not None or discard is None:
            return False

        self.sleep(0.35)
        claimed = self.resolve_claims(self.current_seat, discard)
        if self.winner_seat is not None:
            return False
        if claimed:
            return True
        self.current_seat = next_seat(self.current_seat)
        self.pending_draw = True
        return True

    def result_lines(self) -> list[str]:
        if self.settlement.summary_lines:
            return self.settlement.summary_lines
        return [ansi(self.t("本局结束: 流局", "Round over: draw"), COLOR_MAP["muted"], self.use_color), self.win_reason or self.t("无人胡牌。", "No one won.")]

    def rotate_dealer_for_next_round(self) -> None:
        if self.user_requested_exit:
            return
        if self.winner_seat == self.dealer_seat:
            self.log(self.t(f"{self.dealer_name()} 连庄。", f"{self.dealer_name()} remains dealer."))
            return
        old_dealer = self.dealer_name()
        self.dealer_seat = next_seat(self.dealer_seat)
        self.log(self.t(f"{old_dealer} 下庄，{self.dealer_name()} 接庄。", f"{old_dealer} passes the deal to {self.dealer_name()}."))

    def session_should_end(self) -> tuple[bool, list[str] | None]:
        if self.user_requested_exit:
            return True, [
                ansi(self.t("整场结束: 玩家中止", "Match over: aborted by player"), COLOR_MAP["muted"], self.use_color),
                f"{self.t('当前总榜', 'Current standings')}:",
            ] + self.point_table_lines()
        bankrupt = [player for player in self.players if player.points <= 0]
        if bankrupt:
            return True, [
                ansi(self.t("整场结束: 有人爆分", "Match over: someone busted"), COLOR_MAP["good"], self.use_color),
                self.t(f"{bankrupt[0].name} 点数跌到 0 以下，牌桌收场。", f"{bankrupt[0].name} dropped to 0 or below. Match ends."),
                f"{self.t('最终总榜', 'Final standings')}:",
            ] + self.point_table_lines()
        if self.match_rounds and self.round_index >= self.match_rounds:
            return True, [
                ansi(self.t("整场结束: 达到局数上限", "Match over: round limit reached"), COLOR_MAP["good"], self.use_color),
                f"{self.t('最终总榜', 'Final standings')}:",
            ] + self.point_table_lines()
        return False, None

    def round_end_prompt(self, final_lines: list[str] | None = None) -> bool:
        if final_lines is not None:
            self.render_table(extra_lines=final_lines, prompt=self.t("按回车返回大厅。", "Press Enter to return to lobby."))
            self.safe_input("")
            return False

        if self.auto_user:
            self.render_table(
                extra_lines=self.result_lines(),
                prompt=self.t("托管中，稍后自动进入下一局。", "Auto mode: advancing to the next round shortly."),
            )
            self.sleep(0.25)
            return True

        self.render_table(
            extra_lines=self.result_lines(),
            prompt=self.t("回车继续下局，输入 lobby 返回大厅，输入 quit 结束整场。", "Press Enter for next round, type lobby to leave, or quit to end the match."),
        )
        command = self.safe_input("> ").lower()
        if command in {"", "next", "n", "继续"}:
            return True
        if command in {"quit", "q", "结束"}:
            self.user_requested_exit = True
            return False
        return False

    def play(self) -> None:
        self.join_room_sequence()
        while True:
            self.setup_round()
            running = True
            while running:
                self.render_table(prompt=self.t("牌局进行中...", "Round in progress..."))
                running = self.take_turn()
            should_end, final_lines = self.session_should_end()
            if should_end:
                self.round_end_prompt(final_lines if final_lines is not None else self.result_lines())
                return
            continue_match = self.round_end_prompt()
            if not continue_match:
                self.render_table(
                    extra_lines=[
                        ansi(self.t("整场暂停，返回大厅。", "Match paused, returning to lobby."), COLOR_MAP["muted"], self.use_color),
                        f"{self.t('当前总榜', 'Current standings')}:",
                    ]
                    + self.point_table_lines(),
                    prompt=self.t("按回车返回大厅。", "Press Enter to return to lobby."),
                )
                self.safe_input("")
                return
            self.rotate_dealer_for_next_round()


class MahjongLobbyApp:
    def __init__(self, args: argparse.Namespace):
        self.args = args
        self.lang = normalize_lang(args.lang)
        self.rng = random.Random(args.seed)
        self.use_color = not args.no_color and sys.stdout.isatty()
        self.no_delay = args.no_delay or not sys.stdout.isatty()
        self.notice = ""

    def t(self, zh: str, en: str) -> str:
        return pick(self.lang, zh, en)

    def banner(self) -> str:
        accent = COLOR_MAP["accent"] if self.use_color else ""
        reset = RESET if self.use_color else ""
        return textwrap.dedent(
            f"""
            {accent}███╗   ███╗ █████╗ ██╗  ██╗     ██╗ ██████╗ ███╗   ██╗ ██████╗{reset}
            {accent}████╗ ████║██╔══██╗██║  ██║     ██║██╔═══██╗████╗  ██║██╔════╝{reset}
            {accent}██╔████╔██║███████║███████║     ██║██║   ██║██╔██╗ ██║██║  ███╗{reset}
            {accent}██║╚██╔╝██║██╔══██║██╔══██║██   ██║██║   ██║██║╚██╗██║██║   ██║{reset}
            {accent}██║ ╚═╝ ██║██║  ██║██║  ██║╚█████╔╝╚██████╔╝██║ ╚████║╚██████╔╝{reset}
            {accent}╚═╝     ╚═╝╚═╝  ╚═╝╚═╝  ╚═╝ ╚════╝  ╚═════╝ ╚═╝  ╚═══╝ ╚═════╝ {reset}
            """
        ).strip("\n")

    def safe_input(self, prompt: str) -> str:
        try:
            return input(prompt).strip()
        except EOFError:
            return ""

    def lobby(self) -> int:
        demo_rounds = self.args.match_rounds if self.args.match_rounds > 0 else DEFAULT_DEMO_ROUNDS
        sys.stdout.write(CLEAR)
        sys.stdout.write(self.banner())
        sys.stdout.write("\n")
        sys.stdout.write(f"{BOLD}{self.t('台州麻将 · 文字线上大厅模拟', 'Taizhou Mahjong · Text Lobby')}{RESET}\n")
        sys.stdout.write(self.t("玩法: 白板万能 / 无花 / 连打多局 / 更接近台州胡数台数\n", "Mode: White wildcard / No flowers / multi-round session / closer Taizhou hu-tai scoring\n"))
        sys.stdout.write(self.t("牌友名单现在更中二，房间里味道对了。\n", "The rival names are now much more gloriously over-the-top.\n"))
        sys.stdout.write(f"{self.t('当前语言', 'Current language')}: {self.lang.upper()}\n")
        if self.notice:
            sys.stdout.write(f"{ansi(self.notice, COLOR_MAP['accent'], self.use_color)}\n")
            self.notice = ""
        sys.stdout.write("\n")
        sys.stdout.write(f"1. {self.t('快速匹配（连打多局）', 'Quick Match (multi-round)')}\n")
        sys.stdout.write(f"2. {self.t(f'托管演示（连续 {demo_rounds} 局）', f'Auto Demo ({demo_rounds} rounds)')}\n")
        sys.stdout.write(f"3. {self.t('规则速览', 'Rules')}\n")
        sys.stdout.write(f"4. {self.t('语言设置', 'Language')}\n")
        sys.stdout.write(f"5. {self.t('退出大厅', 'Exit')}\n\n")
        sys.stdout.flush()
        raw = self.safe_input(self.t("选择 > ", "Choose > "))
        return int(raw) if raw.isdigit() and raw in {"1", "2", "3", "4", "5"} else 0

    def change_language(self) -> None:
        sys.stdout.write(CLEAR)
        sys.stdout.write(f"{BOLD}{self.t('语言设置', 'Language Settings')}{RESET}\n\n")
        sys.stdout.write(self.t("输入 `zh` 或 `ch` 切换为中文，输入 `en` 切换为英文。\n\n", "Type `zh` or `ch` for Chinese, or `en` for English.\n\n"))
        raw = normalize_lang(self.safe_input(self.t("语言 > ", "Language > ")))
        self.lang = raw
        self.notice = self.t(f"语言已切换为 {self.lang.upper()}。", f"Language switched to {self.lang.upper()}.")

    def effective_match_rounds(self, auto_user: bool) -> int:
        if self.args.match_rounds > 0:
            return self.args.match_rounds
        if auto_user:
            return DEFAULT_DEMO_ROUNDS
        return 0

    def new_game(self, auto_user: bool) -> TaizhouMahjongGame:
        return TaizhouMahjongGame(
            rng=self.rng,
            lang=self.lang,
            use_color=self.use_color,
            no_delay=self.no_delay,
            auto_user=auto_user,
            max_turns=self.args.max_turns,
            match_rounds=self.effective_match_rounds(auto_user),
        )

    def run(self) -> int:
        if self.args.demo:
            self.new_game(auto_user=True).play()
            return 0

        while True:
            choice = self.lobby()
            if choice == 1:
                self.new_game(auto_user=False).play()
                continue
            if choice == 2:
                self.new_game(auto_user=True).play()
                continue
            if choice == 3:
                self.new_game(auto_user=False).show_rules()
                continue
            if choice == 4:
                self.change_language()
                continue
            if choice == 5:
                return 0
            self.notice = self.t("请输入 1-5。", "Please enter 1-5.")

    def __call__(self) -> int:
        return self.run()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Taizhou Mahjong CLI prototype")
    parser.add_argument("--demo", action="store_true", help="auto-play a local match and exit")
    parser.add_argument("--seed", type=int, default=7, help="random seed for room generation")
    parser.add_argument("--max-turns", type=int, default=120, help="maximum turns per round before draw")
    parser.add_argument("--match-rounds", type=int, default=0, help="number of rounds in a match; 0 means lobby-controlled")
    parser.add_argument("--no-delay", action="store_true", help="disable lobby and action delays")
    parser.add_argument("--no-color", action="store_true", help="disable ANSI colors")
    parser.add_argument("--lang", default="zh", choices=["zh", "ch", "en"], help="interface language")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    app = MahjongLobbyApp(args)
    return app()


if __name__ == "__main__":
    raise SystemExit(main())
