---
name: mahjong
description: Build, run, extend, or coach with the local CLI Mahjong simulator in this workspace, starting with Taizhou Mahjong. Use this skill when the user wants ASCII mahjong tiles, a text-mode online-lobby feel, Taizhou-style rules with white-board wildcards, no flowers, hand review, discard advice, ting analysis, or future regional rule expansion.
---

# Mahjong Skill

This skill owns the local Mahjong prototype in this workspace.

## Files

- `scripts/mahjong_cli.py`: lobby UI, table renderer, game loop, bot logic, and hu detection
- `scripts/review_hand.py`: deterministic hand-review helper for discard advice and ting analysis
- `references/taizhou_rules.md`: current rules, assumptions, and known simplifications
- `references/coaching.md`: workflow for reviewing hands and teaching decision-making
- `agents/openai.yaml`: OpenAI/Codex skill metadata
- `agents/claude.md`: concise adapter prompt for Claude-style assistants
- `agents/openclaw.md`: concise adapter prompt for OpenClaw-style assistants
- `../../main.py`: zero-dependency launcher

## Workflow

1. Read `references/taizhou_rules.md` before changing rule logic.
2. For hand review, coaching, or discard suggestions, prefer running `scripts/review_hand.py` instead of reasoning from memory.
3. Read `references/coaching.md` when the user wants training, post-hand review, or live advice.
4. Keep the project zero-dependency and runnable with `python3 main.py`.
5. Preserve the CLI hall feel: lobby, room entry, system feed, language toggle, and tile-face rendering.
6. Prefer additive rule changes and record rule decisions in `references/taizhou_rules.md`.

## Validation

- Smoke test: `python3 main.py --demo --no-delay --max-turns 120 --match-rounds 3`
- Hand review test: `python3 skills/mahjong/scripts/review_hand.py --hand "1m 2m 2s 3s 4s 6m 6m 6p 7p 8m 8p 9m 9s 白板"`
- Interactive run: `python3 main.py`

## Guardrails

- White board (`Ba`) is treated as the universal wildcard in win evaluation.
- White board does not participate in chi/pung/kong claims.
- There are no flower tiles in this prototype.
- Keep rendering monospace-safe. If you add more Unicode, verify alignment in a normal terminal.
- The current point and hu/tai system aims to be Taizhou-flavored, but it is still an in-project approximation rather than an authoritative local tournament ruleset.
- When reviewing a hand with missing table state, state assumptions explicitly.
