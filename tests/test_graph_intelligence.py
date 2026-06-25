import pytest
import hashlib
from services.graph_service.infrastructure.repositories.sqlite_graph_repository import SQLiteGraphRepository
from services.graph_service.application.graph_builder import GraphBuilder
from services.parser_service.application.symbol_table import SymbolTable
from services.graph_service.application.graph_query_service import GraphQueryService
from services.graph_service.application.call_graph_service import CallGraphService
from services.graph_service.application.dependency_traversal_service import DependencyTraversalService
from services.impact_analysis_service.application.impact_analysis_service import ImpactAnalysisService
from libs.models.ir import IRModule, IRImport, IRClass, IRFunction, IRCall

@pytest.fixture
def repo_graph(tmp_path):
    db_path = str(tmp_path / "test_gitty_graph.db")
    repo = SQLiteGraphRepository(db_path=db_path)
    symbol_table = SymbolTable()
    builder = GraphBuilder(repository=repo, symbol_table=symbol_table)
    
    # We will build a small mock repository
    # f1.py: imports f2, defines func1 which calls func2
    # f2.py: imports f3, defines Class2(Class1), defines func2 which calls func3
    # f3.py: defines Class1, defines func3
    # f4.py: has unused import math
    repo_id = "test-repo"
    
    # f3.py
    f3_path = "f3.py"
    mod3 = IRModule(
        file_path=f3_path,
        language="python",
        imports=[],
        classes=[
            IRClass(name="Class1", bases=[], start_line=1, end_line=3)
        ],
        functions=[
            IRFunction(name="func3", parameters=[], start_line=5, end_line=7)
        ]
    )
    
    # f2.py
    f2_path = "f2.py"
    mod2 = IRModule(
        file_path=f2_path,
        language="python",
        imports=[
            IRImport(name="func3", module="f3", line_number=1)
        ],
        classes=[
            IRClass(name="Class2", bases=["Class1"], start_line=3, end_line=6)
        ],
        functions=[
            IRFunction(
                name="func2",
                parameters=[],
                start_line=8,
                end_line=12,
                calls=[
                    IRCall(name="func3", line_number=10)
                ]
            )
        ]
    )
    
    # f1.py
    f1_path = "f1.py"
    mod1 = IRModule(
        file_path=f1_path,
        language="python",
        imports=[
            IRImport(name="func2", module="f2", line_number=1)
        ],
        classes=[],
        functions=[
            IRFunction(
                name="func1",
                parameters=[],
                start_line=3,
                end_line=7,
                calls=[
                    IRCall(name="func2", line_number=5)
                ]
            )
        ]
    )
    
    # f4.py
    f4_path = "f4.py"
    mod4 = IRModule(
        file_path=f4_path,
        language="python",
        imports=[
            IRImport(name="math", alias="m", line_number=1)
        ],
        classes=[],
        functions=[]
    )
    
    builder.build_graph(
        repo_id=repo_id,
        repo_name="test_repo",
        repo_path="/path/to/test_repo",
        modules=[mod3, mod2, mod1, mod4]
    )
    
    yield repo, repo_id

def test_graph_query_service(repo_graph):
    repo, repo_id = repo_graph
    query_service = GraphQueryService(repo)
    
    # 1. Test find_node
    repo_node = query_service.find_node(repo_id)
    assert repo_node is not None
    assert repo_node["name"] == "test_repo"
    
    # 2. Test find_neighbors
    neighbors = query_service.find_neighbors(repo_id, ["CONTAINS"])
    assert len(neighbors) == 4 # 4 files
    
    # 3. Test unused imports
    unused = query_service.get_unused_imports(repo_id)
    assert len(unused) == 1
    assert unused[0]["name"] == "math"
    
    # 4. Test largest modules
    largest = query_service.get_largest_modules(repo_id)
    assert len(largest) == 4
    
    # 5. Test hotspots
    hotspots = query_service.get_dependency_hotspots(repo_id)
    assert len(hotspots) >= 2 # f2 and f3 imported
    
    # 6. Test most called
    calls = query_service.get_most_called_functions(repo_id)
    assert len(calls) >= 2

    # 7. Test find_callers and find_callees
    f1_id = hashlib.sha256(f"{repo_id}:f1.py".encode()).hexdigest()
    func1_id = hashlib.sha256(f"{f1_id}:func1".encode()).hexdigest()
    f2_id = hashlib.sha256(f"{repo_id}:f2.py".encode()).hexdigest()
    func2_id = hashlib.sha256(f"{f2_id}:func2".encode()).hexdigest()

    callers = query_service.find_callers(func2_id)
    assert len(callers) > 0

    callees = query_service.find_callees(func1_id)
    assert len(callees) > 0

    # 8. Test find_path
    path = query_service.find_path(func1_id, func2_id)
    assert len(path) > 0

def test_call_graph_service(repo_graph):
    repo, repo_id = repo_graph
    call_service = CallGraphService(repo)
    
    # Compute function ids
    f1_id = hashlib.sha256(f"{repo_id}:f1.py".encode()).hexdigest()
    func1_id = hashlib.sha256(f"{f1_id}:func1".encode()).hexdigest()
    
    f2_id = hashlib.sha256(f"{repo_id}:f2.py".encode()).hexdigest()
    func2_id = hashlib.sha256(f"{f2_id}:func2".encode()).hexdigest()
    
    f3_id = hashlib.sha256(f"{repo_id}:f3.py".encode()).hexdigest()
    func3_id = hashlib.sha256(f"{f3_id}:func3".encode()).hexdigest()
    
    # 1. Test direct calls (get_called_functions)
    called = call_service.get_called_functions(func1_id)
    assert func2_id in called
    
    # 2. Test callers (get_calling_functions)
    callers = call_service.get_calling_functions(func2_id)
    assert func1_id in callers
    
    # 3. Test transitive callers
    transitive = call_service.find_all_reachable_callers(func3_id)
    assert func2_id in transitive
    assert func1_id in transitive
    
    # 4. Test call chain
    chain = call_service.find_call_chain(func1_id)
    assert chain["node"]["name"] == "func1"
    assert len(chain["calls"]) == 1
    assert chain["calls"][0]["node"]["name"] == "func2"

def test_dependency_traversal_service(repo_graph):
    repo, repo_id = repo_graph
    dep_service = DependencyTraversalService(repo)
    
    f1_id = hashlib.sha256(f"{repo_id}:f1.py".encode()).hexdigest()
    f2_id = hashlib.sha256(f"{repo_id}:f2.py".encode()).hexdigest()
    f3_id = hashlib.sha256(f"{repo_id}:f3.py".encode()).hexdigest()
    
    # 1. Test file dependencies
    deps = dep_service.get_file_dependencies(f1_id, repo_id)
    assert f2_id in deps
    
    # 2. Test dependency chain
    chain = dep_service.find_dependency_chain(f1_id, repo_id)
    assert f2_id in chain
    assert f3_id in chain
    
    # 3. Test topological sort
    sort_order = dep_service.topological_sort(repo_id)
    # f3 must come before f2, f2 before f1
    idx_f3 = sort_order.index(f3_id)
    idx_f2 = sort_order.index(f2_id)
    idx_f1 = sort_order.index(f1_id)
    assert idx_f3 < idx_f2 < idx_f1
    
    # 4. Test circular dependency (none present initially)
    cycles = dep_service.detect_cycles(repo_id)
    assert len(cycles) == 0

def test_dependency_circular_detection(tmp_path):
    # Setup circular dependency f1 -> f2 -> f1
    db_path = str(tmp_path / "test_gitty_graph_circular.db")
    repo = SQLiteGraphRepository(db_path=db_path)
    symbol_table = SymbolTable()
    builder = GraphBuilder(repository=repo, symbol_table=symbol_table)
    dep_service = DependencyTraversalService(repo)
    
    repo_id = "cycle-repo"
    
    mod1 = IRModule(
        file_path="f1.py",
        language="python",
        imports=[IRImport(name="func2", module="f2", line_number=1)]
    )
    mod2 = IRModule(
        file_path="f2.py",
        language="python",
        imports=[IRImport(name="func1", module="f1", line_number=1)]
    )
    
    builder.build_graph(
        repo_id=repo_id,
        repo_name="cycle_repo",
        repo_path="/path/to/cycle_repo",
        modules=[mod1, mod2]
    )
    
    cycles = dep_service.detect_cycles(repo_id)
    assert len(cycles) == 1
    assert len(cycles[0]) == 2
    
    with pytest.raises(ValueError):
        dep_service.topological_sort(repo_id)

def test_impact_analysis_service(repo_graph):
    repo, repo_id = repo_graph
    impact_service = ImpactAnalysisService(repo)
    
    # Function impact
    f2_id = hashlib.sha256(f"{repo_id}:f2.py".encode()).hexdigest()
    func2_id = hashlib.sha256(f"{f2_id}:func2".encode()).hexdigest()
    
    f1_id = hashlib.sha256(f"{repo_id}:f1.py".encode()).hexdigest()
    func1_id = hashlib.sha256(f"{f1_id}:func1".encode()).hexdigest()
    
    res = impact_service.calculate_blast_radius(func2_id, repo_id)
    assert res["changed_component"]["name"] == "func2"
    assert func1_id in res["impacted_components"]
    assert res["impacted_components"][func1_id]["distance"] == 1
    
    # Class inheritance impact
    f3_id = hashlib.sha256(f"{repo_id}:f3.py".encode()).hexdigest()
    class1_id = hashlib.sha256(f"{f3_id}:Class1".encode()).hexdigest()
    class2_id = hashlib.sha256(f"{f2_id}:Class2".encode()).hexdigest()
    
    res_class = impact_service.calculate_blast_radius(class1_id, repo_id)
    assert res_class["changed_component"]["name"] == "Class1"
    assert class2_id in res_class["impacted_components"]
    assert res_class["impacted_components"][class2_id]["distance"] == 1

    # Missing node impact
    res_none = impact_service.calculate_blast_radius("nonexistent-node-id", repo_id)
    assert res_none["changed_component"] is None
    assert res_none["total_impact_count"] == 0

    # File impact
    res_file = impact_service.calculate_blast_radius(f2_id, repo_id)
    assert res_file["changed_component"]["name"] == "f2.py"
    assert f1_id in res_file["impacted_components"]
    assert res_file["impacted_components"][f1_id]["distance"] == 1
