from protocol import Result

def test_result_ok():
    r = Result(status="success", message="ok")
    assert r.ok is True

def test_result_error():
    r = Result(status="error", message="fail")
    assert r.ok is False

def test_result_to_json():
    import json
    r = Result(status="paused", message="waiting", workflow="test", details={"k": "v"})
    data = json.loads(r.to_json())
    assert data["status"] == "paused"
    assert data["workflow"] == "test"
