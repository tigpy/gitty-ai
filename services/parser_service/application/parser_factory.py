from typing import Dict
from ..domain.interfaces.parser import IParser
from ..infrastructure.parsers.python_parser import PythonParser
from ..infrastructure.parsers.java_parser import JavaParser
from ..infrastructure.parsers.javascript_parser import JavascriptParser
from ..infrastructure.parsers.typescript_parser import TypescriptParser

class ParserFactory:
    def __init__(self):
        js_parser = JavascriptParser()
        ts_parser = TypescriptParser()
        self._parsers: Dict[str, IParser] = {
            "python": PythonParser(),
            "java": JavaParser(),
            "javascript": js_parser,
            "js": js_parser,
            "mjs": js_parser,
            "cjs": js_parser,
            "jsx": js_parser,
            "typescript": ts_parser,
            "ts": ts_parser,
            "tsx": ts_parser,
            "mts": ts_parser,
            "cts": ts_parser
        }

    @property
    def supported_languages(self):
        return ["python", "javascript", "typescript", "java"]

    def get_parser(self, language: str) -> IParser:
        normalized = language.lower()
        if normalized not in self._parsers:
            raise ValueError(f"No parser implementation registered for language: {language}")
        return self._parsers[normalized]
