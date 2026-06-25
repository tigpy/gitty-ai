from ...domain.interfaces.parser import IParser
from typing import Dict, Any


class TypescriptParser(IParser):
    """
    Stub TypeScript parser.  Returns an empty IR module so that the worker
    pipeline does not crash when a .ts / .tsx file is encountered.
    """

    def parse_file(self, file_content: str) -> Dict[str, Any]:
        # TODO: implement full TypeScript AST parsing (tree-sitter recommended)
        return {
            "file_path": "",
            "language": "typescript",
            "imports": [],
            "classes": [],
            "functions": [],
            "calls": [],
        }


Class = TypescriptParser
