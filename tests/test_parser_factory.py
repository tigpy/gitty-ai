import pytest
from services.parser_service.application.parser_factory import ParserFactory
from services.parser_service.infrastructure.parsers.python_parser import PythonParser
from services.parser_service.infrastructure.parsers.java_parser import JavaParser
from services.parser_service.infrastructure.parsers.javascript_parser import JavascriptParser
from services.parser_service.infrastructure.parsers.typescript_parser import TypescriptParser

def test_parser_factory_retrieval():
    factory = ParserFactory()
    
    assert isinstance(factory.get_parser("python"), PythonParser)
    assert isinstance(factory.get_parser("java"), JavaParser)
    assert isinstance(factory.get_parser("javascript"), JavascriptParser)
    assert isinstance(factory.get_parser("typescript"), TypescriptParser)
    
    # Case insensitivity
    assert isinstance(factory.get_parser("PYTHON"), PythonParser)
    assert isinstance(factory.get_parser("TypeScript"), TypescriptParser)

def test_parser_factory_invalid_language():
    factory = ParserFactory()
    with pytest.raises(ValueError) as excinfo:
        factory.get_parser("ruby")
    assert "No parser implementation registered for language: ruby" in str(excinfo.value)

def test_parser_factory_parsers():
    factory = ParserFactory()
    # Java returns placeholder IR
    java_parser = factory.get_parser("java")
    java_result = java_parser.parse_file("public class Foo {}", file_path="test.java")
    assert java_result.get("unsupported") is True

    # JavaScript and TypeScript return active IR
    for lang in ["javascript", "typescript"]:
        parser = factory.get_parser(lang)
        result = parser.parse_file("function hello() { return 1; }", file_path=f"test.{lang}")
        assert result.get("unsupported") is not True
        assert len(result.get("functions", [])) == 1
        assert result["functions"][0]["name"] == "hello"
