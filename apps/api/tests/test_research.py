from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def test_start_research() -> None:
    """Test starting a research workflow."""
    response = client.post(
        "/api/research/start",
        json={"query": "test research query"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "run_id" in data
    assert len(data["run_id"]) > 0


def test_get_research_status() -> None:
    """Test getting research status."""
    # Start a research run first
    start_response = client.post(
        "/api/research/start",
        json={"query": "test query"}
    )
    run_id = start_response.json()["run_id"]

    # Get status
    response = client.get(f"/api/research/status/{run_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["run_id"] == run_id
    assert data["status"] in ["running", "completed", "failed"]
    assert data["query"] == "test query"


def test_get_status_not_found() -> None:
    """Test getting status for non-existent run."""
    response = client.get("/api/research/status/nonexistent-id")
    assert response.status_code == 404


def test_stream_research_status() -> None:
    """Test SSE streaming endpoint."""
    # Start a research run first
    start_response = client.post(
        "/api/research/start",
        json={"query": "test query"}
    )
    run_id = start_response.json()["run_id"]

    # Test that the stream endpoint is accessible
    # Note: Full SSE testing would require more complex setup
    with client.stream("GET", f"/api/research/stream/{run_id}") as response:
        assert response.status_code == 200
        assert response.headers["content-type"] == "text/event-stream; charset=utf-8"
        # Read at least one chunk to verify streaming works
        next(response.iter_lines())
