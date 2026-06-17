def test_create_reservation_via_api_appears_in_my_list(client):
    resp = client.post(
        "/reservations",
        data={"room_id": 1, "start": "2026-06-18T10:00", "end": "2026-06-18T11:00"},
        follow_redirects=True,
    )
    assert resp.status_code == 200

    my = client.get("/my")
    assert my.status_code == 200
    assert "会議室A" in my.text
