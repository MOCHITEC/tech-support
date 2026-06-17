"""現在の main コミット SHA を取得する。チケットの判定基準を固定するため。"""
import subprocess
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent


def current_commit_sha() -> str | None:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=_REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if out.returncode == 0:
            return out.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        pass
    return None
