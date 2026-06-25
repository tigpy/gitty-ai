from typing import List, Dict, Any, Optional
from services.vector_service.domain.value_objects.chunk import Chunk
from ...domain.entities.chat_session import ChatMessage

class PromptBuilder:
    PROMPT_VERSION = "v1"

    DEFAULT_SYSTEM_PROMPT = (
        "You are Gitty AI, a premium repository intelligence assistant.\n"
        "Answer the user's question about the repository using only the provided context.\n"
        "If the answer cannot be found in the retrieved context, state that the repository context does not contain sufficient information.\n"
        "When referring to code:\n"
        "- Mention file paths when available\n"
        "- Mention symbol names when available\n"
        "- Prefer concise technical explanations\n"
        "- Preserve code snippets exactly when cited"
    )

    def __init__(self, max_context_chars: int = 15000):
        self.max_context_chars = max_context_chars

    def build_rag_prompt(self, question: str, retrieved_chunks: List[Chunk]) -> str:
        context_parts = []
        
        for idx, chunk in enumerate(retrieved_chunks):
            chunk_type = chunk.chunk_type
            meta = chunk.metadata or {}
            file_path = meta.get("file_path", "unknown")
            symbol_name = meta.get("symbol_name")
            start_line = chunk.start_line
            end_line = chunk.end_line
            
            lines_str = f"{start_line}-{end_line}" if start_line is not None and end_line is not None else "N/A"
            symbol_str = f" (Symbol: {symbol_name})" if symbol_name else ""
            
            part = (
                f"[Chunk {idx + 1}] File: {file_path}{symbol_str}, Lines: {lines_str}, Type: {chunk_type}\n"
                f"Content:\n{chunk.text}\n"
                f"---"
            )
            context_parts.append(part)
            
        full_context = "\n\n".join(context_parts)
        
        # Enforce size clamping
        if len(full_context) > self.max_context_chars:
            full_context = full_context[:self.max_context_chars] + "\n[Context Truncated for Limit]"

        prompt = (
            "=== Repository Context ===\n\n"
            f"{full_context}\n\n"
            "=== User Question ===\n\n"
            f"{question}\n\n"
            "=== Instructions ===\n\n"
            "Answer using only the retrieved context above, adhering to the Gitty AI citation and technical guidelines."
        )
        return prompt

    def build_chat_prompt(
        self,
        question: str,
        retrieved_chunks: List[Chunk],
        history: List[ChatMessage],
        repository_id: str
    ) -> str:
        context_parts = []
        
        for idx, chunk in enumerate(retrieved_chunks):
            chunk_type = chunk.chunk_type
            meta = chunk.metadata or {}
            file_path = meta.get("file_path", "unknown")
            symbol_name = meta.get("symbol_name")
            start_line = chunk.start_line
            end_line = chunk.end_line
            
            lines_str = f"{start_line}-{end_line}" if start_line is not None and end_line is not None else "N/A"
            symbol_str = f" (Symbol: {symbol_name})" if symbol_name else ""
            
            part = (
                f"[Chunk {idx + 1}] File: {file_path}{symbol_str}, Lines: {lines_str}, Type: {chunk_type}\n"
                f"Content:\n{chunk.text}\n"
                f"---"
            )
            context_parts.append(part)
            
        full_context = "\n\n".join(context_parts)
        
        # Enforce size clamping
        if len(full_context) > self.max_context_chars:
            full_context = full_context[:self.max_context_chars] + "\n[Context Truncated for Limit]"

        # Format conversation history
        history_parts = []
        for msg in history:
            role_label = "User" if msg.role == "user" else "Assistant"
            history_parts.append(f"{role_label}: {msg.content}")
        
        full_history = "\n".join(history_parts)

        prompt = (
            "=== Current Repository ===\n\n"
            f"Repository ID: {repository_id}\n\n"
            "=== Repository Context ===\n\n"
            f"{full_context}\n\n"
            "=== Conversation History ===\n\n"
            f"{full_history or 'No previous messages.'}\n\n"
            "=== User Question ===\n\n"
            f"{question}\n\n"
            "=== Instructions ===\n\n"
            "Answer using the repository context and conversation history above, adhering to the Gitty AI citation and technical guidelines."
        )
        return prompt

