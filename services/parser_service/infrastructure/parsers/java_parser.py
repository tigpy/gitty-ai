from ...domain.interfaces.parser import IParser
from typing import Dict, Any
from libs.logging import get_logger

logger = get_logger("java_parser")

class JavaParser(IParser):
    def parse_file(self, file_content: str, *args, **kwargs) -> Dict[str, Any]:
        """
        Gracefully handles Java files when Tree-sitter is unavailable.
        Returns a valid empty IR dictionary to prevent worker pipeline crashes.
        """
        logger.info("Java AST parsing is currently not active; indexing file without AST symbols.")
        return {
            "imports": [],
            "classes": [],
            "functions": [],
            "calls": [],
            "unsupported": True,
            "language": "java"
        }

Class = JavaParser

