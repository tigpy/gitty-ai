import os
import json
from typing import List, Dict, Any, Optional
from services.graph_service.infrastructure.repositories.sqlite_graph_repository import SQLiteGraphRepository
from services.graph_service.domain.entities.graph_entities import GraphNode, GraphEdge, RepositoryGraphResponse, NodeDetailsResponse
from services.dead_code_service.application.dead_code_detector import DeadCodeDetectionService
from services.security_service.application.security_analysis_service import SecurityAnalysisService
from services.graph_service.application.dependency_traversal_service import DependencyTraversalService

class GraphApplicationService:
    def __init__(self, repository: SQLiteGraphRepository):
        self.repository = repository
        self.dep_service = DependencyTraversalService(repository)
        self.dead_detector = DeadCodeDetectionService(repository)
        self.sec_service = SecurityAnalysisService(repository)

    def get_repositories(self) -> List[Dict[str, Any]]:
        return self.repository.list_repositories()

    def get_repository_graph(self, repo_id: str) -> RepositoryGraphResponse:
        nodes = self.repository.get_nodes_by_repository(repo_id)
        if not nodes:
            return RepositoryGraphResponse(nodes=[], edges=[])

        # Run dead code & security scan dynamically
        try:
            dead_report = self.dead_detector.run_analysis(repo_id)
            dead_funcs = {f["id"] for f in dead_report.dead_functions}
            dead_classes = {c["id"] for c in dead_report.dead_classes}
            dead_files = {fl["id"] for fl in dead_report.dead_files}
            
            dead_modules_files = set()
            for comp in dead_report.dead_modules:
                for path in comp:
                    dead_modules_files.add(path)
            
            dead_node_ids = dead_funcs | dead_classes | dead_files
            smell_node_ids = {s["entity_id"] for s in dead_report.architecture_smells}
        except Exception:
            dead_node_ids = set()
            dead_modules_files = set()
            smell_node_ids = set()

        try:
            sec_report = self.sec_service.run_security_scan(repo_id)
            findings = sec_report.findings
        except Exception:
            findings = []

        # Find File-level security findings to calculate file security scores
        file_findings_map = {}
        for f in findings:
            file_findings_map.setdefault(f.file_path, []).append(f)

        graph_nodes = []
        graph_edges = []

        # 1. Add Repository Node
        repo_db_node = next((n for n in nodes if n["type"] == "Repository"), None)
        if repo_db_node:
            graph_nodes.append(GraphNode(
                id=repo_db_node["id"],
                label=repo_db_node["name"],
                node_type="REPOSITORY",
                file_path=repo_db_node.get("path")
            ))

        # 2. Add File Nodes & contains edges
        file_nodes = [n for n in nodes if n["type"] == "File"]
        for f in file_nodes:
            fid = f["id"]
            fpath = f.get("path")
            
            # Determine dead code status
            is_dead = fid in dead_node_ids or fpath in dead_modules_files
            
            # Determine architecture smell
            is_smell = fid in smell_node_ids

            # Calculate security score (Base 100 with severity deductions)
            score = None
            f_findings = file_findings_map.get(fpath, [])
            if f_findings:
                score = 100
                for fnd in f_findings:
                    if fnd.severity == "CRITICAL":
                        score -= 40
                    elif fnd.severity == "HIGH":
                        score -= 25
                    elif fnd.severity == "MEDIUM":
                        score -= 15
                    elif fnd.severity == "LOW":
                        score -= 5
                score = max(0, score)

            graph_nodes.append(GraphNode(
                id=fid,
                label=f.get("name", "unknown"),
                node_type="FILE",
                file_path=fpath,
                security_score=score,
                dead_code=is_dead,
                architecture_smell=is_smell,
                metadata={"size": f.get("size", 0), "line_count": f.get("line_count", 0)}
            ))

            # CONTAINS link Repository -> File
            if repo_db_node:
                graph_edges.append(GraphEdge(
                    source=repo_db_node["id"],
                    target=fid,
                    relationship="CONTAINS"
                ))

            # DEPENDS links between Files
            file_deps = self.dep_service.get_file_dependencies(fid, repo_id)
            for dep in file_deps:
                # Add edge if dependency node is present
                graph_edges.append(GraphEdge(
                    source=fid,
                    target=dep,
                    relationship="DEPENDS"
                ))

        return RepositoryGraphResponse(nodes=graph_nodes, edges=graph_edges)

    def expand_node(self, node_id: str, repo_id: str) -> RepositoryGraphResponse:
        """Returns Class/Function child nodes contained in the file or class node."""
        outbound = self.repository.get_outbound_edges(node_id)
        child_ids = [e["target_node"] for e in outbound if e["relationship_type"] == "CONTAINS"]
        if not child_ids:
            return RepositoryGraphResponse(nodes=[], edges=[])

        # Run dead code & security scan dynamically for status checks
        try:
            dead_report = self.dead_detector.run_analysis(repo_id)
            dead_node_ids = ({f["id"] for f in dead_report.dead_functions} |
                             {c["id"] for c in dead_report.dead_classes} |
                             {fl["id"] for fl in dead_report.dead_files})
            smell_node_ids = {s["entity_id"] for s in dead_report.architecture_smells}
        except Exception:
            dead_node_ids = set()
            smell_node_ids = set()

        try:
            sec_report = self.sec_service.run_security_scan(repo_id)
            findings = sec_report.findings
        except Exception:
            findings = []

        graph_nodes = []
        graph_edges = []

        for cid in child_ids:
            child = self.repository.get_node(cid)
            if not child:
                continue
            
            cpath = child.get("path")
            cname = child.get("name")
            ctype = child["type"]

            # Highlight security findings directly on symbol
            score = None
            symbol_findings = []
            for f in findings:
                if f.file_path == cpath:
                    is_match = False
                    if getattr(f, "symbol_name", None) == cname:
                        is_match = True
                    elif f.line_number is not None and child.get("start_line") is not None and child.get("end_line") is not None:
                        if child["start_line"] <= f.line_number <= child["end_line"]:
                            is_match = True
                    if is_match:
                        symbol_findings.append(f)
            if symbol_findings:
                score = 100
                for fnd in symbol_findings:
                    if fnd.severity == "CRITICAL":
                        score -= 40
                    elif fnd.severity == "HIGH":
                        score -= 25
                    elif fnd.severity == "MEDIUM":
                        score -= 15
                    elif fnd.severity == "LOW":
                        score -= 5
                score = max(0, score)

            # Style code functions, classes, etc.
            graph_nodes.append(GraphNode(
                id=cid,
                label=cname,
                node_type=ctype.upper(),
                file_path=cpath,
                start_line=child.get("start_line"),
                end_line=child.get("end_line"),
                security_score=score,
                dead_code=cid in dead_node_ids,
                architecture_smell=cid in smell_node_ids,
                metadata=child
            ))

            # Add CONTAINS edge
            graph_edges.append(GraphEdge(
                source=node_id,
                target=cid,
                relationship="CONTAINS"
            ))

            # Pull calls relationships and inherits relationships if they link to nodes in our child list
            inbound_rels = self.repository.get_inbound_edges(cid)
            for r in inbound_rels:
                if r["source_node"] in child_ids:
                    graph_edges.append(GraphEdge(
                        source=r["source_node"],
                        target=cid,
                        relationship=r["relationship_type"]
                    ))

            outbound_rels = self.repository.get_outbound_edges(cid)
            for r in outbound_rels:
                if r["target_node"] in child_ids:
                    graph_edges.append(GraphEdge(
                        source=cid,
                        target=r["target_node"],
                        relationship=r["relationship_type"]
                    ))

        return RepositoryGraphResponse(nodes=graph_nodes, edges=graph_edges)

    def traverse_node(self, node_id: str) -> RepositoryGraphResponse:
        """Call Graph Overlay: Traverses CALLS paths starting from node_id."""
        visited = {node_id}
        queue = [node_id]
        
        nodes_list = []
        edges_list = []

        # Fetch starting node
        start_node = self.repository.get_node(node_id)
        if start_node:
            nodes_list.append(GraphNode(
                id=node_id,
                label=start_node.get("name", "unknown"),
                node_type=start_node["type"].upper(),
                file_path=start_node.get("path")
            ))

        while queue:
            curr_id = queue.pop(0)
            
            # outbound CALLS edges
            outbound = self.repository.get_outbound_edges(curr_id)
            calls_edges = [e for e in outbound if e["relationship_type"] in ("CALLS", "BELONGS_TO")]
            
            for edge in calls_edges:
                target_id = edge["target_node"]
                
                # Check target node
                target_node = self.repository.get_node(target_id)
                if not target_node:
                    continue

                edges_list.append(GraphEdge(
                    source=curr_id,
                    target=target_id,
                    relationship=edge["relationship_type"]
                ))

                if target_id not in visited:
                    visited.add(target_id)
                    queue.append(target_id)
                    
                    if target_node.get("type", "").lower() != "call":
                        nodes_list.append(GraphNode(
                            id=target_id,
                            label=target_node.get("name", "unknown"),
                            node_type=target_node["type"].upper(),
                            file_path=target_node.get("path"),
                            start_line=target_node.get("start_line"),
                            end_line=target_node.get("end_line"),
                            metadata=target_node
                        ))

        return RepositoryGraphResponse(nodes=nodes_list, edges=edges_list)

    def get_node_details(self, node_id: str, repo_id: str) -> NodeDetailsResponse:
        node = self.repository.get_node(node_id)
        if not node:
            raise ValueError(f"Node not found: {node_id}")

        npath = node.get("path")
        nname = node.get("name")
        ntype = node["type"]

        # Run dead code & security scan dynamically
        try:
            dead_report = self.dead_detector.run_analysis(repo_id)
            dead_node_ids = ({f["id"] for f in dead_report.dead_functions} |
                             {c["id"] for c in dead_report.dead_classes} |
                             {fl["id"] for fl in dead_report.dead_files})
            smell_node_ids = {s["entity_id"] for s in dead_report.architecture_smells}
        except Exception:
            dead_node_ids = set()
            smell_node_ids = set()

        try:
            sec_report = self.sec_service.run_security_scan(repo_id)
            findings = sec_report.findings
        except Exception:
            findings = []

        # Filter findings matching path & symbol name
        matched_findings = []
        for f in findings:
            if f.file_path == npath:
                is_match = False
                if ntype == "File":
                    is_match = True
                elif getattr(f, "symbol_name", None) == nname:
                    is_match = True
                elif f.line_number is not None and node.get("start_line") is not None and node.get("end_line") is not None:
                    if node["start_line"] <= f.line_number <= node["end_line"]:
                        is_match = True
                
                if is_match:
                    matched_findings.append({
                        "id": f.id,
                        "rule_id": f.rule_id,
                        "severity": f.severity,
                        "description": f.description,
                        "line_number": f.line_number
                    })

        return NodeDetailsResponse(
            id=node_id,
            type=ntype.upper(),
            name=nname,
            file_path=npath,
            symbol_name=node.get("symbol_name"),
            start_line=node.get("start_line"),
            end_line=node.get("end_line"),
            security_findings=matched_findings,
            dead_code=node_id in dead_node_ids,
            architecture_smell=node_id in smell_node_ids,
            metadata=node
        )
