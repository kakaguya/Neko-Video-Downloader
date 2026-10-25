"""Backward-compatible launcher kept for users of the original project."""
from run import main

if __name__ == "__main__":
    raise SystemExit(main())
