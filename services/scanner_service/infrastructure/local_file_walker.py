import os
import hashlib
import fnmatch
from typing import List, Dict, Any, Set
from ..domain.interfaces.file_walker import IFileWalker

class LocalFileWalker(IFileWalker):
    def __init__(self, default_ignores: List[str] = None):
        self.default_ignores = default_ignores or [
            "node_modules", "venv", "__pycache__", "dist", "build", "target", ".git", ".pytest_cache"
        ]

    def _should_ignore(self, name: str, relative_path: str, ignore_patterns: Set[str]) -> bool:
        # Check against default ignore patterns
        for pattern in self.default_ignores:
            if pattern in relative_path.split(os.sep):
                return True
                
        # Check against parsed .gitignore patterns
        for pattern in ignore_patterns:
            if fnmatch.fnmatch(name, pattern) or fnmatch.fnmatch(relative_path, pattern):
                return True
            # Matches folder names inside relative_path
            for part in relative_path.split(os.sep):
                if fnmatch.fnmatch(part, pattern):
                    return True
        return False

    def _parse_gitignore(self, root_path: str) -> Set[str]:
        patterns = set()
        gitignore_path = os.path.join(root_path, ".gitignore")
        if os.path.exists(gitignore_path):
            try:
                with open(gitignore_path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#"):
                            # Normalize path slashes
                            line = line.replace("/", os.sep)
                            patterns.add(line)
            except Exception:
                pass
        return patterns

    def _compute_sha256(self, filepath: str) -> str:
        sha256_hash = hashlib.sha256()
        try:
            with open(filepath, "rb") as f:
                for byte_block in iter(lambda: f.read(4096), b""):
                    sha256_hash.update(byte_block)
            return sha256_hash.hexdigest()
        except Exception:
            return ""

    def walk(self, root_path: str) -> List[Dict[str, Any]]:
        file_list = []
        ignore_patterns = self._parse_gitignore(root_path)

        for dirpath, dirnames, filenames in os.walk(root_path):
            # In-place modify dirnames to avoid descending into ignored directories
            rel_dirpath = os.path.relpath(dirpath, root_path)
            if rel_dirpath == ".":
                rel_dirpath = ""

            dirnames[:] = [
                d for d in dirnames
                if not self._should_ignore(d, os.path.join(rel_dirpath, d), ignore_patterns)
            ]

            for filename in filenames:
                rel_filepath = os.path.join(rel_dirpath, filename) if rel_dirpath else filename
                if self._should_ignore(filename, rel_filepath, ignore_patterns):
                    continue

                abs_path = os.path.join(dirpath, filename)
                real_root = os.path.normcase(os.path.realpath(root_path))
                real_file = os.path.normcase(os.path.realpath(abs_path))
                if not (real_file == real_root or real_file.startswith(real_root + os.path.sep)):
                    continue

                try:
                    size = os.path.getsize(abs_path)
                    extension = os.path.splitext(filename)[1]
                    checksum = self._compute_sha256(abs_path)

                    file_list.append({
                        "path": rel_filepath,
                        "extension": extension,
                        "size": size,
                        "checksum": checksum
                    })
                except Exception:
                    pass

        return file_list
Class = LocalFileWalker
