import tree_sitter
import tree_sitter_javascript
from typing import Dict, Any, List, Optional
from ...domain.interfaces.parser import IParser
from libs.models.ir import IRImport, IRCall, IRFunction, IRClass, IRModule
from libs.logging import get_logger

logger = get_logger("javascript_parser")

class JavascriptParser(IParser):
    def __init__(self):
        try:
            self.language = tree_sitter.Language(tree_sitter_javascript.language())
            self.parser = tree_sitter.Parser(self.language)
            self._available = True
        except Exception as e:
            logger.error("Failed to initialize tree-sitter JavaScript parser", error=str(e))
            self._available = False

    def parse_file(self, file_content: str, file_path: str = "", *args, **kwargs) -> Dict[str, Any]:
        if not self._available or not file_content or not file_content.strip():
            return IRModule(file_path=file_path, language="javascript").model_dump()

        try:
            content_bytes = file_content.encode("utf-8", errors="ignore")
            tree = self.parser.parse(content_bytes)
        except Exception as e:
            logger.warning("Tree-sitter parse error in JavaScript file", path=file_path, error=str(e))
            return IRModule(file_path=file_path, language="javascript").model_dump()

        imports: List[IRImport] = []
        classes: List[IRClass] = []
        functions: List[IRFunction] = []
        top_level_calls: List[IRCall] = []

        def get_text(node) -> str:
            if not node:
                return ""
            return content_bytes[node.start_byte:node.end_byte].decode("utf-8", errors="ignore")

        def extract_calls(parent_node) -> List[IRCall]:
            calls = []
            def walk_calls(n):
                if n.type == "call_expression":
                    fn_node = n.child_by_field_name("function")
                    fn_name = get_text(fn_node)
                    args_node = n.child_by_field_name("arguments")
                    args = []
                    if args_node:
                        for arg_child in args_node.children:
                            if arg_child.type not in ("(", ")", ","):
                                args.append(get_text(arg_child))
                    line_no = n.start_point[0] + 1
                    calls.append(IRCall(name=fn_name, line_number=line_no, arguments=args))
                elif n.type == "new_expression":
                    cn_node = n.child_by_field_name("constructor")
                    cn_name = get_text(cn_node)
                    args_node = n.child_by_field_name("arguments")
                    args = []
                    if args_node:
                        for arg_child in args_node.children:
                            if arg_child.type not in ("(", ")", ","):
                                args.append(get_text(arg_child))
                    line_no = n.start_point[0] + 1
                    calls.append(IRCall(name=cn_name, line_number=line_no, arguments=args))
                
                for child in n.children:
                    if child.type not in ("function_declaration", "arrow_function", "function_expression", "class_declaration"):
                        walk_calls(child)

            walk_calls(parent_node)
            return calls

        def extract_params(params_node) -> List[str]:
            params = []
            if not params_node:
                return params
            for child in params_node.children:
                if child.type in ("(", ")", ","):
                    continue
                if child.type == "identifier":
                    params.append(get_text(child))
                elif child.type == "assignment_pattern":
                    left = child.child_by_field_name("left")
                    if left:
                        params.append(get_text(left))
                elif child.type == "rest_pattern":
                    params.append(get_text(child))
                elif child.type in ("object_pattern", "array_pattern"):
                    params.append(get_text(child))
            return params

        def process_class(node) -> IRClass:
            name_node = node.child_by_field_name("name")
            cls_name = get_text(name_node) or "AnonymousClass"
            
            bases = []
            for child in node.children:
                if child.type == "class_heritage":
                    for sub in child.children:
                        if sub.type == "extends_clause":
                            for sc in sub.children:
                                if sc.type not in ("extends", ","):
                                    bases.append(get_text(sc))
                        elif sub.type not in ("extends",):
                            bases.append(get_text(sub))

            methods = []
            body_node = node.child_by_field_name("body")
            if body_node:
                for member in body_node.children:
                    if member.type == "method_definition":
                        m_name_node = member.child_by_field_name("name")
                        m_name = get_text(m_name_node)
                        params_node = member.child_by_field_name("parameters")
                        params = extract_params(params_node)
                        start_line = member.start_point[0] + 1
                        end_line = member.end_point[0] + 1
                        
                        method_body = member.child_by_field_name("body")
                        m_calls = extract_calls(method_body) if method_body else []
                        
                        methods.append(IRFunction(
                            name=m_name,
                            parameters=params,
                            start_line=start_line,
                            end_line=end_line,
                            calls=m_calls,
                            is_method=True,
                            class_context=cls_name
                        ))

            start_line = node.start_point[0] + 1
            end_line = node.end_point[0] + 1
            return IRClass(
                name=cls_name,
                bases=bases,
                start_line=start_line,
                end_line=end_line,
                methods=methods
            )

        def process_function(node, name_override: Optional[str] = None) -> IRFunction:
            fn_name = name_override if name_override else (get_text(node.child_by_field_name("name")) or "anonymous")
            params_node = node.child_by_field_name("parameters")
            params = extract_params(params_node)
            start_line = node.start_point[0] + 1
            end_line = node.end_point[0] + 1
            
            body_node = node.child_by_field_name("body")
            fn_calls = extract_calls(body_node) if body_node else []
            
            return IRFunction(
                name=fn_name,
                parameters=params,
                start_line=start_line,
                end_line=end_line,
                calls=fn_calls,
                is_method=False
            )

        def process_import(node):
            source_node = node.child_by_field_name("source")
            module_name = get_text(source_node).strip("'\"") if source_node else ""
            line_no = node.start_point[0] + 1
            has_specifiers = False
            for child in node.children:
                if child.type == "import_clause":
                    for clause_child in child.children:
                        if clause_child.type == "identifier":
                            imports.append(IRImport(
                                module=module_name,
                                name=get_text(clause_child),
                                line_number=line_no
                            ))
                            has_specifiers = True
                        elif clause_child.type == "named_imports":
                            for spec in clause_child.children:
                                if spec.type == "import_specifier":
                                    name_sub = spec.child_by_field_name("name")
                                    alias_sub = spec.child_by_field_name("alias")
                                    imports.append(IRImport(
                                        module=module_name,
                                        name=get_text(name_sub),
                                        alias=get_text(alias_sub) if alias_sub else None,
                                        line_number=line_no
                                    ))
                                    has_specifiers = True
                        elif clause_child.type == "namespace_import":
                            alias_sub = clause_child.child_by_field_name("alias") or [c for c in clause_child.children if c.type == "identifier"]
                            alias_name = get_text(alias_sub[0]) if isinstance(alias_sub, list) and alias_sub else get_text(alias_sub)
                            imports.append(IRImport(
                                module=module_name,
                                name="*",
                                alias=alias_name,
                                line_number=line_no
                            ))
                            has_specifiers = True

            if not has_specifiers and module_name:
                imports.append(IRImport(
                    module=module_name,
                    name="*",
                    line_number=line_no
                ))

        def scan_top_level(node):
            for child in node.children:
                if child.type == "import_statement":
                    process_import(child)
                    
                elif child.type == "export_statement":
                    for export_child in child.children:
                        if export_child.type == "class_declaration":
                            classes.append(process_class(export_child))
                        elif export_child.type == "function_declaration":
                            functions.append(process_function(export_child))
                        elif export_child.type in ("lexical_declaration", "variable_declaration"):
                            for decl in export_child.children:
                                if decl.type == "variable_declarator":
                                    id_node = decl.child_by_field_name("name")
                                    val_node = decl.child_by_field_name("value")
                                    if val_node and val_node.type in ("arrow_function", "function_expression"):
                                        functions.append(process_function(val_node, name_override=get_text(id_node)))
                                    elif val_node and val_node.type == "call_expression":
                                        fn_node = val_node.child_by_field_name("function")
                                        if get_text(fn_node) == "require":
                                            args_node = val_node.child_by_field_name("arguments")
                                            arg_text = ""
                                            if args_node:
                                                for a in args_node.children:
                                                    if a.type in ("string", "string_fragment"):
                                                        arg_text = get_text(a).strip("'\"")
                                            imports.append(IRImport(module=arg_text, name=get_text(id_node), line_number=child.start_point[0]+1))
                            
                elif child.type == "class_declaration":
                    classes.append(process_class(child))
                    
                elif child.type == "function_declaration":
                    functions.append(process_function(child))
                    
                elif child.type in ("lexical_declaration", "variable_declaration"):
                    for decl in child.children:
                        if decl.type == "variable_declarator":
                            id_node = decl.child_by_field_name("name")
                            val_node = decl.child_by_field_name("value")
                            if val_node and val_node.type in ("arrow_function", "function_expression"):
                                functions.append(process_function(val_node, name_override=get_text(id_node)))
                            elif val_node and val_node.type == "call_expression":
                                fn_node = val_node.child_by_field_name("function")
                                if get_text(fn_node) == "require":
                                    args_node = val_node.child_by_field_name("arguments")
                                    arg_text = ""
                                    if args_node:
                                        for a in args_node.children:
                                            if a.type in ("string", "string_fragment"):
                                                arg_text = get_text(a).strip("'\"")
                                    if id_node and id_node.type == "identifier":
                                        imports.append(IRImport(module=arg_text, name=get_text(id_node), line_number=child.start_point[0]+1))
                                    elif id_node and id_node.type == "object_pattern":
                                        for prop in id_node.children:
                                            if prop.type == "shorthand_property_identifier_pattern":
                                                imports.append(IRImport(module=arg_text, name=get_text(prop), line_number=child.start_point[0]+1))
                elif child.type == "expression_statement":
                    for expr_child in child.children:
                        if expr_child.type == "call_expression":
                            fn_node = expr_child.child_by_field_name("function")
                            if get_text(fn_node) == "require":
                                args_node = expr_child.child_by_field_name("arguments")
                                arg_text = ""
                                if args_node:
                                    for a in args_node.children:
                                        if a.type in ("string", "string_fragment"):
                                            arg_text = get_text(a).strip("'\"")
                                imports.append(IRImport(module=arg_text, name="*", line_number=child.start_point[0]+1))
                            else:
                                top_level_calls.extend(extract_calls(expr_child))

        scan_top_level(tree.root_node)

        module = IRModule(
            file_path=file_path,
            language="javascript",
            imports=imports,
            classes=classes,
            functions=functions,
            calls=top_level_calls
        )
        return module.model_dump()

Class = JavascriptParser
