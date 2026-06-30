"""サンドボックスでのテスト実行。

オーケストレータは生成テスト+ソースを bundle として GCS のランダム prefix に置き、
秘密情報ゼロ・外向き通信遮断の Cloud Run Job を起動する。Job は bundle を取り出し
pytest を実行して結果(passed/output)を同 prefix に書き戻す。store / executor は
seam にし、ローカルでは fake、本番では GCS / Cloud Run executions API を使う。
"""
import json
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Protocol

_RESULT_OBJECT = "result.json"


class BundleStore(Protocol):
    def put_tree(self, prefix: str, files: dict[str, str]) -> None: ...
    def get_tree(self, prefix: str) -> dict[str, str]: ...
    def put_text(self, path: str, content: str) -> None: ...
    def get_text(self, path: str) -> str: ...


class JobExecutor(Protocol):
    def execute(self, env: dict[str, str]) -> None: ...


class SandboxRunner:
    def __init__(self, *, bucket: str, store: BundleStore, executor: JobExecutor):
        self.bucket = bucket
        self.store = store
        self.executor = executor

    def run(self, *, files: dict[str, str], target: str) -> tuple[bool, str]:
        """与えられた全ファイルを bundle にして target を sandbox で実行する。"""
        prefix = f"runs/{uuid.uuid4().hex}"
        self.store.put_tree(f"{prefix}/source", files)

        self.executor.execute(
            {
                "BUNDLE_BUCKET": self.bucket,
                "BUNDLE_PREFIX": prefix,
                "TEST_TARGET": target,
            }
        )

        result = json.loads(self.store.get_text(f"{prefix}/{_RESULT_OBJECT}"))
        return result["passed"], result["output"]


def run_bundle(
    *, store: BundleStore, bucket: str, prefix: str, target: str, workdir: Path
) -> None:
    """Job 側エントリポイント: bundle を展開し pytest を実行、結果を書き戻す。"""
    workdir = Path(workdir)
    for rel, content in store.get_tree(f"{prefix}/source").items():
        path = workdir / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", target],
        cwd=workdir,
        capture_output=True,
        text=True,
        timeout=120,
    )
    store.put_text(
        f"{prefix}/{_RESULT_OBJECT}",
        json.dumps({"passed": proc.returncode == 0, "output": proc.stdout + proc.stderr}),
    )


class GcsBundleStore:
    """google-cloud-storage を使う BundleStore 実装。"""

    def __init__(self, bucket: str):
        from google.cloud import storage

        self._bucket = storage.Client().bucket(bucket)

    def put_tree(self, prefix: str, files: dict[str, str]) -> None:
        for rel, content in files.items():
            self._bucket.blob(f"{prefix}/{rel}").upload_from_string(content)

    def get_tree(self, prefix: str) -> dict[str, str]:
        out = {}
        for blob in self._bucket.list_blobs(prefix=prefix + "/"):
            out[blob.name[len(prefix) + 1 :]] = blob.download_as_text()
        return out

    def put_text(self, path: str, content: str) -> None:
        self._bucket.blob(path).upload_from_string(content)

    def get_text(self, path: str) -> str:
        return self._bucket.blob(path).download_as_text()


class CloudRunJobExecutor:
    """Cloud Run Job を env override 付きで同期実行する。"""

    def __init__(self, job: str, region: str, project: str):
        self._job = job
        self._region = region
        self._project = project

    def execute(self, env: dict[str, str]) -> None:
        from google.cloud import run_v2

        client = run_v2.JobsClient()
        name = f"projects/{self._project}/locations/{self._region}/jobs/{self._job}"
        overrides = run_v2.RunJobRequest.Overrides(
            container_overrides=[
                run_v2.RunJobRequest.Overrides.ContainerOverride(
                    env=[run_v2.EnvVar(name=k, value=v) for k, v in env.items()]
                )
            ]
        )
        client.run_job(
            request=run_v2.RunJobRequest(name=name, overrides=overrides)
        ).result()
