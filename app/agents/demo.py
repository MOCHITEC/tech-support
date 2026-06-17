"""エージェントパイプラインをローカルで一気通貫に動かすデモ。

実行: python -m app.agents.demo
仕込みバグ①(二重予約)の報告を想定し、トリアージ→再現→修正までを表示する。
"""
import difflib
import tempfile
from pathlib import Path

from app.agents.fake_llm import FakeLLM
from app.agents.pipeline import run_pipeline
from app.agents.schemas import TicketInput

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent

SAMPLE = TicketInput(
    title="同じ時間に二重予約できてしまう",
    steps="1. 会議室Aを10:00-11:00で予約\n2. 同じ枠でもう一度予約する",
    tobe="2回目は重複エラーになるはず",
    asis="2回目も予約できてしまった",
)


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        result = run_pipeline(
            SAMPLE, ticket_id=1, llm=FakeLLM(), workspace_root=Path(tmp) / "ws"
        )

    print("=" * 60)
    print(f"判定:        {result.kind}")
    print(f"根拠:        {result.rationale}")
    print(f"仕様引用:    {result.spec_citation}")
    print(f"再現:        {result.reproduced}")
    print(f"修正:        {result.fixed}（試行 {result.attempts} 回）")
    print(f"メッセージ:  {result.message}")

    if result.generated_test:
        print("\n--- 生成された再現テスト ---")
        print(result.generated_test.code)

    if result.patch:
        print("--- 修正の差分(app/services.py) ---")
        original = (_REPO_ROOT / "app" / "services.py").read_text(encoding="utf-8")
        new = result.patch.files["app/services.py"]
        diff = difflib.unified_diff(
            original.splitlines(), new.splitlines(),
            fromfile="a/app/services.py", tofile="b/app/services.py", lineterm="",
        )
        print("\n".join(diff))
    print("=" * 60)


if __name__ == "__main__":
    main()
