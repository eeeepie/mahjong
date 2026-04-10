Use `../SKILL.md` as the core instruction file for this skill.

For live play support or training:
- Load `../references/coaching.md`
- Prefer running `../scripts/review_hand.py`
- Use `../references/taizhou_rules.md` for rule assumptions

Behavior:
- Give deterministic, state-based advice
- Prioritize legal Taizhou-style interpretations from the local references
- Recommend one best discard before listing alternatives
- Include waits and rough live counts when possible
