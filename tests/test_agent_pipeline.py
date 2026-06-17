from app.agents.fake_llm import FakeLLM
from app.agents.pipeline import run_pipeline
from app.agents.schemas import TicketInput


def test_pipeline_reproduces_and_fixes_double_booking(tmp_path):
    ticket = TicketInput(
        title="同じ時間に二重予約できてしまう",
        steps="1. 会議室Aを10-11時で予約\n2. 同じ枠でもう一度予約",
        tobe="2回目は重複エラーになる",
        asis="2回目も予約できてしまう",
    )

    result = run_pipeline(
        ticket, ticket_id=1, llm=FakeLLM(), workspace_root=tmp_path / "ws"
    )

    assert result.kind == "bug"
    assert result.reproduced is True
    assert result.fixed is True
    assert result.attempts >= 1
    assert result.generated_test is not None
    assert result.patch is not None
    assert "app/services.py" in result.patch.files


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
