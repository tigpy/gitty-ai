import ast
from typing import Dict, Any, List, Optional
from ...domain.interfaces.parser import IParser
from libs.models.ir import IRImport, IRCall, IRFunction, IRClass, IRModule

class PythonASTVisitor(ast.NodeVisitor):
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.imports: List[IRImport] = []
        self.classes: List[IRClass] = []
        self.functions: List[IRFunction] = []
        self.calls: List[IRCall] = []

        # Track the current class *object* (not just its name) so that methods are
        # always appended to the correct IRClass instance even if two classes share
        # the same name (e.g. nested classes or same-name re-definitions).
        self._current_class_obj: Optional[IRClass] = None
        self._current_class: Optional[str] = None   # kept for is_method / class_context
        self._current_function: Optional[str] = None

    def visit_Import(self, node: ast.Import):
        for alias in node.names:
            self.imports.append(IRImport(
                name=alias.name,
                alias=alias.asname,
                line_number=node.lineno
            ))
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom):
        for alias in node.names:
            self.imports.append(IRImport(
                module=node.module,
                name=alias.name,
                alias=alias.asname,
                line_number=node.lineno
            ))
        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef):
        # Resolve bases
        bases = []
        for base in node.bases:
            if isinstance(base, ast.Name):
                bases.append(base.id)
            elif isinstance(base, ast.Attribute):
                # e.g., 'foo.bar'
                parts = []
                curr = base
                while isinstance(curr, ast.Attribute):
                    parts.append(curr.attr)
                    curr = curr.value
                if isinstance(curr, ast.Name):
                    parts.append(curr.id)
                bases.append(".".join(reversed(parts)))

        # Decorators names
        decorators = []
        for dec in node.decorator_list:
            if isinstance(dec, ast.Name):
                decorators.append(dec.id)
            elif isinstance(dec, ast.Attribute):
                decorators.append(dec.attr)

        prev_class = self._current_class
        prev_class_obj = self._current_class_obj
        self._current_class = node.name

        ir_class = IRClass(
            name=node.name,
            bases=bases,
            start_line=node.lineno,
            end_line=node.end_lineno or node.lineno,
            decorators=decorators,
            methods=[]
        )

        # Pin the current class *object* before visiting children so that methods
        # are always appended to the correct IRClass instance, even when two classes
        # share the same name (nested or re-defined).
        self._current_class_obj = ir_class
        self.classes.append(ir_class)
        self.generic_visit(node)

        self._current_class = prev_class
        self._current_class_obj = prev_class_obj

    def visit_FunctionDef(self, node: ast.FunctionDef):
        self._visit_function(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        self._visit_function(node)

    def _visit_function(self, node: Any):
        params = [arg.arg for arg in node.args.args]
        
        decorators = []
        for dec in node.decorator_list:
            if isinstance(dec, ast.Name):
                decorators.append(dec.id)
            elif isinstance(dec, ast.Attribute):
                decorators.append(dec.attr)
            elif isinstance(dec, ast.Call):
                # e.g. @cached(ttl=10)
                if isinstance(dec.func, ast.Name):
                    decorators.append(dec.func.id)

        # Return type representation
        return_type = None
        if node.returns:
            if isinstance(node.returns, ast.Name):
                return_type = node.returns.id

        prev_func = self._current_function
        self._current_function = node.name

        # Temporary local calls tracking for this function
        self._local_calls: List[IRCall] = []
        
        self.generic_visit(node)
        
        ir_function = IRFunction(
            name=node.name,
            parameters=params,
            return_type=return_type,
            start_line=node.lineno,
            end_line=node.end_lineno or node.lineno,
            decorators=decorators,
            calls=self._local_calls,
            is_method=self._current_class is not None,
            class_context=self._current_class
        )

        if self._current_class_obj is not None:
            # Append method directly to the pinned class object reference —
            # no name search needed, avoids the duplicate-name ambiguity bug.
            self._current_class_obj.methods.append(ir_function)
        else:
            self.functions.append(ir_function)

        self._current_function = prev_func

    def visit_Call(self, node: ast.Call):
        # Resolve function name
        func_name = ""
        if isinstance(node.func, ast.Name):
            func_name = node.func.id
        elif isinstance(node.func, ast.Attribute):
            parts = []
            curr = node.func
            while isinstance(curr, ast.Attribute):
                parts.append(curr.attr)
                curr = curr.value
            if isinstance(curr, ast.Name):
                parts.append(curr.id)
            func_name = ".".join(reversed(parts))

        if func_name:
            args_repr = []
            for arg in node.args:
                if isinstance(arg, ast.Constant):
                    args_repr.append(str(arg.value))
                elif isinstance(arg, ast.Name):
                    args_repr.append(arg.id)

            ir_call = IRCall(
                name=func_name,
                caller_name=self._current_function,
                line_number=node.lineno,
                arguments=args_repr
            )

            if self._current_function is not None:
                self._local_calls.append(ir_call)
            else:
                self.calls.append(ir_call)

        self.generic_visit(node)

class PythonParser(IParser):
    def parse_file(self, file_content: str) -> Dict[str, Any]:
        """
        Parses python source code and compiles it into an IR representation.
        """
        # Parse content into Python AST
        try:
            tree = ast.parse(file_content)
        except SyntaxError as e:
            # Return empty skeleton on syntax errors
            return IRModule(
                file_path="",
                language="python"
            ).model_dump()

        visitor = PythonASTVisitor("")
        visitor.visit(tree)

        module = IRModule(
            file_path="",
            language="python",
            imports=visitor.imports,
            classes=visitor.classes,
            functions=visitor.functions,
            calls=visitor.calls
        )
        return module.model_dump()
Class = PythonParser
