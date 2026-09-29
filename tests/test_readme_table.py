"""The README's property table matches the code (slow: set PROSEWEAVE_SLOW=1)."""
import os
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


@unittest.skipUnless(os.environ.get("PROSEWEAVE_SLOW"), "set PROSEWEAVE_SLOW=1 to run (about 4 minutes)")
class ReadmeTable(unittest.TestCase):
    def test_table_is_current(self):
        r = subprocess.run([sys.executable, str(ROOT / "tools" / "property_table.py"), "--check"],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)


if __name__ == "__main__":
    unittest.main()
