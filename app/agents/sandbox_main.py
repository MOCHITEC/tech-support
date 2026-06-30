"""サンドボックス Cloud Run Job のエントリポイント。

env(BUNDLE_BUCKET / BUNDLE_PREFIX / TEST_TARGET)から bundle を取得し pytest を
実行、結果を書き戻す。秘密情報ゼロ・外向き通信遮断の Job 内で実行される。
"""
import os
import tempfile

from app.agents.sandbox import GcsBundleStore, run_bundle


def main() -> None:
    bucket = os.environ["BUNDLE_BUCKET"]
    prefix = os.environ["BUNDLE_PREFIX"]
    target = os.environ["TEST_TARGET"]
    run_bundle(
        store=GcsBundleStore(bucket),
        bucket=bucket,
        prefix=prefix,
        target=target,
        workdir=tempfile.mkdtemp(),
    )


if __name__ == "__main__":
    main()
