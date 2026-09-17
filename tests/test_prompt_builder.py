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
    
    assert "=== Repository Context (Untrusted Data) ===" in prompt
    assert "<repository_untrusted_context>" in prompt
    assert "</repository_untrusted_context>" in prompt
    assert "=== User Question ===" in prompt
    assert "=== Instructions ===" in prompt
    
    assert '<code_chunk index="1" file="auth.py" lines="1-2" type="FUNCTION" symbol="login">' in prompt
    assert "def login():" in prompt
    
    assert '<code_chunk index="2" file="README.md" lines="N/A" type="DOCUMENTATION">' in prompt
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
