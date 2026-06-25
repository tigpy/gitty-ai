import hashlib
import uuid
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from .node_builder import NodeBuilder
from .relationship_builder import RelationshipBuilder
from services.graph_service.infrastructure.repositories.sqlite_graph_repository import SQLiteGraphRepository
from services.parser_service.application.symbol_table import SymbolTable
from libs.models.ir import IRModule
from libs.core.message_bus.interfaces.event_bus import IEventBus
from libs.events.schemas import GraphBuiltV1

class GraphBuilder:
    def __init__(self, repository: SQLiteGraphRepository, symbol_table: SymbolTable, publisher: Optional[IEventBus] = None):
        self.repository = repository
        self.symbol_table = symbol_table
        self.publisher = publisher
        self.nb = NodeBuilder()
        self.rb = RelationshipBuilder()

    def build_graph(
        self,
        repo_id: str,
        repo_name: str,
        repo_path: str,
        modules: List[IRModule]
    ) -> Dict[str, int]:
        start_time = datetime.now(timezone.utc)
        # 1. Save Repository metadata
        indexed_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        repo_hash = hashlib.sha256(f"{repo_name}:{repo_path}:{len(modules)}".encode()).hexdigest()
        self.repository.save_repository(
            repo_id, repo_name, repo_path, "python", indexed_at, repo_hash
        )

        # Build repository node
        repo_node = self.nb.build_repository_node(repo_id, repo_name, repo_path)
        self.repository.add_node(repo_node.id, repo_node.type, repo_node.model_dump())

        # 2. Register Symbols in SymbolTable
        self.symbol_table.clear()
        for mod in modules:
            file_id = self.nb.build_file_node(repo_id, mod.file_path).id
            
            # Register top-level functions
            for func in mod.functions:
                fully_qualified = f"{mod.file_path.replace('.py', '').replace('/', '.')}.{func.name}"
                self.symbol_table.register_symbol(func.name, fully_qualified)
                
                # Register node ID
                func_node_id = self.nb.build_function_node(file_id, func.name, mod.file_path).id
                self.symbol_table.register_node_id(fully_qualified, func_node_id)

            # Register classes & methods
            for cls in mod.classes:
                class_fq = f"{mod.file_path.replace('.py', '').replace('/', '.')}.{cls.name}"
                self.symbol_table.register_symbol(cls.name, class_fq)
                class_node_id = self.nb.build_class_node(file_id, cls.name, mod.file_path).id
                self.symbol_table.register_node_id(class_fq, class_node_id)
                
                for method in cls.methods:
                    method_fq = f"{class_fq}.{method.name}"
                    # Allow lookup by 'Class.method' or 'instance.method'
                    self.symbol_table.register_symbol(f"{cls.name}.{method.name}", method_fq)
                    
                    method_node_id = self.nb.build_function_node(class_node_id, method.name, mod.file_path).id
                    self.symbol_table.register_node_id(method_fq, method_node_id)

        # 3. Translate IR Modules to Nodes & Edges
        nodes_count = 1 # repo node
        edges_count = 0

        for mod in modules:
            file_node = self.nb.build_file_node(repo_id, mod.file_path)
            self.repository.add_node(file_node.id, file_node.type, file_node.model_dump())
            nodes_count += 1

            # Link Repo -> File
            rel = self.rb.build_relationship(repo_node.id, file_node.id, "CONTAINS")
            self.repository.add_edge(rel.source_node, rel.target_node, rel.relationship_type, rel.metadata)
            edges_count += 1

            # Build Import Nodes & Edges
            for imp in mod.imports:
                imp_name = f"{imp.module}.{imp.name}" if imp.module else imp.name
                imp_node = self.nb.build_import_node(file_node.id, imp_name, mod.file_path, {"alias": imp.alias})
                self.repository.add_node(imp_node.id, imp_node.type, imp_node.model_dump())
                nodes_count += 1

                # Link File -> Import
                rel = self.rb.build_relationship(file_node.id, imp_node.id, "IMPORTS")
                self.repository.add_edge(rel.source_node, rel.target_node, rel.relationship_type, rel.metadata)
                edges_count += 1

            # Build Top-level Functions
            for func in mod.functions:
                func_node = self.nb.build_function_node(file_node.id, func.name, mod.file_path, {
                    "parameters": func.parameters,
                    "return_type": func.return_type,
                    "start_line": func.start_line,
                    "end_line": func.end_line,
                    "decorators": func.decorators
                })
                self.repository.add_node(func_node.id, func_node.type, func_node.model_dump())
                nodes_count += 1

                # Link File -> Function
                rel = self.rb.build_relationship(file_node.id, func_node.id, "CONTAINS")
                self.repository.add_edge(rel.source_node, rel.target_node, rel.relationship_type, rel.metadata)
                edges_count += 1

                # Add Call Nodes
                edges_count += self._process_function_calls(func_node.id, func.calls, mod.file_path)

            # Build Classes
            for cls in mod.classes:
                class_node = self.nb.build_class_node(file_node.id, cls.name, mod.file_path, {
                    "bases": cls.bases,
                    "start_line": cls.start_line,
                    "end_line": cls.end_line,
                    "decorators": cls.decorators
                })
                self.repository.add_node(class_node.id, class_node.type, class_node.model_dump())
                nodes_count += 1

                # Link File -> Class
                rel = self.rb.build_relationship(file_node.id, class_node.id, "CONTAINS")
                self.repository.add_edge(rel.source_node, rel.target_node, rel.relationship_type, rel.metadata)
                edges_count += 1

                # Link Class inherits from base Class (if resolved)
                for base in cls.bases:
                    resolved_base = self.symbol_table.resolve_symbol(base) or base
                    # Target node is either registered in the symbol table or fallback to hash
                    target_base_id = self.symbol_table.get_node_id(resolved_base)
                    if not target_base_id:
                        target_base_id = hashlib.sha256(f"{file_node.id}:{base}".encode()).hexdigest()
                    rel = self.rb.build_relationship(class_node.id, target_base_id, "INHERITS", {"base_name": resolved_base})
                    self.repository.add_edge(rel.source_node, rel.target_node, rel.relationship_type, rel.metadata)
                    edges_count += 1

                # Build Class Methods
                for method in cls.methods:
                    method_node = self.nb.build_function_node(class_node.id, method.name, mod.file_path, {
                        "parameters": method.parameters,
                        "return_type": method.return_type,
                        "start_line": method.start_line,
                        "end_line": method.end_line,
                        "is_method": True,
                        "decorators": method.decorators
                    })
                    self.repository.add_node(method_node.id, method_node.type, method_node.model_dump())
                    nodes_count += 1

                    # Link Class -> Method
                    rel = self.rb.build_relationship(class_node.id, method_node.id, "CONTAINS")
                    self.repository.add_edge(rel.source_node, rel.target_node, rel.relationship_type, rel.metadata)
                    edges_count += 1

                    # Add Call Nodes
                    edges_count += self._process_function_calls(method_node.id, method.calls, mod.file_path)

        duration_ms = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)
        if self.publisher:
            graph_event = GraphBuiltV1(
                event_id=str(uuid.uuid4()),
                timestamp=datetime.now(timezone.utc),
                repository_id=repo_id,
                nodes_created=nodes_count,
                edges_created=edges_count,
                duration_ms=duration_ms
            )
            self.publisher.publish("graph.built", graph_event)

        return {"nodes_created": nodes_count, "edges_created": edges_count}

    def _process_function_calls(self, func_node_id: str, calls: List[Any], file_path: str) -> int:
        edges_count = 0
        for call in calls:
            # Resolve call symbol via SymbolTable
            resolved_target = self.symbol_table.resolve_symbol(call.name) or call.name

            # Create CallNode
            call_node = self.nb.build_call_node(func_node_id, call.name, file_path, call.line_number, {
                "resolved_target": resolved_target,
                "arguments": call.arguments
            })
            self.repository.add_node(call_node.id, call_node.type, call_node.model_dump())

            # Function -> CALLS -> CallNode
            rel_calls = self.rb.build_relationship(func_node_id, call_node.id, "CALLS")
            self.repository.add_edge(rel_calls.source_node, rel_calls.target_node, rel_calls.relationship_type, rel_calls.metadata)
            edges_count += 1

            # CallNode -> BELONGS_TO -> resolved target function hash (if local/resolved)
            target_func_id = self.symbol_table.get_node_id(resolved_target)
            if not target_func_id:
                target_func_id = hashlib.sha256(resolved_target.encode()).hexdigest()
                
            rel_belongs = self.rb.build_relationship(call_node.id, target_func_id, "BELONGS_TO")
            self.repository.add_edge(rel_belongs.source_node, rel_belongs.target_node, rel_belongs.relationship_type, rel_belongs.metadata)
            edges_count += 2 # counts as another edge link

        return edges_count
