from ...domain.interfaces.parser import IParser
from typing import Dict, Any


class JavaParser(IParser):
    """
    Stub Java parser.  Returns an empty IR module so that the worker pipeline
    does not crash when a Java file is encountered.  A proper tree-sitter or
    javac-based implementation can replace the body of parse_file() without
    changing any callers.
    """

    def parse_file(self, file_content: str) -> Dict[str, Any]:
        # TODO: implement full Java AST parsing (tree-sitter recommended)
        return {
            "file_path": "",
            "language": "java",
            "imports": [],
            "classes": [],
            "functions": [],
            "calls": [],
        }


Class = JavaParser
