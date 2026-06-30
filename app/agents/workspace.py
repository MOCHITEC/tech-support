"""エージェントのサンドボックス作業領域と書き込みパスガード。

LLM が提案したファイル書き込みは、必ず許可パス(app/ と tests/、ただし
app/agents/ を除く)に収まることを決定論的に検証してから適用する。
作業はリポジトリのコピー上で行い、本体には触れない。
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from collections.abc import Iterable, Mapping
from pathlib import Path

# 書き込みを許可するトップレベル接頭辞。
_ALLOWED_PREFIXES = ("app/", "tests/")
# 許可接頭辞の配下でも書き込み禁止(エージェント自身のコードの自己改変防止)。
_FORBIDDEN_PREFIXES = ("app/agents/",)
# 作業領域に複製するディレクトリ(再帰や app.main 依存を避け、最小構成にする)。
_MATERIALIZE_DIRS = ("app", "docs")
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def validate_write_paths(paths: Iterable[str]) -> None:
    """書き込み対象が許可パス内かを検証する。1つでも違反すれば ValueError。"""
    for raw in paths:
        norm = raw.replace("\\", "/")
        if norm.startswith("/") or ".." in norm.split("/") or ":" in norm:
            raise ValueError(f"許可されないパスです: {raw}")
        if any(norm.startswith(p) for p in _FORBIDDEN_PREFIXES):
            raise ValueError(f"エージェント自身のコードは変更できません: {raw}")
        if not any(norm.startswith(p) for p in _ALLOWED_PREFIXES):
            raise ValueError(f"許可されないパスです: {raw}")


class Workspace:
    """リポジトリのコピー。テスト/パッチを適用し pytest を隔離実行する。"""

    def __init__(self, root: Path):
        self.root = root

    @classmethod
    def materialize(cls, dest: Path, source_root: Path | None = None) -> "Workspace":
        """source_root(既定はリポジトリルート、本番はクローン)から最小構成を複製する。"""
        root = source_root or _REPO_ROOT
        dest.mkdir(parents=True, exist_ok=True)
        for name in _MATERIALIZE_DIRS:
            src = root / name
            if src.exists():
                shutil.copytree(src, dest / name, dirs_exist_ok=True)
        # テストは conftest(フィクスチャ)のみ複製し、生成テストを書き込む土台にする。
        (dest / "tests").mkdir(exist_ok=True)
        (dest / "tests" / "__init__.py").touch()
        if (root / "tests" / "conftest.py").exists():
            shutil.copy2(root / "tests" / "conftest.py", dest / "tests" / "conftest.py")
        if (root / "pytest.ini").exists():
            shutil.copy2(root / "pytest.ini", dest / "pytest.ini")
        return cls(dest)

    def write_files(self, files: Mapping[str, str]) -> None:
        """検証済みパスにのみファイルを書き込む。"""
        validate_write_paths(files.keys())
        for rel, content in files.items():
            target = self.root / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")

    def read(self, rel: str) -> str:
        return (self.root / rel).read_text(encoding="utf-8")

    def snapshot(self) -> dict[str, str]:
        """作業領域内の全テキストファイルを 相対パス→内容 で返す(bundle 用)。"""
        files: dict[str, str] = {}
        for path in self.root.rglob("*"):
            if path.is_file() and "__pycache__" not in path.parts:
                rel = path.relative_to(self.root).as_posix()
                files[rel] = path.read_text(encoding="utf-8")
        return files

    def run_tests(self, target: str | None = None) -> tuple[bool, str]:
        """pytest を作業領域で実行し (全て成功したか, 出力) を返す。"""
        args = [sys.executable, "-m", "pytest", "-q"]
        args.append(target if target else "tests")
        proc = subprocess.run(
            args, cwd=self.root, capture_output=True, text=True, timeout=120
        )
        return proc.returncode == 0, proc.stdout + proc.stderr
