import hashlib
import os
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Any, Set, Optional
from libs.config import get_settings
from libs.events.schemas import DeadCodeDetectedV1, DeadModuleDetectedV1, DeadCodeAnalysisCompletedV1
from libs.core.message_bus.interfaces.event_bus import IEventBus
from services.graph_service.domain.repositories.graph_repository import IGraphRepository
from services.graph_service.application.dependency_traversal_service import DependencyTraversalService
from ..domain.entities.dead_code_report import DeadCodeReport

ENTRYPOINT_FILES = {
    "main.py",
    "app.py",
    "manage.py",
    "__main__.py",
    "wsgi.py",
    "asgi.py",
    "cli.py",
    "run.py"
}

DUNDER_METHODS = {
    "__init__",
    "__str__",
    "__repr__",
    "__eq__",
    "__len__",
    "__getitem__",
    "__setitem__",
    "__delitem__",
    "__iter__",
    "__next__",
    "__call__",
    "__enter__",
    "__exit__",
    "__new__"
}

EXCLUDED_DECORATOR_SUBSTRINGS = {
    "route", "get", "post", "put", "delete", "patch", "options", "head",
    "task", "celery", "click", "command", "api", "health"
}

class DeadCodeDetectionService:
    def __init__(self, repository: Any, publisher: Optional[IEventBus] = None):
        self.repository = repository
        self.publisher = publisher
        self.dep_service = DependencyTraversalService(repository)
        self.settings = get_settings()

    def calculate_confidence(self, entity_type: str, path: str, properties: Dict[str, Any]) -> Dict[str, Any]:
        """Calculates a weighted confidence score and level for a dead code finding."""
        is_test_file = "test_" in path or "_test" in path or "/tests/" in path or "\\tests\\" in path
        
        if is_test_file:
            score = 0.50
        else:
            if entity_type == "Function":
                score = 0.80
                decorators = properties.get("decorators") or properties.get("metadata", {}).get("decorators", [])
                if not decorators:
                    score += 0.15
            elif entity_type == "Class":
                score = 0.85
                decorators = properties.get("decorators") or properties.get("metadata", {}).get("decorators", [])
                if not decorators:
                    score += 0.10
            elif entity_type == "File":
                score = 0.90
            else:
                score = 0.80

        score = round(min(score, 1.0), 2)
        if score >= 0.90:
            level = "HIGH"
        elif score >= 0.70:
            level = "MEDIUM"
        else:
            level = "LOW"

        return {"confidence_score": score, "confidence_level": level}

    def _build_called_function_ids(self, nodes: List[Dict[str, Any]]) -> set:
        """
        Builds the set of function node IDs that are referenced by at least one CallNode via
        a BELONGS_TO edge.  A function is "live" if any CallNode points to it.

        Graph shape written by GraphBuilder:
            FunctionNode --CALLS--> CallNode --BELONGS_TO--> target_func_id

        So we collect every *target_node* of a BELONGS_TO edge that originates from a CallNode.
        """
        call_node_ids = {n["id"] for n in nodes if n["type"] == "Call"}
        referenced: set = set()
        for cid in call_node_ids:
            for edge in self.repository.get_outbound_edges(cid):
                if edge["relationship_type"] == "BELONGS_TO":
                    referenced.add(edge["target_node"])
        return referenced

    def detect_unused_functions(self, nodes: List[Dict[str, Any]], repo_id: str) -> List[Dict[str, Any]]:
        """Identifies functions with zero inbound call references, excluding routes/tasks/dunders."""
        unused = []
        functions = [n for n in nodes if n["type"] == "Function"]

        # Pre-compute the set of function IDs that are called anywhere in the repo.
        # This is O(call_nodes) instead of O(functions * edges).
        called_ids = self._build_called_function_ids(nodes)

        for func in functions:
            func_name = func.get("name", "")
            func_id = func["id"]
            path = func.get("path", "")

            # Skip dunder methods
            if func_name in DUNDER_METHODS or (func_name.startswith("__") and func_name.endswith("__")):
                continue

            # Skip entrypoint file functions
            if os.path.basename(path) in ENTRYPOINT_FILES:
                continue

            # Skip common test methods
            if func_name.startswith("test_"):
                continue

            # Skip methods (functions inside classes)
            is_method = func.get("metadata", {}).get("is_method", False) or func.get("is_method", False)
            if is_method:
                continue

            # Check decorators
            decorators = func.get("metadata", {}).get("decorators", []) or func.get("decorators", [])
            is_excluded_decorator = False
            for dec in decorators:
                dec_lower = dec.lower()
                if any(sub in dec_lower for sub in EXCLUDED_DECORATOR_SUBSTRINGS):
                    is_excluded_decorator = True
                    break
            if is_excluded_decorator:
                continue

            # A function is considered live if any CallNode targets it via BELONGS_TO.
            # We use the pre-built called_ids set for O(1) lookup instead of per-node
            # inbound edge queries (which were incorrectly using BELONGS_TO before).
            if func_id not in called_ids:
                conf = self.calculate_confidence("Function", path, func)
                unused.append({
                    "id": func_id,
                    "name": func_name,
                    "path": path,
                    "confidence_score": conf["confidence_score"],
                    "confidence_level": conf["confidence_level"]
                })
        return unused

    def detect_orphan_classes(self, nodes: List[Dict[str, Any]], repo_id: str) -> List[Dict[str, Any]]:
        """Identifies classes with zero inbound INHERITS or CALLS (instantiation) references."""
        unused = []
        classes = [n for n in nodes if n["type"] == "Class"]

        for cls in classes:
            class_name = cls.get("name", "")
            class_id = cls["id"]
            path = cls.get("path", "")

            inbound = self.repository.get_inbound_edges(class_id)
            # A class is referenced if something inherits from it OR directly calls it
            # (instantiation shows up as a CALLS edge from a function to the class node).
            inherits_edges = [e for e in inbound if e["relationship_type"] == "INHERITS"]
            call_edges = [e for e in inbound if e["relationship_type"] == "CALLS"]

            if not inherits_edges and not call_edges:
                conf = self.calculate_confidence("Class", path, cls)
                unused.append({
                    "id": class_id,
                    "name": class_name,
                    "path": path,
                    "confidence_score": conf["confidence_score"],
                    "confidence_level": conf["confidence_level"]
                })
        return unused

    def detect_unreferenced_files(self, nodes: List[Dict[str, Any]], repo_id: str, inbound_deps: Dict[str, Set[str]]) -> List[Dict[str, Any]]:
        """Identifies files that are not imported by any other file, excluding ENTRYPOINT_FILES."""
        unused = []
        files = [n for n in nodes if n["type"] == "File"]

        for f in files:
            fid = f["id"]
            path = f.get("path", "")
            file_name = f.get("name", "")

            if file_name in ENTRYPOINT_FILES:
                continue

            # Check if this is a test file
            if file_name.startswith("test_") or file_name.endswith("_test.py") or "tests/" in path or "tests\\" in path:
                continue

            if len(inbound_deps.get(fid, set())) == 0:
                conf = self.calculate_confidence("File", path, f)
                unused.append({
                    "id": fid,
                    "name": file_name,
                    "path": path,
                    "confidence_score": conf["confidence_score"],
                    "confidence_level": conf["confidence_level"]
                })
        return unused

    def detect_dead_modules(self, nodes: List[Dict[str, Any]], repo_id: str, deps: Dict[str, List[str]], inbound_deps: Dict[str, Set[str]]) -> List[List[str]]:
        """Runs reachability analysis from repository entrypoint files to find completely unreachable subgraphs."""
        files = [n for n in nodes if n["type"] == "File"]
        file_ids = [f["id"] for f in files]
        id_to_path = {f["id"]: f["path"] for f in files}

        # 1. Identify roots (entry points or files with 0 inbound but >0 outbound dependencies)
        roots = []
        for f in files:
            fid = f["id"]
            file_name = f.get("name", "")
            path = f.get("path", "")
            
            # Skip test files when determining roots/dead modules to avoid skewing reachability
            if "test_" in file_name or "_test" in file_name or "tests/" in path or "tests\\" in path:
                continue

            if file_name in ENTRYPOINT_FILES:
                roots.append(fid)
            elif len(inbound_deps.get(fid, set())) == 0 and len(deps.get(fid, [])) > 0:
                roots.append(fid)

        # 2. Traverse reachable files from roots
        reachable = set()
        queue = list(roots)
        reachable.update(roots)

        while queue:
            curr = queue.pop(0)
            for neighbor in deps.get(curr, []):
                if neighbor not in reachable:
                    reachable.add(neighbor)
                    queue.append(neighbor)

        # 3. Anything else (not reachable) is unreachable
        unreachable = set()
        for fid in file_ids:
            path = id_to_path[fid]
            file_name = os.path.basename(path)
            
            # Skip test files and entrypoints
            if "test_" in file_name or "_test" in file_name or "tests/" in path or "tests\\" in path:
                continue
            if file_name in ENTRYPOINT_FILES:
                continue

            if fid not in reachable:
                unreachable.add(fid)

        # 4. Group unreachable files into disconnected components (subgraphs)
        visited = set()
        dead_components = []

        for u_id in unreachable:
            if u_id not in visited:
                component = []
                comp_queue = [u_id]
                visited.add(u_id)

                while comp_queue:
                    curr = comp_queue.pop(0)
                    component.append(id_to_path[curr])

                    # Get neighbors in unreachable set (both import and imported-by)
                    neighbors = set(deps.get(curr, [])) | inbound_deps.get(curr, set())
                    for n in neighbors:
                        if n in unreachable and n not in visited:
                            visited.add(n)
                            comp_queue.append(n)
                dead_components.append(component)

        return dead_components

    def detect_architecture_smells(self, nodes: List[Dict[str, Any]], repo_id: str) -> List[Dict[str, Any]]:
        """Scans for architectural smells including LARGE_MODULE, Circular Imports, and High Fan-in/out."""
        smells = []
        files = [n for n in nodes if n["type"] == "File"]

        # Load settings thresholds
        fan_in_threshold = self.settings.GITTY_SMELL_FAN_IN_THRESHOLD
        fan_out_threshold = self.settings.GITTY_SMELL_FAN_OUT_THRESHOLD
        size_threshold = self.settings.GITTY_SMELL_MODULE_SIZE_THRESHOLD

        # 1. LARGE_MODULE detection
        for f in files:
            fid = f["id"]
            path = f.get("path", "")
            
            line_count = f.get("line_count") or 0
            if not line_count:
                meta = f.get("metadata", {})
                if isinstance(meta, dict):
                    line_count = meta.get("line_count") or 0
                    
            # Count functions and classes in this file
            funcs_count = len([n for n in nodes if n["type"] == "Function" and (n.get("parent_id") == fid or n.get("metadata", {}).get("parent_id") == fid)])
            classes_count = len([n for n in nodes if n["type"] == "Class" and (n.get("file_id") == fid or n.get("metadata", {}).get("file_id") == fid)])

            module_size_score = line_count + (funcs_count * 5) + (classes_count * 10)
            if module_size_score > size_threshold:
                smells.append({
                    "type": "LARGE_MODULE",
                    "entity_id": fid,
                    "entity_name": f.get("name"),
                    "path": path,
                    "message": f"Module size score ({module_size_score}) exceeds threshold ({size_threshold}). Lines: {line_count}, Functions: {funcs_count}, Classes: {classes_count}."
                })

        # 2. CIRCULAR_DEPENDENCY detection
        sccs = self.dep_service.strongly_connected_components(repo_id)
        id_to_path = {n["id"]: n["path"] for n in nodes if n["type"] == "File"}
        for scc in sccs:
            if len(scc) > 1:
                paths = [id_to_path[node_id] for node_id in scc if node_id in id_to_path]
                smells.append({
                    "type": "CIRCULAR_DEPENDENCY",
                    "entity_id": scc[0],
                    "entity_name": "cycle",
                    "path": paths[0],
                    "message": f"Circular dependency cycle detected: {', '.join(paths)}"
                })

        # 3. HIGH_FAN_IN and HIGH_FAN_OUT detection
        for n in nodes:
            if n["type"] in ("File", "Class", "Function"):
                nid = n["id"]
                inbound_count = len(self.repository.get_inbound_edges(nid))
                outbound_count = len(self.repository.get_outbound_edges(nid))

                if inbound_count > fan_in_threshold:
                    smells.append({
                        "type": "HIGH_FAN_IN",
                        "entity_id": nid,
                        "entity_name": n.get("name"),
                        "path": n.get("path", ""),
                        "message": f"Entity has {inbound_count} inbound edges, exceeding threshold of {fan_in_threshold}."
                    })
                if outbound_count > fan_out_threshold:
                    smells.append({
                        "type": "HIGH_FAN_OUT",
                        "entity_id": nid,
                        "entity_name": n.get("name"),
                        "path": n.get("path", ""),
                        "message": f"Entity has {outbound_count} outbound edges, exceeding threshold of {fan_out_threshold}."
                    })

        return smells

    def calculate_health_score(self, report: DeadCodeReport) -> int:
        """Calculates a repository health score out of 100 with deductions."""
        score = 100
        
        # Deductions
        score -= len(report.dead_functions) * 2
        score -= len(report.dead_classes) * 5
        score -= len(report.dead_files) * 10
        
        # Dead module files count
        for mod in report.dead_modules:
            score -= len(mod) * 10

        # Architecture smells deductions
        for smell in report.architecture_smells:
            if smell["type"] == "CIRCULAR_DEPENDENCY":
                score -= 10
            elif smell["type"] == "LARGE_MODULE":
                score -= 5
            elif smell["type"] in ("HIGH_FAN_IN", "HIGH_FAN_OUT"):
                score -= 3

        return max(0, score)

    def _detect_unused_imports(self, nodes: List[Dict[str, Any]], repo_id: str) -> List[Dict[str, Any]]:
        """
        Detects unused imports by comparing Import nodes in each file against the
        call names recorded in that file's Call nodes.

        An import is considered used if its name (or alias) appears in at least one
        Call node path recorded under the same file.
        """
        unused = []

        # Build per-file call name set from Call nodes
        file_call_names: Dict[str, set] = {}
        for n in nodes:
            if n["type"] == "Call":
                path = n.get("path", "")
                call_name = n.get("name", "")
                if path and call_name:
                    # A call like "os.path.join" registers both "os" and "os.path" as used roots
                    parts = call_name.split(".")
                    for i in range(1, len(parts) + 1):
                        file_call_names.setdefault(path, set()).add(".".join(parts[:i]))

        # Walk Import nodes
        for n in nodes:
            if n["type"] != "Import":
                continue
            path = n.get("path", "")
            import_name = n.get("name", "")  # format: "module.name" or just "name"
            meta = n.get("metadata", {}) or {}
            alias = meta.get("alias") or None

            # The effective local name is the alias if present, otherwise the last segment
            local_name = alias if alias else import_name.split(".")[-1]
            root_module = import_name.split(".")[0] if import_name else ""

            call_names_in_file = file_call_names.get(path, set())

            is_used = (
                local_name in call_names_in_file
                or root_module in call_names_in_file
                or import_name in call_names_in_file
            )

            if not is_used:
                unused.append({
                    "id": n["id"],
                    "name": import_name,
                    "alias": alias,
                    "path": path,
                    "local_name": local_name,
                })

        return unused

    def run_analysis(self, repo_id: str) -> DeadCodeReport:
        """Runs the complete analysis, saves results, and broadcasts completed/detected events."""
        nodes = self.repository.get_nodes_by_repository(repo_id)
        repo_node = next((n for n in nodes if n["type"] == "Repository"), None)
        repo_name = repo_node.get("name", "unknown") if repo_node else "unknown"

        # Construct dependency maps for unreferenced files & dead modules
        file_nodes = [n for n in nodes if n["type"] == "File"]
        file_ids = [f["id"] for f in file_nodes]
        deps = {}
        inbound_deps = {fid: set() for fid in file_ids}
        
        for f in file_nodes:
            fid = f["id"]
            file_deps = self.dep_service.get_file_dependencies(fid, repo_id)
            deps[fid] = file_deps
            for dep in file_deps:
                if dep in inbound_deps:
                    inbound_deps[dep].add(fid)

        # 1. Run detections
        dead_files = self.detect_unreferenced_files(nodes, repo_id, inbound_deps)
        dead_modules = self.detect_dead_modules(nodes, repo_id, deps, inbound_deps)
        
        # Collect all dead paths to avoid duplicate count in unused functions/classes
        dead_paths = {f["path"] for f in dead_files}
        for mod in dead_modules:
            dead_paths.update(mod)

        dead_funcs = self.detect_unused_functions(nodes, repo_id)
        dead_classes = self.detect_orphan_classes(nodes, repo_id)

        # Filter out functions/classes that are inside dead files/modules to avoid duplicate penalties
        dead_funcs = [f for f in dead_funcs if f["path"] not in dead_paths]
        dead_classes = [c for c in dead_classes if c["path"] not in dead_paths]

        smells = self.detect_architecture_smells(nodes, repo_id)

        # Detect unused imports: walk Import nodes and check if any Function/Class in the
        # same file references the imported symbol name in a Call or Attribute access.
        unused_imports = self._detect_unused_imports(nodes, repo_id)

        # Calculate average confidence
        total_score = 0.0
        findings_count = len(dead_funcs) + len(dead_classes) + len(dead_files)
        for f in dead_funcs:
            total_score += f["confidence_score"]
        for c in dead_classes:
            total_score += c["confidence_score"]
        for fl in dead_files:
            total_score += fl["confidence_score"]
            
        avg_score = round(total_score / findings_count, 2) if findings_count > 0 else 1.0
        avg_level = "HIGH" if avg_score >= 0.90 else ("MEDIUM" if avg_score >= 0.70 else "LOW")

        # 2. Build Report
        report = DeadCodeReport(
            repository_id=repo_id,
            repository_name=repo_name,
            analysis_timestamp=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            summary={
                "dead_functions": len(dead_funcs),
                "dead_classes": len(dead_classes),
                "dead_files": len(dead_files),
                "unused_imports": len(unused_imports),
                "dead_modules": len(dead_modules),
                "architecture_smells": len(smells)
            },
            dead_functions=dead_funcs,
            dead_classes=dead_classes,
            dead_files=dead_files,
            unused_imports=unused_imports,
            dead_modules=dead_modules,
            architecture_smells=smells,
            confidence_score=avg_score,
            confidence_level=avg_level,
            repository_health=100
        )
        
        report.repository_health = self.calculate_health_score(report)

        # 3. Publish Events
        if self.publisher:
            # Publish DeadCodeDetectedV1 if dead code is found
            if findings_count > 0:
                dead_code_event = DeadCodeDetectedV1(
                    event_id=str(uuid.uuid4()) if hasattr(uuid, "uuid4") else repo_id + "_dead_code",
                    timestamp=datetime.now(timezone.utc),
                    repository_id=repo_id,
                    dead_functions=dead_funcs,
                    dead_classes=dead_classes,
                    dead_files=dead_files,
                    unused_imports=unused_imports,
                    confidence_score=avg_score,
                    confidence_level=avg_level
                )
                self.publisher.publish("dead_code.detected", dead_code_event)

            # Publish DeadModuleDetectedV1 for each dead module
            for comp in dead_modules:
                dead_mod_event = DeadModuleDetectedV1(
                    event_id=repo_id + "_dead_module",
                    timestamp=datetime.now(timezone.utc),
                    repository_id=repo_id,
                    dead_files=comp,
                    root_files=[] # reachability entry points are not directly applicable inside dead module
                )
                self.publisher.publish("dead_code.module_detected", dead_mod_event)

            # Publish DeadCodeAnalysisCompletedV1 always
            completion_event = DeadCodeAnalysisCompletedV1(
                event_id=repo_id + "_analysis_completed",
                timestamp=datetime.now(timezone.utc),
                repository_id=repo_id,
                analysis_timestamp=report.analysis_timestamp,
                repository_health=report.repository_health,
                summary=report.summary
            )
            self.publisher.publish("dead_code.analysis_completed", completion_event)

        return report
