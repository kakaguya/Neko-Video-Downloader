"""Convenience launcher for source checkouts."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def main() -> int:
    try:
        from neko_downloader.app import main as app_main
    except ModuleNotFoundError as exc:
        if exc.name and exc.name.startswith("PyQt5"):
            print(
                "缺少 PyQt5。请先在当前 Python/Conda 环境执行：\n"
                "  python -m pip install -r requirements.txt\n",
                file=sys.stderr,
            )
            return 2
        raise
    return app_main()


if __name__ == "__main__":
    raise SystemExit(main())
