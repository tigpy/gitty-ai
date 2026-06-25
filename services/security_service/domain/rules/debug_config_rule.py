import ast
import hashlib
from typing import List
from libs.events.schemas import Severity
from .base_rule import SecurityRule
from ..entities.security_finding import SecurityFinding

class DebugConfigRule(SecurityRule):
    @property
    def id(self) -> str:
        return "DEBUG_CONFIG"

    @property
    def name(self) -> str:
        return "Debug Configurations"

    @property
    def severity(self) -> Severity:
        return Severity.LOW

    @property
    def cwe_id(self) -> str:
        return "CWE-489"

    @property
    def owasp_category(self) -> str:
        return "A05:2021-Security Misconfiguration"

    def evaluate(self, tree: ast.AST, file_content: str, file_path: str) -> List[SecurityFinding]:
        findings = []
        lines = file_content.splitlines()

        for node in ast.walk(tree):
            # 1. Check assignments: DEBUG = True
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == "DEBUG":
                        if isinstance(node.value, ast.Constant) and node.value.value is True:
                            line_idx = node.lineno - 1
                            snippet = lines[line_idx] if line_idx < len(lines) else ""
                            finding_id = hashlib.sha256(f"{file_path}:{node.lineno}:{self.id}:assign_debug".encode()).hexdigest()
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
                                description="DEBUG mode is explicitly set to True.",
                                recommendation="Ensure debug modes are disabled in production settings (e.g. read from an environment variable)."
                            ))

            # 2. Check run calls with debug=True
            if isinstance(node, ast.Call):
                is_run_debug = False
                func_name = None
                
                if isinstance(node.func, ast.Attribute) and node.func.attr == "run":
                    func_name = f"app.run"  # general run method
                    for kw in node.keywords:
                        if kw.arg == "debug":
                            if (isinstance(kw.value, ast.Constant) and kw.value.value is True) or \
                               (isinstance(kw.value, ast.Name) and kw.value.id == "True"):
                                is_run_debug = True
                                break
                elif isinstance(node.func, ast.Name) and node.func.id == "run":
                    func_name = "run"
                    for kw in node.keywords:
                        if kw.arg == "debug":
                            if (isinstance(kw.value, ast.Constant) and kw.value.value is True) or \
                               (isinstance(kw.value, ast.Name) and kw.value.id == "True"):
                                is_run_debug = True
                                break

                if is_run_debug:
                    line_idx = node.lineno - 1
                    snippet = lines[line_idx] if line_idx < len(lines) else ""
                    finding_id = hashlib.sha256(f"{file_path}:{node.lineno}:{self.id}:run_debug".encode()).hexdigest()
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
                        description=f"Server executed in debug mode via '{func_name}(debug=True)'.",
                        recommendation="Do not enable debug configurations in production environments. Run flask or general web app with debug=False."
                    ))

        return findings
