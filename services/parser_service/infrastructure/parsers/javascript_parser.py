from ...domain.interfaces.parser import IParser
from typing import Dict, Any


class JavascriptParser(IParser):
    """
    Stub JavaScript parser.  Returns an empty IR module so that the worker
    pipeline does not crash when a .js file is encountered.  A proper
    tree-sitter or acorn-based implementation can replace parse_file().
    """

    def parse_file(self, file_content: str) -> Dict[str, Any]:
        # TODO: implement full JavaScript AST parsing (tree-sitter recommended)
        return {
            "file_path": "",
            "language": "javascript",
            "imports": [],
            "classes": [],
            "functions": [],
            "calls": [],
        }


Class = JavascriptParser
