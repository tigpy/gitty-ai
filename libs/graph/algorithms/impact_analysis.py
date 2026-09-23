from typing import Dict, List, Set, Any, Tuple
from .bfs import bfs_traverse

def calculate_blast_radius(
    changed_component: str,
    get_dependents: dict
) -> Dict[str, Any]:
    """
    Given a changed class/function/module name, trace all components dependent on it.
    Returns details on impacted items and severity/distance.
    """
    visited: Set[str] = {changed_component}
    queue: List[Tuple[str, int]] = [(changed_component, 0)] # (node, distance)
    impacted_nodes: Dict[str, int] = {}

    while queue:
        current, dist = queue.pop(0)
        if current != changed_component:
            impacted_nodes[current] = dist
            
        for dependent in get_dependents.get(current, []):
            if dependent not in visited:
                visited.add(dependent)
                queue.append((dependent, dist + 1))
                
    return {
        "changed_component": changed_component,
        "impacted_components": impacted_nodes,
        "total_impact_count": len(impacted_nodes)
    }
