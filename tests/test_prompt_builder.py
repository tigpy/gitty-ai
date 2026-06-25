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
    
    assert "=== Repository Context ===" in prompt
    assert "=== User Question ===" in prompt
    assert "=== Instructions ===" in prompt
    
    assert "[Chunk 1] File: auth.py (Symbol: login), Lines: 1-2, Type: FUNCTION" in prompt
    assert "def login():" in prompt
    
    assert "[Chunk 2] File: README.md, Lines: N/A, Type: DOCUMENTATION" in prompt
    assert "# API documentation" in prompt
    
    assert "How to login?" in prompt
    assert builder.DEFAULT_SYSTEM_PROMPT is not None

def test_prompt_builder_context_truncation():
    # Force tiny character limit
    builder = PromptBuilder(max_context_chars=30)
    
    chunks = [
        Chunk(
            id="c1",
            text="this is a very long text snippet that will definitely exceed thirty characters limit",
            chunk_type="FILE",
            metadata={"file_path": "a.py"},
            content_hash="h1",
            version=1
        )
    ]
    
    prompt = builder.build_rag_prompt("query", chunks)
    
    # Extract the context section from the structured prompt
    assert "[Context Truncated for Limit]" in prompt
    # The actual context should be capped close to 30 chars (+ extra label text)
