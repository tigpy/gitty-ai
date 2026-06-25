from typing import Dict, Any, List
from .base_agent import BaseAgent, AgentResult

class ImpactAgent(BaseAgent):
    @property
    def agent_name(self) -> str:
        return "ImpactAgent"

    def analyze(self, repository_id: str, context: Dict[str, Any]) -> AgentResult:
        from services.graph_service.infrastructure.repositories.graph_repository_factory import get_graph_repository
        from services.graph_service.application.dependency_traversal_service import DependencyTraversalService
        
        try:
            repo = get_graph_repository()
            traversal = DependencyTraversalService(repo)
            
            target = context.get("changed_component")
            if not target:
                # Fallback to the first File node found in the repository
                nodes = repo.get_nodes_by_repository(repository_id)
                file_node = next((n for n in nodes if n.get("type") == "File"), None)
                target = file_node["id"] if file_node else None
                
            if not target:
                return AgentResult(
                    agent_name=self.agent_name,
                    score=100.0,
                    findings=["No files found to analyze dependency impact."],
                    recommendations=["Index files in the repository first."],
                    severity="LOW",
                    metadata={"affected_files": [], "affected_functions": [], "risk_level": "LOW"}
                )

            # Retrieve target details
            target_node = repo.get_node(target)
            target_name = target_node.get("name") if target_node else target
            
            # Find files that depend on target transitively (inbound dependencies / callers)
            visited = {target}
            queue = [target]
            affected_files = []
            
            while queue:
                curr = queue.pop(0)
                inbound = repo.get_inbound_edges(curr)
                for edge in inbound:
                    src = edge["source_node"]
                    edge_type = edge["relationship_type"]
                    
                    if edge_type in ("IMPORTS", "DEPENDS", "CALLS"):
                        if src not in visited:
                            visited.add(src)
                            queue.append(src)
                            src_node = repo.get_node(src)
                            if src_node:
                                if src_node.get("type") == "File":
                                    affected_files.append(src_node.get("path"))
                                elif src_node.get("type") == "Function":
                                    affected_files.append(src_node.get("name"))

            # Filter unique affected files & functions
            nodes = repo.get_nodes_by_repository(repository_id)
            all_file_paths = {n.get("path") for n in nodes if n.get("type") == "File" and n.get("path")}
            all_func_names = {n.get("name") for n in nodes if n.get("type") == "Function" and n.get("name")}
            
            aff_files = sorted(list(set([x for x in affected_files if x in all_file_paths])))
            aff_funcs = sorted(list(set([x for x in affected_files if x in all_func_names])))
            
            risk_level = "HIGH" if len(aff_files) > 5 else "MEDIUM" if len(aff_files) > 0 else "LOW"
            score = max(0.0, 100.0 - len(aff_files) * 5)
            
            findings = [f"Changed component {target_name} affects {len(aff_files)} files transitively."]
            recommendations = [f"Run automated regression tests covering: {', '.join(aff_files[:3])}"] if aff_files else ["No downstream impact identified."]
            
            return AgentResult(
                agent_name=self.agent_name,
                score=score,
                findings=findings,
                recommendations=recommendations,
                severity=risk_level,
                metadata={
                    "affected_files": aff_files,
                    "affected_functions": aff_funcs,
                    "risk_level": risk_level
                }
            )
        except Exception as e:
            return AgentResult(
                agent_name=self.agent_name,
                score=100.0,
                findings=[f"Failed to analyze dependency impact: {str(e)}"],
                recommendations=["Ensure the repository structure is correctly parsed."],
                severity="INFO",
                metadata={"error": str(e), "status": "failed", "affected_files": [], "affected_functions": [], "risk_level": "LOW"}
            )
