"""サンドボックス実行のラウンドトリップ。

オーケストレータ側(SandboxRunner)は bundle を store に置き、Job を起動し、
結果を読む。Job 側(run_bundle)は bundle を取り出して pytest を実行し結果を書く。
GCS/Run はフェイク、pytest は実物。Executor はフェイク内で run_bundle を呼んで
Job 実行を模す。
"""
import uuid

import pytest

from app.agents.sandbox import SandboxRunner, run_bundle


class FakeStore:
    """パス→内容の辞書ストア(GCS の代用)。"""

    def __init__(self):
        self.objects: dict[str, str] = {}

    def put_tree(self, prefix: str, files: dict[str, str]) -> None:
        for rel, content in files.items():
            self.objects[f"{prefix}/{rel}"] = content

    def get_tree(self, prefix: str) -> dict[str, str]:
        out = {}
        for path, content in self.objects.items():
            if path.startswith(prefix + "/"):
                out[path[len(prefix) + 1 :]] = content
        return out

    def put_text(self, path: str, content: str) -> None:
        self.objects[path] = content

    def get_text(self, path: str) -> str:
        return self.objects[path]


class FakeExecutor:
    """execute() で run_bundle を呼び、Job 実行を模す。"""

    def __init__(self, store, tmp_path):
        self.store = store
        self.tmp_path = tmp_path
        self.calls = []

    def execute(self, env: dict[str, str]) -> None:
        self.calls.append(env)
        run_bundle(
            store=self.store,
            bucket=env["BUNDLE_BUCKET"],
            prefix=env["BUNDLE_PREFIX"],
            target=env["TEST_TARGET"],
            workdir=self.tmp_path / uuid.uuid4().hex,
        )


def _runner(store, executor):
    return SandboxRunner(
        bucket="bundle-bucket",
        store=store,
        executor=executor,
        source_files=lambda: {},  # 自己完結テストなので app ソース不要
    )


def test_passing_test_reports_success(tmp_path):
    store = FakeStore()
    runner = _runner(store, FakeExecutor(store, tmp_path))

    passed, output = runner.run(
        test_filename="tests/test_x.py", test_code="def test_ok():\n    assert True\n"
    )
    assert passed is True


def test_failing_test_reports_failure(tmp_path):
    store = FakeStore()
    runner = _runner(store, FakeExecutor(store, tmp_path))

    passed, output = runner.run(
        test_filename="tests/test_x.py", test_code="def test_no():\n    assert False\n"
    )
    assert passed is False
    assert "assert" in output.lower() or "fail" in output.lower()


def test_each_run_uses_a_unique_prefix(tmp_path):
    store = FakeStore()
    executor = FakeExecutor(store, tmp_path)
    runner = _runner(store, executor)

    runner.run(test_filename="tests/test_x.py", test_code="def test_ok():\n    assert True\n")
    runner.run(test_filename="tests/test_x.py", test_code="def test_ok():\n    assert True\n")

    prefixes = {e["BUNDLE_PREFIX"] for e in executor.calls}
    assert len(prefixes) == 2
