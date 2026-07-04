"""外部シークレットの正規化。

Secret Manager に手動投入した値には、投入時のツール(PowerShell 等)由来の BOM や
末尾改行が混入しうる。これらは HTTP ヘッダ(Gemini API キー / GitHub トークン)に
入れるとエンコードエラーになるため、使用前に除去する。
"""

_BOM = "﻿"


def sanitize_secret(value: str) -> str:
    return value.replace(_BOM, "").strip()
