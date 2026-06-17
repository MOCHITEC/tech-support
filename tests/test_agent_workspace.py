from app.agents.workspace import Workspace

_PASSING = """
def test_trivial_pass():
    assert 1 + 1 == 2
"""

_FAILING = """
def test_trivial_fail():
    assert 1 + 1 == 3
"""


def test_materialized_workspace_runs_passing_test(tmp_path):
    ws = Workspace.materialize(tmp_path / "ws")
    ws.write_files({"tests/test_gen.py": _PASSING})

    passed, output = ws.run_tests("tests/test_gen.py")

    assert passed is True


def test_materialized_workspace_detects_failing_test(tmp_path):
    ws = Workspace.materialize(tmp_path / "ws")
    ws.write_files({"tests/test_gen.py": _FAILING})

    passed, output = ws.run_tests("tests/test_gen.py")

    assert passed is False


def test_workspace_rejects_disallowed_write(tmp_path):
    import pytest

    ws = Workspace.materialize(tmp_path / "ws")
    with pytest.raises(ValueError):
        ws.write_files({"infra/main.tf": "x"})
