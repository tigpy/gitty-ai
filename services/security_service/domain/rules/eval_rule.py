import ast
import hashlib
from typing import List
from libs.events.schemas import Severity
from .base_rule import SecurityRule
from ..entities.security_finding import SecurityFinding

DANGEROUS_FUNCS = {"eval", "exec", "compile"}

class EvalRule(SecurityRule):
    @property
    def id(self) -> str:
        return "EVAL_EXEC"

    @property
    def name(self) -> str:
        return "Dangerous APIs Detection"

    @property
    def severity(self) -> Severity:
        return Severity.HIGH

    @property
    def cwe_id(self) -> str:
        return "CWE-95"

    @property
    def owasp_category(self) -> str:
        return "A03:2021-Injection"

    def evaluate(self, tree: ast.AST, file_content: str, file_path: str) -> List[SecurityFinding]:
        findings = []
        lines = file_content.splitlines()

        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func_name = None
                if isinstance(node.func, ast.Name):
                    func_name = node.func.id
                
                if func_name in DANGEROUS_FUNCS:
                    line_idx = node.lineno - 1
                    snippet = lines[line_idx] if line_idx < len(lines) else ""
                    finding_id = hashlib.sha256(f"{file_path}:{node.lineno}:{self.id}:{func_name}".encode()).hexdigest()
                    findings.append(SecurityFinding(
                        id=finding_id,
                        rule_id=self.id,
                        severity=self.severity,
                        cwe_id=self.cwe_id,
                        owasp_category=self.owasp_category,
                        confidence="HIGH",
                        file_path=file_path,
                        line_number=node.lineno,
                        code_snippet=snippet.strip(),
                        description=f"Use of dangerous built-in API '{func_name}()'.",
                        recommendation=f"Avoid using '{func_name}()' with untrusted input as it can lead to arbitrary code execution. Rewrite using safer alternatives."
                    ))

        return findings
