import ast
from abc import ABC, abstractmethod
from typing import List
from libs.events.schemas import Severity
from ..entities.security_finding import SecurityFinding

class SecurityRule(ABC):
    @property
    @abstractmethod
    def id(self) -> str:
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @property
    @abstractmethod
    def severity(self) -> Severity:
        pass

    @property
    @abstractmethod
    def cwe_id(self) -> str:
        pass

    @property
    @abstractmethod
    def owasp_category(self) -> str:
        pass

    @abstractmethod
    def evaluate(self, tree: ast.AST, file_content: str, file_path: str) -> List[SecurityFinding]:
        """
        Evaluates the python AST, raw file content, and file path.
        Returns a list of SecurityFinding objects if any security issue is found.
        """
        pass
