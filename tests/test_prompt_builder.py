import pytest
from services.rag_service.application.services.prompt_builder import PromptBuilder
from services.vector_service.domain.value_objects.chunk import Chunk

def test_prompt_builder_structure():
    builder = PromptBuilder()
    
    chunks = [
        Chunk(
            id="c1",
            text="def login():\n    pass",
            chunk_type="FUNCTION",
            metadata={"file_path": "auth.py", "symbol_name": "login"},
            content_hash="h1",
            version=1,
            start_line=1,
            end_line=2
        ),
        Chunk(
            id="c2",
            text="# API documentation\nDetails here",
            chunk_type="DOCUMENTATION",
            metadata={"file_path": "README.md"},
            content_hash="h2",
            version=1
        )
    ]
    
    prompt = builder.build_rag_prompt("How to login?", chunks)
    boundary = builder.boundary_id

    assert f'<gitty-untrusted id="{boundary}">' in prompt
    assert prompt.count(f'</gitty-untrusted id="{boundary}">') == 1
    assert f'<gitty-user-instruction id="{boundary}">' in prompt
    assert f'</gitty-user-instruction id="{boundary}">' in prompt
    assert boundary in builder.system_prompt
    assert "def login():" not in builder.system_prompt

    assert f'file="auth.py"' in prompt
    assert 'lines="1-2"' in prompt
    assert 'type="FUNCTION"' in prompt
    assert 'symbol="login"' in prompt
    assert "def login():" in prompt

    assert 'file="README.md"' in prompt
    assert 'type="DOCUMENTATION"' in prompt
    assert "# API documentation" in prompt

    assert "How to login?" in prompt
    assert builder.DEFAULT_SYSTEM_PROMPT is not None

def test_prompt_builder_context_truncation():
    # Character limit sufficient for only first chunk
    builder = PromptBuilder(max_context_chars=120)
    
    chunks = [
        Chunk(
            id="c1",
            text="chunk one content",
            chunk_type="FILE",
            metadata={"file_path": "a.py"},
            content_hash="h1",
            version=1
        ),
        Chunk(
            id="c2",
            text="chunk two should be excluded due to budget limit",
            chunk_type="FILE",
            metadata={"file_path": "b.py"},
            content_hash="h2",
            version=1
        )
    ]
    
    prompt = builder.build_rag_prompt("query", chunks)
    
    # First chunk is included
    assert "chunk one content" in prompt
    # Second chunk exceeded the budget and was omitted to prevent broken/cut-off syntax
    assert "chunk two should be excluded" not in prompt
