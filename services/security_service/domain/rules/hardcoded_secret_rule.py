import ast
import re
import hashlib
from typing import List
from libs.events.schemas import Severity
from .base_rule import SecurityRule
from ..entities.security_finding import SecurityFinding

SECRET_KEYWORDS = {"aws_secret_access_key", "api_key", "token", "password", "private_key"}

class HardcodedSecretRule(SecurityRule):
    @property
    def id(self) -> str:
        return "HARDCODED_SECRET"

    @property
    def name(self) -> str:
        return "Hardcoded Secrets Detection"

    @property
    def severity(self) -> Severity:
        return Severity.HIGH

    @property
    def cwe_id(self) -> str:
        return "CWE-798"

    @property
    def owasp_category(self) -> str:
        return "A01:2021-Broken Access Control"

    def _is_placeholder(self, val: str) -> bool:
        val_lower = val.lower()
        if len(val.strip()) <= 4:
            return True
        placeholders = ["xxxx", "your_", "secret_key", "placeholder", "my_token", "<", ">", "[", "]"]
        for p in placeholders:
            if p in val_lower:
                return True
        return False

    def evaluate(self, tree: ast.AST, file_content: str, file_path: str) -> List[SecurityFinding]:
        findings = []
        lines = file_content.splitlines()

        # AST Scanning for variable assignments
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        name_lower = target.id.lower()
                        if any(kw in name_lower for kw in SECRET_KEYWORDS):
                            if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                                val = node.value.value
                                if not self._is_placeholder(val):
                                    line_idx = node.lineno - 1
                                    snippet = lines[line_idx] if line_idx < len(lines) else ""
                                    finding_id = hashlib.sha256(f"{file_path}:{node.lineno}:{self.id}:{target.id}".encode()).hexdigest()
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
                                        description=f"Potential hardcoded secret assigned to '{target.id}'.",
                                        recommendation="Remove hardcoded secrets and use environment variables or a secure secret manager."
                                    ))

        # Regex line-by-line fallback (for comments or assignments that might have been skipped)
        # To avoid duplicate findings on the same line, track already flagged lines
        flagged_lines = {f.line_number for f in findings}
        
        # Matches typical variable assignment to string literals
        pattern = re.compile(r'(?i)\b(aws_secret_access_key|api_key|token|password|private_key)\s*=\s*[\'"]([^\'"]+)[\'"]')
        for idx, line in enumerate(lines):
            line_no = idx + 1
            if line_no in flagged_lines:
                continue
            match = pattern.search(line)
            if match:
                var_name = match.group(1)
                val = match.group(2)
                if not self._is_placeholder(val):
                    finding_id = hashlib.sha256(f"{file_path}:{line_no}:{self.id}:{var_name}".encode()).hexdigest()
                    findings.append(SecurityFinding(
                        id=finding_id,
                        rule_id=self.id,
                        severity=self.severity,
                        cwe_id=self.cwe_id,
                        owasp_category=self.owasp_category,
                        confidence="HIGH",
                        file_path=file_path,
                        line_number=line_no,
                        code_snippet=line.strip(),
                        description=f"Potential hardcoded secret matching regex for '{var_name}'.",
                        recommendation="Remove hardcoded secrets and use environment variables or a secure secret manager."
                    ))

        return findings
