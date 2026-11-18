def test_health_and_queues(api):
    assert api.client.get("/api/health").json()["status"] == "ok"
    for q in ("all", "urgent", "overdue", "rejected", "unowned", "escalated"):
        r = api.get("coordinator_auh", f"/api/cases?queue={q}")
        assert r.status_code == 200, r.text
        print(q, r.json()["total"])
