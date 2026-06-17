import pytest

from app.agents.workspace import validate_write_paths


def test_allows_app_and_tests():
    validate_write_paths(["app/services.py", "tests/test_x.py", "app/migrations/001.py"])


def test_rejects_self_modification_of_agents():
    with pytest.raises(ValueError):
        validate_write_paths(["app/agents/pipeline.py"])


def test_rejects_path_traversal():
    with pytest.raises(ValueError):
        validate_write_paths(["../etc/passwd"])


def test_rejects_workflow_and_infra():
    with pytest.raises(ValueError):
        validate_write_paths([".github/workflows/ci.yml"])
    with pytest.raises(ValueError):
        validate_write_paths(["infra/main.tf"])


def test_rejects_absolute_path():
    with pytest.raises(ValueError):
        validate_write_paths(["/etc/passwd"])
