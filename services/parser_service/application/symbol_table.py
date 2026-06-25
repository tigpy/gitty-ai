from typing import Dict, Optional, Tuple

class SymbolTable:
    def __init__(self):
        # Maps local symbol name -> fully qualified name
        # e.g., 'UserService' -> 'user.service.UserService'
        self._symbols: Dict[str, str] = {}
        # Maps fully qualified name -> node ID
        self._fqn_to_node_id: Dict[str, str] = {}

    def register_symbol(self, local_name: str, fully_qualified_name: str) -> None:
        self._symbols[local_name] = fully_qualified_name

    def register_node_id(self, fqn: str, node_id: str) -> None:
        self._fqn_to_node_id[fqn] = node_id

    def get_node_id(self, fqn: str) -> Optional[str]:
        if fqn in self._fqn_to_node_id:
            return self._fqn_to_node_id[fqn]
        return None

    def resolve_symbol(self, local_name: str) -> Optional[str]:
        # Check direct match
        if local_name in self._symbols:
            return self._symbols[local_name]
            
        # Check sub-attributes e.g. 'user_service.login' -> local symbol is 'user_service'
        parts = local_name.split(".")
        first_part = parts[0]
        if first_part in self._symbols:
            resolved_parent = self._symbols[first_part]
            return ".".join([resolved_parent] + parts[1:])
            
        return None

    def clear(self) -> None:
        self._symbols.clear()
        self._fqn_to_node_id.clear()
