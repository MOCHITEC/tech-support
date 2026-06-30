"""フィードバック投稿時に Pub/Sub イベントを発行する(パイプライン起動の入口)。

publisher はフェイクに差し替え、作成された ticket の id が一度だけ発行されること、
作成に失敗した投稿(CSRF 不一致)では発行されないことを検証する。
"""
import re

from app.main import app, get_publisher


class FakePublisher:
    def __init__(self):
        self.published: list[int] = []

    def publish_ticket_created(self, ticket_id: int) -> None:
        self.published.append(ticket_id)


def _csrf(client):
    html = client.get("/feedback").text
    return re.search(r'name="csrf_token"\s+value="([^"]+)"', html).group(1)


def test_feedback_publishes_event_for_created_ticket(client):
    fake = FakePublisher()
    app.dependency_overrides[get_publisher] = lambda: fake

    token = _csrf(client)
    resp = client.post(
        "/feedback",
        data={
            "csrf_token": token,
            "title": "二重予約できてしまう",
            "steps": "1. 予約 2. 同じ枠で再予約",
            "tobe": "重複エラーになる",
            "asis": "両方成立する",
        },
        headers={"Origin": "http://testserver"},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert fake.published == [1]  # 新規 DB なので最初の ticket id は 1


def test_rejected_feedback_does_not_publish(client):
    fake = FakePublisher()
    app.dependency_overrides[get_publisher] = lambda: fake

    resp = client.post(
        "/feedback",
        data={"title": "x", "steps": "x", "tobe": "x", "asis": "x"},
        headers={"Origin": "http://testserver"},
    )
    assert resp.status_code == 403
    assert fake.published == []
