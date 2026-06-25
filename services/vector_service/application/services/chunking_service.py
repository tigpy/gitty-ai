import os
import hashlib
from typing import List, Dict, Any, Optional
from ...domain.value_objects.chunk import Chunk

class ChunkingService:
    def _read_file_lines(self, abs_path: str, repo_path: str, start_line: Optional[int], end_line: Optional[int]) -> Optional[str]:
        if not os.path.exists(abs_path):
            return None
        if repo_path:
            real_root = os.path.normcase(os.path.realpath(repo_path))
            real_file = os.path.normcase(os.path.realpath(abs_path))
            if not (real_file == real_root or real_file.startswith(real_root + os.path.sep)):
                return None
        try:
            with open(abs_path, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()
            if start_line is not None and end_line is not None:
                s_idx = max(0, start_line - 1)
                e_idx = min(len(lines), end_line)
                return "".join(lines[s_idx:e_idx])
            return "".join(lines)
        except Exception:
            return None

    def generate_chunks(
        self, 
        nodes: List[Dict[str, Any]], 
        repo_id: str, 
        repo_name: str, 
        repo_path: str,
        security_findings: Optional[List[Dict[str, Any]]] = None
    ) -> List[Chunk]:
        """Generates versioned, metadata-rich chunks from graph nodes, docs, and security findings."""
        chunks: List[Chunk] = []

        for node in nodes:
            node_type = node.get("type")
            name = node.get("name", "")
            path = node.get("path", "")
            node_id = node.get("id")

            if not path or not node_id:
                continue

            abs_path = os.path.join(repo_path, path) if repo_path else path
            meta = node.get("metadata", {})

            if node_type == "Function":
                start = meta.get("start_line") or node.get("start_line")
                end = meta.get("end_line") or node.get("end_line")
                code = self._read_file_lines(abs_path, repo_path, start, end)
                if code:
                    content_hash = hashlib.sha256(code.encode("utf-8")).hexdigest()
                    chunk_id = hashlib.sha256(f"{repo_id}:chunk:function:{node_id}".encode()).hexdigest()
                    metadata = {
                        "repository_id": repo_id,
                        "repository_name": repo_name,
                        "file_path": path,
                        "language": "python",
                        "symbol_name": name,
                        "node_type": "FUNCTION",
                        "chunk_type": "FUNCTION"
                    }
                    chunks.append(Chunk(
                        id=chunk_id,
                        text=code,
                        chunk_type="FUNCTION",
                        metadata=metadata,
                        content_hash=content_hash,
                        version=1,
                        start_line=start,
                        end_line=end
                    ))

            elif node_type == "Class":
                start = meta.get("start_line") or node.get("start_line")
                end = meta.get("end_line") or node.get("end_line")
                code = self._read_file_lines(abs_path, repo_path, start, end)
                if code:
                    content_hash = hashlib.sha256(code.encode("utf-8")).hexdigest()
                    chunk_id = hashlib.sha256(f"{repo_id}:chunk:class:{node_id}".encode()).hexdigest()
                    metadata = {
                        "repository_id": repo_id,
                        "repository_name": repo_name,
                        "file_path": path,
                        "language": "python",
                        "symbol_name": name,
                        "node_type": "CLASS",
                        "chunk_type": "CLASS"
                    }
                    chunks.append(Chunk(
                        id=chunk_id,
                        text=code,
                        chunk_type="CLASS",
                        metadata=metadata,
                        content_hash=content_hash,
                        version=1,
                        start_line=start,
                        end_line=end
                    ))

            elif node_type == "File":
                code = self._read_file_lines(abs_path, repo_path, None, None)
                if code:
                    content_hash = hashlib.sha256(code.encode("utf-8")).hexdigest()
                    chunk_id = hashlib.sha256(f"{repo_id}:chunk:file:{node_id}".encode()).hexdigest()
                    metadata = {
                        "repository_id": repo_id,
                        "repository_name": repo_name,
                        "file_path": path,
                        "language": "python",
                        "symbol_name": name,
                        "node_type": "FILE",
                        "chunk_type": "FILE"
                    }
                    chunks.append(Chunk(
                        id=chunk_id,
                        text=code,
                        chunk_type="FILE",
                        metadata=metadata,
                        content_hash=content_hash,
                        version=1
                    ))

        # Chunk Documentation (README.md)
        readme_rel = "README.md"
        readme_abs = os.path.join(repo_path, readme_rel) if repo_path else readme_rel
        if os.path.exists(readme_abs):
            readme_code = self._read_file_lines(readme_abs, repo_path, None, None)
            if readme_code:
                # Divide README by headings
                heading_splits = readme_code.split("\n#")
                for h_idx, section in enumerate(heading_splits):
                    if not section.strip():
                        continue
                    # Restore # prefix (except for first item if it didn't start with #)
                    h_text = "#" + section if h_idx > 0 else section
                    lines = h_text.splitlines()
                    heading_title = lines[0].replace("#", "").strip() if lines else f"section_{h_idx}"
                    
                    content_hash = hashlib.sha256(h_text.encode("utf-8")).hexdigest()
                    chunk_id = hashlib.sha256(f"{repo_id}:chunk:doc:{h_idx}".encode()).hexdigest()
                    metadata = {
                        "repository_id": repo_id,
                        "repository_name": repo_name,
                        "file_path": readme_rel,
                        "language": "markdown",
                        "symbol_name": f"README: {heading_title}",
                        "node_type": "DOCUMENTATION",
                        "chunk_type": "DOCUMENTATION"
                    }
                    chunks.append(Chunk(
                        id=chunk_id,
                        text=h_text,
                        chunk_type="DOCUMENTATION",
                        metadata=metadata,
                        content_hash=content_hash,
                        version=1
                    ))

        # Chunk Security Findings
        if security_findings:
            for find in security_findings:
                finding_id = find.get("id")
                rule_id = find.get("rule_id", "vulnerability")
                severity = find.get("severity", "UNKNOWN")
                f_path = find.get("file_path", "")
                line_no = find.get("line_number", 0)
                code_snippet = find.get("code_snippet", "")
                description = find.get("description", "")
                
                text_content = (
                    f"Severity: {severity}, Rule: {rule_id}, File: {f_path}, Line: {line_no}, "
                    f"Code: {code_snippet}, Description: {description}"
                )
                
                content_hash = hashlib.sha256(text_content.encode("utf-8")).hexdigest()
                chunk_id = hashlib.sha256(f"{repo_id}:chunk:security:{finding_id}".encode()).hexdigest()
                metadata = {
                    "repository_id": repo_id,
                    "repository_name": repo_name,
                    "file_path": f_path,
                    "language": "python",
                    "symbol_name": rule_id,
                    "node_type": "SECURITY_FINDING",
                    "chunk_type": "SECURITY_FINDING"
                }
                chunks.append(Chunk(
                    id=chunk_id,
                    text=text_content,
                    chunk_type="SECURITY_FINDING",
                    metadata=metadata,
                    content_hash=content_hash,
                    version=1,
                    start_line=line_no,
                    end_line=line_no
                ))

        return chunks
