from unittest.mock import MagicMock

from services.graph_service.infrastructure.repositories.sqlite_graph_repository import SQLiteGraphRepository
from services.rag_service.application.services.chat_service import ChatService
from services.rag_service.application.services.graph_context_expander import (
    GraphContextExpander,
    assemble_hybrid_context,
)
from services.rag_service.application.services.prompt_builder import PromptBuilder
from services.rag_service.application.services.rag_service import RAGService
from services.rag_service.domain.entities.rag_query import RAGQuery
from services.rag_service.infrastructure.persistence.sqlite_session_repository import SQLiteChatSessionRepository
from services.vector_service.domain.value_objects.chunk import Chunk


def _chunk(text, node_id=None, file_path="auth.py", symbol="authenticate", chunk_type="FUNCTION"):
    metadata = {"file_path": file_path, "symbol_name": symbol, "repository_id": "auth-repo"}
    if node_id:
        metadata["graph_node_id"] = node_id
    return Chunk(
        id=f"vec-{symbol}",
        text=text,
        chunk_type=chunk_type,
        metadata=metadata,
        content_hash="h",
        version=1,
        start_line=1,
        end_line=3,
    )


def _build_auth_graph(tmp_path):
    repo = SQLiteGraphRepository(str(tmp_path / "graph.db"))
    repo.save_repository("auth-repo", "auth", "/src", "python", "now", "h1")
    repo.save_repository("other-repo", "other", "/other", "python", "now", "h2")
    nodes = [
        ("auth-repo", "Repository", {"name": "auth", "path": "/src"}),
        ("file-auth", "File", {"name": "auth.py", "path": "auth.py"}),
        ("file-sec", "File", {"name": "security.py", "path": "security.py"}),
        ("fn-auth", "Function", {"name": "authenticate", "path": "auth.py", "start_line": 1, "end_line": 4}),
        ("call-verify", "Call", {"name": "verify_password", "path": "auth.py"}),
        ("fn-verify", "Function", {"name": "verify_password", "path": "security.py", "start_line": 8, "end_line": 12}),
        ("imp-jwt", "Import", {"name": "jwt", "path": "auth.py"}),
        ("other-repo", "Repository", {"name": "other", "path": "/other"}),
        ("file-other", "File", {"name": "secret.py", "path": "secret.py"}),
        ("fn-secret", "Function", {"name": "other_secret_marker", "path": "secret.py"}),
    ]
    for node_id, label, props in nodes:
        repo.add_node(node_id, label, props)
    edges = [
        ("auth-repo", "file-auth", "CONTAINS"),
        ("auth-repo", "file-sec", "CONTAINS"),
        ("file-auth", "fn-auth", "CONTAINS"),
        ("file-auth", "imp-jwt", "IMPORTS"),
        ("file-sec", "fn-verify", "CONTAINS"),
        ("fn-auth", "call-verify", "CALLS"),
        ("call-verify", "fn-verify", "BELONGS_TO"),
        ("other-repo", "file-other", "CONTAINS"),
        ("file-other", "fn-secret", "CONTAINS"),
        ("fn-auth", "fn-secret", "CALLS"),
    ]
    for source, target, kind in edges:
        repo.add_edge(source, target, kind, {})
    return repo


def _graph_text(chunks):
    return "\n".join(chunk.text for chunk in chunks if chunk.chunk_type == "GRAPH")


def test_vector_only_context_when_graph_is_absent():
    seed = _chunk("def authenticate():\n    return True\n")
    assembled = assemble_hybrid_context(None, "auth-repo", [seed])
    assert assembled == [seed]
    assert all(chunk.chunk_type != "GRAPH" for chunk in assembled)


def test_authentication_question_expands_real_graph_relationships(tmp_path):
    repo = _build_auth_graph(tmp_path)
    seed = _chunk("def authenticate(user):\n    return verify_password(user)\n", node_id="fn-auth")
    extra = GraphContextExpander(repo, max_seeds=5, max_depth=2, max_nodes=24, max_relationships=32).expand(
        "auth-repo",
        [seed],
    )
    text = _graph_text(extra)
    assert "CALLS" in text
    assert "BELONGS_TO" in text
    assert "IMPORTS" in text
    assert "verify_password" in text
    assert "jwt" in text
    assert "other_secret_marker" not in text
    assert "CONTAINS" in text


def test_multiple_seeds_are_deduplicated(tmp_path):
    repo = _build_auth_graph(tmp_path)
    seeds = [
        _chunk("def authenticate():\n    pass\n", node_id="fn-auth"),
        _chunk("def verify_password():\n    pass\n", node_id="fn-verify", file_path="security.py", symbol="verify_password"),
    ]
    extra = GraphContextExpander(repo).expand("auth-repo", seeds)
    ids = [chunk.metadata["graph_node_id"] for chunk in extra]
    assert ids.count("file-auth") <= 1
    assert len(ids) == len(set(ids))
    assert "fn-auth" not in ids
    assert "fn-verify" not in ids


def test_expansion_is_bounded(tmp_path):
    repo = _build_auth_graph(tmp_path)
    seed = _chunk("def authenticate():\n    pass\n", node_id="fn-auth")
    extra = GraphContextExpander(
        repo, max_seeds=1, max_depth=2, max_nodes=1, max_relationships=2
    ).expand("auth-repo", [seed])
    assert len(extra) <= 1
    relationship_lines = [
        line for chunk in extra for line in chunk.text.splitlines() if " " in line and line != chunk.text.splitlines()[0]
    ]
    assert len(relationship_lines) <= 2


def test_unresolvable_chunk_and_graph_failure_keep_vector_evidence():
    seed = _chunk("def authenticate():\n    return 1\n")
    missing = GraphContextExpander(SQLiteGraphRepository(":memory:")).expand("auth-repo", [seed])
    assert missing == []
    assembled = assemble_hybrid_context(None, "auth-repo", [seed])
    assert assembled[0].text.startswith("def authenticate")

    class Unavailable:
        def get_nodes_by_repository(self, _repo_id):
            raise RuntimeError("graph unavailable")

        def get_outbound_edges(self, _node_id):
            raise RuntimeError("graph unavailable")

        def get_inbound_edges(self, _node_id):
            raise RuntimeError("graph unavailable")

        def get_node(self, _node_id):
            raise RuntimeError("graph unavailable")

        def get_repository(self, _repo_id):
            return None

    failed = assemble_hybrid_context(Unavailable(), "auth-repo", [seed])
    assert [chunk.text for chunk in failed] == [seed.text]
    assert all(chunk.chunk_type != "GRAPH" for chunk in failed)


def test_empty_graph_keeps_the_vector_chunk(tmp_path):
    repo = SQLiteGraphRepository(str(tmp_path / "empty.db"))
    repo.save_repository("auth-repo", "auth", "/src", "python", "now", "h")
    repo.add_node("fn-auth", "Function", {"name": "authenticate", "path": "auth.py"})
    seed = _chunk("def authenticate():\n    return 1\n", node_id="fn-auth")
    extra = GraphContextExpander(repo).expand("auth-repo", [seed])
    assert extra == []
    assembled = assemble_hybrid_context(repo, "auth-repo", [seed], max_nodes=24)
    assert assembled[0].chunk_type == "FUNCTION"
    assert not any(chunk.chunk_type == "GRAPH" for chunk in assembled)


def test_graph_context_stays_untrusted_and_out_of_the_system_prompt(tmp_path):
    repo = _build_auth_graph(tmp_path)
    seed = _chunk("def authenticate(user):\n    return verify_password(user)\n", node_id="fn-auth")
    assembled = assemble_hybrid_context(repo, "auth-repo", [seed])
    assert assembled[0].chunk_type == "FUNCTION"
    assert any(chunk.chunk_type == "GRAPH" for chunk in assembled)
    builder = PromptBuilder()
    prompt = builder.build_rag_prompt(
        "Where is authentication implemented and what components depend on it?",
        assembled,
    )
    system = builder.system_prompt
    assert "def authenticate(user):" in prompt
    assert "verify_password" in prompt
    assert 'origin="graph"' in prompt
    assert 'origin="vector"' in prompt
    assert "def authenticate(user):" not in system
    assert "verify_password" not in system
    assert "other_secret_marker" not in prompt
    assert prompt.count(f'</gitty-untrusted id="{builder.boundary_id}">') == 1


def test_prompt_budget_drops_graph_context_after_vector_evidence():
    vector = _chunk("def authenticate():\n    return 1\n", node_id="fn-auth")
    graph = Chunk(
        id="graph:file-auth",
        text="GRAPH-RELATIONSHIP " + ("x" * 400),
        chunk_type="GRAPH",
        metadata={"file_path": "auth.py", "symbol_name": "auth.py", "origin": "graph"},
        content_hash="",
        version=1,
    )
    prompt = PromptBuilder(max_context_chars=80).build_rag_prompt("Explain auth.", [vector, graph])
    assert "def authenticate():" in prompt
    assert "GRAPH-RELATIONSHIP" not in prompt


def test_rag_and_chat_keep_vector_citations_and_add_graph_context(tmp_path):
    repo = _build_auth_graph(tmp_path)
    seed = _chunk("def authenticate(user):\n    return verify_password(user)\n", node_id="fn-auth")
    search = MagicMock()
    search.retrieve_context.return_value = [seed]
    search.search_security_findings.return_value = []
    llm = MagicMock()
    llm.provider_name = "mock"
    llm.model_name = "mock"
    llm.generate.return_value = "Authentication is in auth.py and calls verify_password."

    rag = RAGService(search_service=search, llm_provider=llm, graph_repo=repo)
    response = rag.query_repository(RAGQuery(
        repository_id="auth-repo",
        question="Where is authentication implemented and what components depend on it?",
        include_security=False,
    ))
    assert len(response.retrieved_chunks) == 1
    assert response.retrieved_chunks[0].symbol_name == "authenticate"
    rag_prompt = llm.generate.call_args.kwargs["prompt"]
    rag_system = llm.generate.call_args.kwargs["system_prompt"]
    assert "def authenticate(user):" in rag_prompt
    assert "BELONGS_TO" in rag_prompt
    assert "other_secret_marker" not in rag_prompt
    assert "def authenticate(user):" not in rag_system

    sessions = SQLiteChatSessionRepository(str(tmp_path / "chat.db"))
    chat = ChatService(search_service=search, session_repo=sessions, llm_provider=llm, graph_repo=repo)
    session = chat.create_session("auth-repo")
    reply = chat.send_message(session.session_id, "What does authentication depend on?", include_security=False)
    assert len(reply.citations) == 1
    chat_prompt = llm.generate.call_args.kwargs["prompt"]
    assert "IMPORTS" in chat_prompt or "CALLS" in chat_prompt
    assert "other_secret_marker" not in chat_prompt
    assert "def authenticate(user):" not in llm.generate.call_args.kwargs["system_prompt"]
