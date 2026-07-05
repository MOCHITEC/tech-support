import shutil
from pathlib import Path

from app.agents.fake_llm import FakeLLM
from app.agents.pipeline import run_pipeline
from app.agents.schemas import TicketInput

_REPO_ROOT = Path(__file__).resolve().parent.parent
_BUGGY_SERVICES = Path(__file__).resolve().parent / "fixtures" / "services_buggy.py"


def _buggy_source_root(tmp_path):
    """planted bug ① を確実に含む再現用ソースツリーを組み立てる。

    実 app/ を複製し app/services.py だけを既知のバグあり版で上書きするため、
    実装が修正済みのブランチ(修正 PR の CI 等)でも再現→修正を安定検証できる。
    """
    src = tmp_path / "src"
    shutil.copytree(_REPO_ROOT / "app", src / "app")
    (src / "tests").mkdir(parents=True)
    shutil.copy2(_REPO_ROOT / "tests" / "conftest.py", src / "tests" / "conftest.py")
    shutil.copy2(_REPO_ROOT / "pytest.ini", src / "pytest.ini")
    shutil.copy2(_BUGGY_SERVICES, src / "app" / "services.py")
    return src


def test_pipeline_reproduces_and_fixes_double_booking(tmp_path):
    ticket = TicketInput(
        title="同じ時間に二重予約できてしまう",
        steps="1. 会議室Aを10-11時で予約\n2. 同じ枠でもう一度予約",
        tobe="2回目は重複エラーになる",
        asis="2回目も予約できてしまう",
    )

    result = run_pipeline(
        ticket,
        ticket_id=1,
        llm=FakeLLM(),
        workspace_root=tmp_path / "ws",
        source_root=_buggy_source_root(tmp_path),
    )

    assert result.kind == "bug"
    assert result.reproduced is True
    assert result.fixed is True
    assert result.attempts >= 1
    assert result.generated_test is not None
    assert result.patch is not None
    assert "app/services.py" in result.patch.files


class _FlakyFixLLM(FakeLLM):
    """propose_fix が最初の `fail_times` 回だけ空応答(例外)を返すフェイク。

    本番で Gemini が稀に空応答(.text=None)を返し propose_fix が例外になった事象を
    再現する。パイプラインはこれで落ちず、次の試行で作り直すべき。
    """

    def __init__(self, fail_times: int):
        self.fail_times = fail_times
        self.calls = 0

    def propose_fix(self, *args, **kwargs):
        self.calls += 1
        if self.calls <= self.fail_times:
            raise ValueError("Gemini が空応答を返しました (finish_reason=MAX_TOKENS)")
        return super().propose_fix(*args, **kwargs)


def test_pipeline_retries_when_fix_generation_fails(tmp_path):
    llm = _FlakyFixLLM(fail_times=1)
    ticket = TicketInput(
        title="同じ時間に二重予約できてしまう",
        steps="1. 会議室Aを10-11時で予約\n2. 同じ枠でもう一度予約",
        tobe="2回目は重複エラーになる",
        asis="2回目も予約できてしまう",
    )

    result = run_pipeline(
        ticket,
        ticket_id=1,
        llm=llm,
        workspace_root=tmp_path / "ws",
        source_root=_buggy_source_root(tmp_path),
    )

    assert result.fixed is True  # 空応答で落ちず、再試行で修正できる
    assert llm.calls >= 2


def test_pipeline_escalates_when_fix_generation_always_fails(tmp_path):
    llm = _FlakyFixLLM(fail_times=99)
    ticket = TicketInput(
        title="同じ時間に二重予約できてしまう",
        steps="1. 会議室Aを10-11時で予約\n2. 同じ枠でもう一度予約",
        tobe="2回目は重複エラーになる",
        asis="2回目も予約できてしまう",
    )

    # 常に空応答でも例外で落ちず、上限まで再試行してエスカレーションする。
    result = run_pipeline(
        ticket,
        ticket_id=1,
        llm=llm,
        workspace_root=tmp_path / "ws",
        source_root=_buggy_source_root(tmp_path),
        max_attempts=3,
    )

    assert result.fixed is False
    assert result.escalated is True
    assert llm.calls == 3


def test_pipeline_routes_feature_request_to_requirement_doc(tmp_path):
    ticket = TicketInput(
        title="繰り返し予約の機能がほしい",
        steps="毎週同じ枠を一括で予約したい",
        tobe="繰り返し予約ができる",
        asis="毎回手動で予約している",
    )

    result = run_pipeline(
        ticket, ticket_id=2, llm=FakeLLM(), workspace_root=tmp_path / "ws"
    )

    assert result.kind == "feature"
    assert result.requirement_doc
    assert result.patch is None
