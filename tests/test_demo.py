from fastapi.testclient import TestClient

from app.main import app


def test_demo_serves_frontend_and_real_sample():
    client = TestClient(app)
    page = client.get("/demo")
    assert page.status_code == 200
    assert page.headers["content-type"].startswith("text/html")
    sample = client.get("/demo/sample")
    assert sample.status_code == 200
    assert sample.text.splitlines()[0].startswith("Username,Movie Name,Year,Rating10")


def test_openapi_keeps_demo_routes_out_of_integration_contract():
    paths = TestClient(app).get("/openapi.json").json()["paths"]
    assert "/upload" in paths
    assert "/recommend/{user_id}" in paths
    assert "/demo" not in paths
