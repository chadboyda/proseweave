"""Make the package and validation/ importable without installing."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for p in (ROOT / "src", ROOT / "validation"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
