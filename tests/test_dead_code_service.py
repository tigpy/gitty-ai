import pytest
from typing import Any
import hashlib
import os
import sqlite3
from unittest.mock import MagicMock, patch
from libs.config import get_settings
from libs.events.schemas import DeadCodeDetectedV1, DeadModuleDetectedV1, DeadCodeAnalysisCompletedV1
from services.graph_service.infrastructure.repositories.sqlite_graph_repository import SQLiteGraphRepository
from services.graph_service.application.graph_builder import GraphBuilder
from services.parser_service.application.symbol_table import SymbolTable
from services.dead_code_service.application.dead_code_detector import DeadCodeDetectionService, ENTRYPOINT_FILES
from libs.models.ir import IRModule, IRImport, IRClass, IRFunction, IRCall
from apps.worker.worker_app import detect_dead_code

class MockEventBus:
    def __init__(self):
        self.published = []

    def publish(self, topic: str, event: Any) -> None:
        self.published.append((topic, event))

    def subscribe(self, queue_name: str, topic: str, handler: Any) -> None:
        pass

    def start_consuming(self) -> None:
        pass

@pytest.fixture
def mock_repo_graph(tmp_path):
    db_path = str(tmp_path / "test_dead_code_gitty_graph.db")
    repo = SQLiteGraphRepository(db_path=db_path)
    symbol_table = SymbolTable()
    builder = GraphBuilder(repository=repo, symbol_table=symbol_table)
    
    repo_id = "test-dead-code-repo"
    
    # Let's build a repository with various test cases:
    # 1. main.py (entrypoint file)
    #    - contains func_main (entrypoint function)
    #    - calls func_used
    # 2. utils.py
    #    - contains func_used (referenced)
    #    - contains func_unused (dead function)
    #    - contains __init__ (dunder, ignored)
    #    - contains func_route (decorated with @app.get, ignored)
    # 3. services.py
    #    - contains ClassUsed (instantiated by func_used)
    #    - contains ClassOrphan (no references, dead class)
    #    - contains ClassBase (inherited by ClassUsed, referenced)
    # 4. dead_module_file.py (isolated file, dead file / dead module root)
    #    - contains func_dead_module (dead module function)
    
    # main.py
    mod_main = IRModule(
        file_path="main.py",
        language="python",
        imports=[
            IRImport(name="func_used", module="utils", line_number=1)
        ],
        functions=[
            IRFunction(
                name="func_main",
                start_line=3,
                end_line=7,
                calls=[
                    IRCall(name="func_used", line_number=5)
                ]
            )
        ]
    )

    # utils.py
    mod_utils = IRModule(
        file_path="utils.py",
        language="python",
        imports=[
            IRImport(name="ClassUsed", module="services", line_number=1)
        ],
        functions=[
            IRFunction(
                name="func_used",
                start_line=3,
                end_line=8,
                calls=[
                    IRCall(name="ClassUsed", line_number=6)
                ]
            ),
            IRFunction(
                name="func_unused",
                start_line=10,
                end_line=12,
                calls=[]
            ),
            IRFunction(
                name="__init__",
                start_line=14,
                end_line=15,
                calls=[]
            ),
            IRFunction(
                name="func_route",
                start_line=17,
                end_line=20,
                decorators=["@app.get('/route')"],
                calls=[]
            )
        ]
    )

    # services.py
    mod_services = IRModule(
        file_path="services.py",
        language="python",
        classes=[
            IRClass(
                name="ClassBase",
                bases=[],
                start_line=1,
                end_line=4,
                methods=[]
            ),
            IRClass(
                name="ClassUsed",
                bases=["ClassBase"],
                start_line=6,
                end_line=12,
                methods=[
                    IRFunction(
                        name="method_used",
                        start_line=8,
                        end_line=10,
                        is_method=True,
                        class_context="ClassUsed"
                    )
                ]
            ),
            IRClass(
                name="ClassOrphan",
                bases=[],
                start_line=14,
                end_line=18,
                methods=[]
            )
        ]
    )

    # dead_module_file.py
    mod_dead = IRModule(
        file_path="dead_module_file.py",
        language="python",
        functions=[
            IRFunction(
                name="func_dead_module",
                start_line=2,
                end_line=5,
                calls=[]
            )
        ]
    )

    builder.build_graph(
        repo_id=repo_id,
        repo_name="test_dead_code_repo",
        repo_path="/path/to/test_dead_code_repo",
        modules=[mod_main, mod_utils, mod_services, mod_dead]
    )

    # Let's add line count metadata manually to simulate parser line counts
    # main.py: 10 lines
    # utils.py: 30 lines
    # services.py: 600 lines (trigger LARGE_MODULE score deduction)
    with repo._get_connection() as conn:
        cursor = conn.cursor()
        main_id = hashlib.sha256(f"{repo_id}:main.py".encode()).hexdigest()
        utils_id = hashlib.sha256(f"{repo_id}:utils.py".encode()).hexdigest()
        services_id = hashlib.sha256(f"{repo_id}:services.py".encode()).hexdigest()
        dead_id = hashlib.sha256(f"{repo_id}:dead_module_file.py".encode()).hexdigest()

        # Update metadata line_count
        cursor.execute("UPDATE nodes SET metadata = ? WHERE id = ?", ('{"line_count": 10}', main_id))
        cursor.execute("UPDATE nodes SET metadata = ? WHERE id = ?", ('{"line_count": 30}', utils_id))
        cursor.execute("UPDATE nodes SET metadata = ? WHERE id = ?", ('{"line_count": 600}', services_id)) # line_count 600 + funcs 0*5 + classes 3*10 = 630 (close to 750)
        # Let's make services.py size score > 750 to trigger LARGE_MODULE
        cursor.execute("UPDATE nodes SET metadata = ? WHERE id = ?", ('{"line_count": 730}', services_id)) # 730 + 0*5 + 3*10 = 760 (triggers)
        cursor.execute("UPDATE nodes SET metadata = ? WHERE id = ?", ('{"line_count": 5}', dead_id))
        conn.commit()

    yield repo, repo_id

def test_unused_functions_detection(mock_repo_graph):
    repo, repo_id = mock_repo_graph
    detector = DeadCodeDetectionService(repo)
    nodes = repo.get_nodes_by_repository(repo_id)

    dead_funcs = detector.detect_unused_functions(nodes, repo_id)
    dead_func_names = {f["name"] for f in dead_funcs}

    assert "func_unused" in dead_func_names
    assert "func_used" not in dead_func_names
    assert "func_main" not in dead_func_names # entrypoint file main.py skipped
    assert "__init__" not in dead_func_names  # dunder skipped
    assert "func_route" not in dead_func_names # decorated route skipped

def test_orphan_classes_detection(mock_repo_graph):
    repo, repo_id = mock_repo_graph
    detector = DeadCodeDetectionService(repo)
    nodes = repo.get_nodes_by_repository(repo_id)

    dead_classes = detector.detect_orphan_classes(nodes, repo_id)
    dead_class_names = {c["name"] for c in dead_classes}

    assert "ClassOrphan" in dead_class_names
    assert "ClassUsed" not in dead_class_names # instantiated in utils.py
    assert "ClassBase" not in dead_class_names # inherited by ClassUsed

def test_unreferenced_files_detection(mock_repo_graph):
    repo, repo_id = mock_repo_graph
    detector = DeadCodeDetectionService(repo)
    nodes = repo.get_nodes_by_repository(repo_id)

    # Reconstruct inbound dependencies
    file_nodes = [n for n in nodes if n["type"] == "File"]
    file_ids = [f["id"] for f in file_nodes]
    inbound_deps = {fid: set() for fid in file_ids}
    
    for f in file_nodes:
        fid = f["id"]
        file_deps = detector.dep_service.get_file_dependencies(fid, repo_id)
        for dep in file_deps:
            if dep in inbound_deps:
                inbound_deps[dep].add(fid)

    dead_files = detector.detect_unreferenced_files(nodes, repo_id, inbound_deps)
    dead_file_names = {f["name"] for f in dead_files}

    assert "dead_module_file.py" in dead_file_names
    assert "main.py" not in dead_file_names # entrypoint
    assert "utils.py" not in dead_file_names # imported by main.py

def test_dead_modules_detection(mock_repo_graph):
    repo, repo_id = mock_repo_graph
    detector = DeadCodeDetectionService(repo)
    nodes = repo.get_nodes_by_repository(repo_id)

    file_nodes = [n for n in nodes if n["type"] == "File"]
    file_ids = [f["id"] for f in file_nodes]
    deps = {}
    inbound_deps = {fid: set() for fid in file_ids}
    
    for f in file_nodes:
        fid = f["id"]
        file_deps = detector.dep_service.get_file_dependencies(fid, repo_id)
        deps[fid] = file_deps
        for dep in file_deps:
            if dep in inbound_deps:
                inbound_deps[dep].add(fid)

    dead_modules = detector.detect_dead_modules(nodes, repo_id, deps, inbound_deps)
    assert len(dead_modules) == 1
    assert "dead_module_file.py" in dead_modules[0]

def test_architecture_smell_detection(mock_repo_graph):
    repo, repo_id = mock_repo_graph
    detector = DeadCodeDetectionService(repo)
    nodes = repo.get_nodes_by_repository(repo_id)

    smells = detector.detect_architecture_smells(nodes, repo_id)
    smell_types = {s["type"] for s in smells}

    # Verify LARGE_MODULE smell is raised for services.py (line score 760 > 750)
    assert "LARGE_MODULE" in smell_types
    large_module_smell = next(s for s in smells if s["type"] == "LARGE_MODULE")
    assert large_module_smell["entity_name"] == "services.py"

def test_confidence_and_health_calculations(mock_repo_graph):
    repo, repo_id = mock_repo_graph
    detector = DeadCodeDetectionService(repo)
    
    # 1. Test Confidence Level mappings
    conf_high = detector.calculate_confidence("Function", "services.py", {"decorators": []})
    assert conf_high["confidence_score"] == 0.95
    assert conf_high["confidence_level"] == "HIGH"

    conf_medium = detector.calculate_confidence("Function", "services.py", {"decorators": ["@route"]})
    assert conf_medium["confidence_score"] == 0.80
    assert conf_medium["confidence_level"] == "MEDIUM"

    conf_low = detector.calculate_confidence("Function", "test_services.py", {"decorators": []})
    assert conf_low["confidence_score"] == 0.50
    assert conf_low["confidence_level"] == "LOW"

    # 2. Test Health Score calculations
    report = detector.run_analysis(repo_id)
    assert report.repository_health < 100
    assert report.repository_health > 0
    # Health score starting at 100
    # dead_functions = 1 ("func_unused") -> -2
    # dead_classes = 1 ("ClassOrphan") -> -5
    # dead_files = 1 ("dead_module_file.py") -> -10
    # dead_modules = 1 ("dead_module_file.py" components) -> -10
    # LARGE_MODULE smell = 1 ("services.py") -> -5
    # Expected: 100 - 2 - 5 - 10 - 10 - 5 = 68
    assert report.repository_health == 68

def test_dead_code_detector_publish_events(mock_repo_graph):
    repo, repo_id = mock_repo_graph
    publisher = MockEventBus()
    detector = DeadCodeDetectionService(repo, publisher=publisher)

    report = detector.run_analysis(repo_id)

    # Verify event types published
    topics = [t for t, e in publisher.published]
    assert "dead_code.detected" in topics
    assert "dead_code.module_detected" in topics
    assert "dead_code.analysis_completed" in topics

    # Verify completion event metadata
    comp_event = next(e for t, e in publisher.published if t == "dead_code.analysis_completed")
    assert comp_event.repository_id == repo_id
    assert comp_event.repository_health == 68
    assert comp_event.summary["dead_functions"] == 1
    assert comp_event.summary["dead_classes"] == 1
    assert comp_event.summary["dead_files"] == 1
    assert comp_event.summary["dead_modules"] == 1

@patch("apps.worker.worker_app.analyze_repository_security")
@patch("apps.worker.worker_app.RabbitMQPublisher")
def test_worker_detect_dead_code_task(mock_publisher_cls, mock_sec_analysis, mock_repo_graph, tmp_path):
    repo, repo_id = mock_repo_graph
    settings = get_settings()
    
    mock_publisher = MagicMock()
    mock_publisher_cls.return_value = mock_publisher

    original_db = settings.SQLITE_DB_PATH
    settings.SQLITE_DB_PATH = repo.db_path

    try:
        res = detect_dead_code(repo_id)
        assert res["status"] == "completed"
        assert res["repository_id"] == repo_id
        assert res["repository_health"] == 68
        assert res["summary"]["dead_functions"] == 1
        assert res["summary"]["dead_classes"] == 1
    finally:
        settings.SQLITE_DB_PATH = original_db
