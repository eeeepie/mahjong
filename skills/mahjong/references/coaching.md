# Coaching Workflow

Use this file when the user wants live advice, hand review, or practice.

## Inputs

- `hand`: concealed tiles, preferably 13 or 14 tiles
- `visible`: known discards and exposed meld tiles, if available
- `meld_count`: number of already-fixed melds when the user has chi/pung/kong exposed
- `lang`: `zh` or `en`

## Preferred Path

1. Run `scripts/review_hand.py` with the provided hand.
2. Use `--visible` when the user provides rivers or exposed melds so live-out counts are better.
3. If the hand is irregular or incomplete, say so instead of forcing precise advice.

## Response Shape

1. State whether the hand is already complete, one tile from winning, or still needs shape improvement.
2. Give the best discard and the main alternative if there is one.
3. Show waits and rough remaining live tiles.
4. Explain the lesson in plain language.

## Coaching Style

- Be concrete: explain shape, live tiles, and tradeoffs.
- Do not pretend to know hidden information.
- Prefer one strong recommendation over a long list.
- If the user is learning, add one short takeaway such as:
  - preserve connected shapes
  - keep more live waits
  - avoid dead honors
  - prefer wider ting over prettier shape
