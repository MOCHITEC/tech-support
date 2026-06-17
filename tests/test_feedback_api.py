import re


def _csrf(client):
    html = client.get("/feedback").text
    m = re.search(r'name="csrf_token"\s+value="([^"]+)"', html)
    assert m, "CSRF トークンがフォームにありません"
    return m.group(1)


def test_feedback_creates_ticket_and_shows_in_status_page(client):
    token = _csrf(client)
    resp = client.post(
        "/feedback",
        data={
            "csrf_token": token,
            "title": "二重予約できてしまう",
            "steps": "1. 会議室Aを10-11時で予約\n2. 同じ枠でもう一度予約",
            "tobe": "2回目は重複エラーになる",
            "asis": "2回目も予約できる",
        },
        headers={"Origin": "http://testserver"},
        follow_redirects=True,
    )
    assert resp.status_code == 200

    page = client.get("/tickets")
    assert page.status_code == 200
    assert "二重予約できてしまう" in page.text
    assert "受付" in page.text


def test_feedback_rejected_without_csrf_token(client):
    resp = client.post(
        "/feedback",
        data={"title": "x", "steps": "x", "tobe": "x", "asis": "x"},
        headers={"Origin": "http://testserver"},
    )
    assert resp.status_code == 403


def test_feedback_rejected_with_foreign_origin(client):
    token = _csrf(client)
    resp = client.post(
        "/feedback",
        data={
            "csrf_token": token,
            "title": "x",
            "steps": "x",
            "tobe": "x",
            "asis": "x",
        },
        headers={"Origin": "http://evil.example.com"},
    )
    assert resp.status_code == 403
