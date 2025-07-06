import json
import os
import sys
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Test configuration
# ---------------------------------------------------------------------------
# Ensure ckpool_bot imports without complaining about missing BOT_TOKEN
os.environ.setdefault("BOT_TOKEN", "TEST_TOKEN")

# Add project root (where ckpool_bot.py resides) to import path
ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from ckpool_bot import is_ckpool  # noqa: E402  pylint: disable=wrong-import-position

# ---------------------------------------------------------------------------
# Parameterised test cases: (filename, expected_result)
# ---------------------------------------------------------------------------
TEST_BLOCKS = [
    (
        "000000000000000000020c5281e68cbf5b382e02e3a42d4a9d2965b08d1f8bb3.json",
        True,
    ),
    (
        "00000000000000000001f4a9a2444a36b37c21499d70d0a162aded570bfc729a.json",
        False,
    ),
]


@pytest.mark.parametrize("filename, expected", TEST_BLOCKS)
def test_is_ckpool(filename: str, expected: bool):
    """Ensure is_ckpool() returns expected boolean for cached block files."""

    block_path = ROOT_DIR / "blocks" / filename
    if not block_path.exists():
        pytest.skip(
            f"Cached block {filename} not found – run the bot first to cache it"
        )

    detail = json.loads(block_path.read_text())
    assert is_ckpool(detail) is expected
