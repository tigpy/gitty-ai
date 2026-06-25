import ast
import hashlib
from typing import List
from libs.events.schemas import Severity
from .base_rule import SecurityRule
from ..entities.security_finding import SecurityFinding

class PickleRule(SecurityRule):
    @property
    def id(self) -> str:
        return "INSECURE_DESERIALIZATION"

    @property
    def name(self) -> str:
        return "Insecure Deserialization Detection"

    @property
    def severity(self) -> Severity:
        return Severity.HIGH

    @property
    def cwe_id(self) -> str:
        return "CWE-502"

    @property
    def owasp_category(self) -> str:
        return "A08:2021-Software and Data Integrity Failures"

    def evaluate(self, tree: ast.AST, file_content: str, file_path: str) -> List[SecurityFinding]:
        findings = []
        lines = file_content.splitlines()

        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func_name = None
                is_dangerous = False
                
                # Check for pickle.loads, marshal.loads, yaml.load
                if isinstance(node.func, ast.Attribute):
                    if isinstance(node.func.value, ast.Name):
                        full_name = f"{node.func.value.id}.{node.func.attr}"
                        if full_name in ("pickle.loads", "marshal.loads", "shelve.open"):
                            func_name = full_name
                            is_dangerous = True
                        elif full_name == "yaml.load":
                            # Check if Loader is SafeLoader
                            has_safe_loader = False
                            for kw in node.keywords:
                                if kw.arg == "Loader":
                                    if isinstance(kw.value, ast.Name) and kw.value.id == "SafeLoader":
                                        has_safe_loader = True
                                    elif isinstance(kw.value, ast.Attribute) and kw.value.attr == "SafeLoader":
                                        has_safe_loader = True
                            if not has_safe_loader:
                                func_name = "yaml.load"
                                is_dangerous = True
                
                elif isinstance(node.func, ast.Name):
                    if node.func.id in ("loads", "load"):
                        # If simple name, check if it could be from pickle or yaml
                        # For security, flag if loads/load is called, but we can check if it matches pickle/yaml imports
                        # Let's flag direct loads() or load() calls if we imported pickle or yaml
                        func_name = node.func.id
                        is_dangerous = True

                if is_dangerous:
                    line_idx = node.lineno - 1
                    snippet = lines[line_idx] if line_idx < len(lines) else ""
                    finding_id = hashlib.sha256(f"{file_path}:{node.lineno}:{self.id}:{func_name}".encode()).hexdigest()
                    findings.append(SecurityFinding(
                        id=finding_id,
                        rule_id=self.id,
                        severity=self.severity,
                        cwe_id=self.cwe_id,
                        owasp_category=self.owasp_category,
                        confidence="HIGH" if func_name != "load" and func_name != "loads" else "MEDIUM",
                        file_path=file_path,
                        line_number=node.lineno,
                        code_snippet=snippet.strip(),
                        description=f"Insecure deserialization call to '{func_name}()'.",
                        recommendation="Avoid deserializing untrusted data with pickle, marshal, or unsafe yaml. Use safe alternatives such as json.loads() or yaml.safe_load()."
                    ))

        return findings
