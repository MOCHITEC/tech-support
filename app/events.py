"""イベント発行の seam。

ローカル/テストは NullPublisher(何もしない)、本番は Pub/Sub に発行する
PubSubPublisher。環境変数 EVENTS_TOPIC が設定されていれば本番用を選ぶ。
"""
import json
import os
from typing import Protocol


class Publisher(Protocol):
    def publish_ticket_created(self, ticket_id: int) -> None: ...


class NullPublisher:
    """発行を行わない(ローカル/テスト用の既定)。"""

    def publish_ticket_created(self, ticket_id: int) -> None:
        pass


class PubSubPublisher:
    """Pub/Sub トピックに ticket イベントを発行する。"""

    def __init__(self, topic: str, project_id: str) -> None:
        from google.cloud import pubsub_v1

        self._client = pubsub_v1.PublisherClient()
        self._topic_path = self._client.topic_path(project_id, topic)

    def publish_ticket_created(self, ticket_id: int) -> None:
        data = json.dumps({"ticket_id": ticket_id}).encode("utf-8")
        self._client.publish(self._topic_path, data=data).result()


def default_publisher() -> Publisher:
    topic = os.environ.get("EVENTS_TOPIC")
    if not topic:
        return NullPublisher()

    project_id = os.environ.get("GOOGLE_CLOUD_PROJECT")
    if not project_id:
        import google.auth

        _, project_id = google.auth.default()
    return PubSubPublisher(topic, project_id)
