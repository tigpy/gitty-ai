import pytest
import sqlite3
from typing import List, Dict, Any
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from services.graph_service.infrastructure.repositories.sqlite_graph_repository import SQLiteGraphRepository
from services.graph_service.application.dependency_traversal_service import DependencyTraversalService
from services.dead_code_service.application.dead_code_detector import DeadCodeDetectionService
from services.graph_service.application.graph_application_service import GraphApplicationService
from services.security_service.application.dependency_scanner import (
    query_osv_batch,
    query_osv,
    scan_dependencies,
    Dependency
)
from app.main import app

class QueryCountCursor:
    def __init__(self, real_cursor, tracker):
        self._real_cursor = real_cursor
        self._tracker = tracker

    def execute(self, sql, params=()):
        self._tracker["count"] += 1
        self._tracker["queries"].append((sql, params))
        return self._real_cursor.execute(sql, params)

    def executemany(self, sql, seq_of_params):
        self._tracker["count"] += 1
        self._tracker["queries"].append((sql, seq_of_params))
        return self._real_cursor.executemany(sql, seq_of_params)

    def fetchone(self):
        return self._real_cursor.fetchone()

    def fetchall(self):
        return self._real_cursor.fetchall()

    def __getattr__(self, name):
        return getattr(self._real_cursor, name)

class QueryCountConnection:
    def __init__(self, real_conn, tracker):
        self._real_conn = real_conn
        self._tracker = tracker

    def cursor(self):
        return QueryCountCursor(self._real_conn.cursor(), self._tracker)

    def commit(self):
        return self._real_conn.commit()

    def rollback(self):
        return self._real_conn.rollback()

    def close(self):
        return self._real_conn.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            self.rollback()
        else:
            self.commit()
        self.close()

    def __getattr__(self, name):
        return getattr(self._real_conn, name)

def get_instrumented_repo(db_path: str, tracker: dict):
    repo = SQLiteGraphRepository(db_path=db_path)
    real_create_conn = repo.connection_factory.create_connection

    def instrumented_create_conn():
        return QueryCountConnection(real_create_conn(), tracker)

    repo.connection_factory.create_connection = instrumented_create_conn
    return repo


@pytest.fixture
def populated_repo(tmp_path):
    db_path = str(tmp_path / "perf_test.db")
    repo = SQLiteGraphRepository(db_path=db_path)
    repo_id = "test-repo-1"
    repo.save_repository(repo_id, "test-repo", "/mock/path", "python", "2026-09-23", "hash1")

    # Add 20 file nodes
    for i in range(20):
        fid = f"file_{i}"
        repo.add_node(fid, "File", {"name": f"mod_{i}.py", "path": f"src/mod_{i}.py"})
        repo.add_edge(repo_id, fid, "CONTAINS", {})

        # Each file has an import node
        imp_id = f"imp_{i}"
        target_mod = (i + 1) % 20
        repo.add_node(imp_id, "Import", {"name": f"src.mod_{target_mod}"})
        repo.add_edge(fid, imp_id, "IMPORTS", {})

        # Each file has 2 functions
        for f in range(2):
            func_id = f"func_{i}_{f}"
            repo.add_node(func_id, "Function", {"name": f"do_thing_{f}", "path": f"src/mod_{i}.py"})
            repo.add_edge(fid, func_id, "CONTAINS", {})

            # Each function has a call
            call_id = f"call_{i}_{f}"
            target_func = f"func_{target_mod}_{f}"
            repo.add_node(call_id, "Call", {"name": f"do_thing_{f}", "path": f"src/mod_{i}.py"})
            repo.add_edge(func_id, call_id, "CALLS", {})
            repo.add_edge(call_id, target_func, "BELONGS_TO", {})

        # Each file has a class
        cls_id = f"cls_{i}"
        repo.add_node(cls_id, "Class", {"name": f"Class_{i}", "path": f"src/mod_{i}.py"})
        repo.add_edge(fid, cls_id, "CONTAINS", {})

    return db_path, repo_id


def test_get_nodes_by_repository_query_bounded(populated_repo):
    db_path, repo_id = populated_repo
    tracker = {"count": 0, "queries": []}
    repo = get_instrumented_repo(db_path, tracker)

    nodes = repo.get_nodes_by_repository(repo_id)
    assert len(nodes) > 50

    # For ~100 nodes across 4 BFS depths, query count must be bounded by depth levels, NOT by node count.
    # Previous implementation executed 1 query per node (>100 queries).
    assert tracker["count"] < 10, f"Expected < 10 queries, got {tracker['count']}"


def test_get_all_file_dependencies_query_bounded(populated_repo):
    db_path, repo_id = populated_repo
    tracker = {"count": 0, "queries": []}
    repo = get_instrumented_repo(db_path, tracker)
    dep_service = DependencyTraversalService(repo)

    all_deps = dep_service.get_all_file_dependencies(repo_id)
    assert len(all_deps) == 20

    # Verify cyclic relationship mod_i -> mod_{i+1} was correctly resolved
    for i in range(20):
        fid = f"file_{i}"
        expected_target = f"file_{(i + 1) % 20}"
        assert expected_target in all_deps[fid]

    # Pre-fetching nodes and IMPORTS edges must take bounded queries, NOT 20 * 100 queries!
    assert tracker["count"] < 15, f"Expected < 15 queries, got {tracker['count']}"


def test_build_called_function_ids_batched(populated_repo):
    db_path, repo_id = populated_repo
    tracker = {"count": 0, "queries": []}
    repo = get_instrumented_repo(db_path, tracker)
    detector = DeadCodeDetectionService(repo)

    nodes = repo.get_nodes_by_repository(repo_id)
    tracker["count"] = 0  # reset after node fetch

    called = detector._build_called_function_ids(nodes)
    assert len(called) > 0

    # With 40 calls, previously executed 40 individual queries.
    # Batched implementation executes at most 2 queries.
    assert tracker["count"] <= 2, f"Expected <= 2 queries, got {tracker['count']}"


def test_architecture_degree_aggregation_batched(populated_repo):
    db_path, repo_id = populated_repo
    tracker = {"count": 0, "queries": []}
    repo = get_instrumented_repo(db_path, tracker)
    detector = DeadCodeDetectionService(repo)

    nodes = repo.get_nodes_by_repository(repo_id)
    tracker["count"] = 0

    smells = detector.detect_architecture_smells(nodes, repo_id)
    assert isinstance(smells, list)

    # For 60+ File/Class/Function entities, previously executed 120+ queries.
    # Degree aggregation and SCC execute in bounded queries (< 12 total, down from 120+).
    assert tracker["count"] < 12, f"Expected < 12 queries for smell detection, got {tracker['count']}"


def test_get_repository_graph_contains_real_edges_and_no_n_plus_one(populated_repo):
    db_path, repo_id = populated_repo
    tracker = {"count": 0, "queries": []}
    repo = get_instrumented_repo(db_path, tracker)
    service = GraphApplicationService(repo)

    graph = service.get_repository_graph(repo_id)
    assert len(graph.nodes) > 50
    assert len(graph.edges) > 50, "Graph must contain real edges!"

    # Verify DEPENDS relationships exist between files
    depends_edges = [e for e in graph.edges if e.relationship == "DEPENDS"]
    assert len(depends_edges) == 20

    # The entire get_repository_graph should complete with bounded queries
    assert tracker["count"] < 35, f"Expected < 35 queries, got {tracker['count']}"


def test_osv_batch_parsing_and_fallback():
    # 1. Test batch query parsing
    mock_payload = {
        "results": [
            {"vulns": [{"id": "GHSA-1234", "details": "Critical issue"}]},
            {"vulns": []}
        ]
    }

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = mock_payload

    with patch("httpx.post", return_value=mock_resp):
        status, results, err = query_osv_batch([
            {"package": {"name": "pkg-a", "ecosystem": "npm"}, "version": "1.0.0"},
            {"package": {"name": "pkg-b", "ecosystem": "npm"}, "version": "2.0.0"}
        ])
        assert status == "succeeded"
        assert len(results) == 2
        assert len(results[0]) == 1
        assert results[0][0]["id"] == "GHSA-1234"
        assert len(results[1]) == 0
        assert err is None

    # 2. Test fallback when batch endpoint returns non-200
    fail_resp = MagicMock()
    fail_resp.status_code = 500

    single_resp = MagicMock()
    single_resp.status_code = 200
    single_resp.json.return_value = {"vulns": []}

    def mock_post(url, *args, **kwargs):
        if "querybatch" in url:
            return fail_resp
        return single_resp

    with patch("httpx.post", side_effect=mock_post):
        # query_osv_batch returns unavailable
        b_status, b_results, b_err = query_osv_batch([{"package": {"name": "p"}, "version": "1"}])
        assert b_status == "unavailable"

        # single query succeeds via fallback
        s_status, s_vulns, s_err = query_osv("p", "npm", "1")
        assert s_status == "succeeded"


def test_repository_status_persistence_and_api(tmp_path):
    db_path = str(tmp_path / "status_test.db")
    repo = SQLiteGraphRepository(db_path=db_path)
    repo_id = "repo-status-test"

    # Initial save with 'processing'
    repo.save_repository(repo_id, "status-repo", "/mock", "python", "2026-09-23", "hash1", status="processing")
    row = repo.get_repository(repo_id)
    assert row["status"] == "processing"

    # Update to 'completed'
    repo.update_repository_status(repo_id, "completed")
    row = repo.get_repository(repo_id)
    assert row["status"] == "completed"

    # Update to 'failed'
    repo.update_repository_status(repo_id, "failed")
    row = repo.get_repository(repo_id)
    assert row["status"] == "failed"


def test_api_status_endpoint():
    client = TestClient(app)
    # Validate non-existent repository returns unknown / 400 validation
    response = client.get("/api/v1/repositories/nonexistent-12345678/status")
    assert response.status_code == 200
    data = response.json()
    assert data["repository_id"] == "nonexistent-12345678"
    assert data["status"] in ("unknown", "failed", "completed")
