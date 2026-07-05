"""git 操作の seam 実装(create_fix_pr の RepoOps)。

既存のクローン上で、base から新しいブランチを切り、与えられたファイルを書き込んで
コミットし origin に push する。clone 自体は workspace 用意側の責務。
"""
import subprocess
from pathlib import Path

_BOT_NAME = "tech-support-bot"
_BOT_EMAIL = "tech-support-bot@users.noreply.github.com"


class GitRepoOps:
    def __init__(
        self,
        root: Path,
        *,
        base: str = "main",
        author_name: str = _BOT_NAME,
        author_email: str = _BOT_EMAIL,
    ):
        self.root = Path(root)
        self.base = base
        self.author_name = author_name
        self.author_email = author_email

    def _git(self, *args: str) -> None:
        proc = subprocess.run(
            ["git", "-C", str(self.root), *args],
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0:
            # git の stderr を握り潰さず例外に載せる(push 失敗の原因追跡のため)。
            raise RuntimeError(
                f"git {args[0]} failed (exit {proc.returncode}): "
                f"{(proc.stderr or proc.stdout).strip()}"
            )

    def commit_and_push(self, *, branch: str, files: dict[str, str], message: str) -> None:
        self._git("checkout", self.base)
        self._git("checkout", "-B", branch)
        for rel, content in files.items():
            target = self.root / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
            self._git("add", rel)
        self._git(
            "-c",
            f"user.name={self.author_name}",
            "-c",
            f"user.email={self.author_email}",
            "commit",
            "-m",
            message,
        )
        self._git("push", "--force", "-u", "origin", branch)
