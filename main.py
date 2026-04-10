from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SKILL_SCRIPTS = ROOT / "skills" / "mahjong" / "scripts"
sys.path.insert(0, str(SKILL_SCRIPTS))

from mahjong_cli import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main())
