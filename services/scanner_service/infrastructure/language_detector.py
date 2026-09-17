import os
from ..domain.interfaces.language_detector import ILanguageDetector

class LanguageDetector(ILanguageDetector):
    def __init__(self):
        self.mappings = {
            ".py": "python",
            ".java": "java",
            ".js": "javascript",
            ".mjs": "javascript",
            ".cjs": "javascript",
            ".jsx": "javascript",
            ".ts": "typescript",
            ".tsx": "typescript",
            ".mts": "typescript",
            ".cts": "typescript"
        }

    def detect_language(self, file_path: str) -> str:
        _, ext = os.path.splitext(file_path.lower())
        return self.mappings.get(ext, "unknown")
Class = LanguageDetector
