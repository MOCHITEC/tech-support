"""シークレット値の正規化(BOM・前後空白の除去)。"""
from app.agents.config import sanitize_secret


def test_strips_bom_and_whitespace():
    assert sanitize_secret("﻿AIzaKEY") == "AIzaKEY"
    assert sanitize_secret("  ghp_tok\n") == "ghp_tok"
    assert sanitize_secret("﻿ghp_tok\r\n") == "ghp_tok"
    assert sanitize_secret("clean") == "clean"
