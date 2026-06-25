import os
import pytest
from services.vector_service.application.services.chunking_service import ChunkingService

def test_chunking_service_generate_chunks(tmp_path):
    # Create mock repo dir
    repo_dir = tmp_path / "mock_repo"
    repo_dir.mkdir()
    
    # Write a mock python file
    f_py = repo_dir / "user.py"
    f_py.write_text("""# User module
class User:
    def login(self):
        print("login")

def helper():
    return 42
""", encoding="utf-8")

    # Write a mock README.md
    readme = repo_dir / "README.md"
    readme.write_text("""# Gitty AI Mock Repository
This is a mock repository for vector indexing testing.

## Installation
Run pip install.

## Usage
Run python main.py.
""", encoding="utf-8")

    # Create mock graph nodes
    nodes = [
        {
            "type": "Repository", "id": "repo-1", "name": "mock_repo", "path": str(repo_dir)
        },
        {
            "type": "File", "id": "f_node", "name": "user.py", "path": "user.py"
        },
        {
            "type": "Class", "id": "cls_node", "name": "User", "path": "user.py",
            "metadata": {"start_line": 2, "end_line": 4}
        },
        {
            "type": "Function", "id": "func_node", "name": "login", "path": "user.py",
            "metadata": {"start_line": 3, "end_line": 4}
        },
        {
            "type": "Function", "id": "helper_node", "name": "helper", "path": "user.py",
            "metadata": {"start_line": 6, "end_line": 7}
        }
    ]

    # Mock security findings
    findings = [
        {
            "id": "sec-1",
            "rule_id": "HARDCODED_SECRET",
            "severity": "HIGH",
            "file_path": "user.py",
            "line_number": 6,
            "code_snippet": "password = '123'",
            "description": "Hardcoded password"
        }
    ]

    service = ChunkingService()
    chunks = service.generate_chunks(
        nodes=nodes,
        repo_id="repo-1",
        repo_name="mock_repo",
        repo_path=str(repo_dir),
        security_findings=findings
    )

    # Chunks should contain:
    # - 1 File chunk (user.py)
    # - 1 Class chunk (User)
    # - 2 Function chunks (login, helper)
    # - 3 Documentation chunks (README split: intro, Installation, Usage)
    # - 1 Security Finding chunk
    assert len(chunks) == 8

    chunk_types = [c.chunk_type for c in chunks]
    assert chunk_types.count("FUNCTION") == 2
    assert chunk_types.count("CLASS") == 1
    assert chunk_types.count("FILE") == 1
    assert chunk_types.count("DOCUMENTATION") == 3
    assert chunk_types.count("SECURITY_FINDING") == 1

    # Verify functions chunk content
    helper_chunk = next(c for c in chunks if c.chunk_type == "FUNCTION" and c.metadata["symbol_name"] == "helper")
    assert "def helper():" in helper_chunk.text
    assert helper_chunk.start_line == 6
    assert helper_chunk.end_line == 7
    assert helper_chunk.content_hash is not None
    assert helper_chunk.version == 1

    # Verify documentation heading extraction
    doc_chunk = next(c for c in chunks if c.chunk_type == "DOCUMENTATION" and "Installation" in c.metadata["symbol_name"])
    assert "## Installation" in doc_chunk.text
    
    # Verify security finding chunk content
    sec_chunk = next(c for c in chunks if c.chunk_type == "SECURITY_FINDING")
    assert "Severity: HIGH" in sec_chunk.text
    assert "HARDCODED_SECRET" in sec_chunk.text
