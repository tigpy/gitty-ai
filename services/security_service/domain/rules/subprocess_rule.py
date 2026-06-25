import ast
import hashlib
from typing import List
from libs.events.schemas import Severity
from .base_rule import SecurityRule
from ..entities.security_finding import SecurityFinding

SUBPROCESS_FUNCS = {"run", "Popen", "call", "check_call", "check_output"}

class SubprocessRule(SecurityRule):
    @property
    def id(self) -> str:
        return "COMMAND_INJECTION"

    @property
    def name(self) -> str:
        return "Command Injection Risks"

    @property
    def severity(self) -> Severity:
        return Severity.CRITICAL

    @property
    def cwe_id(self) -> str:
        return "CWE-78"

    @property
    def owasp_category(self) -> str:
        return "A03:2021-Injection"

    def evaluate(self, tree: ast.AST, file_content: str, file_path: str) -> List[SecurityFinding]:
        findings = []
        lines = file_content.splitlines()

        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func_name = None
                is_injection_risk = False
                
                # Check for os.system
                if isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name):
                    if node.func.value.id == "os" and node.func.attr == "system":
                        func_name = "os.system"
                        is_injection_risk = True
                    elif node.func.value.id == "subprocess" and node.func.attr in SUBPROCESS_FUNCS:
                        # Check for shell=True keyword argument
                        for kw in node.keywords:
                            if kw.arg == "shell":
                                if (isinstance(kw.value, ast.Constant) and kw.value.value is True) or \
                                   (isinstance(kw.value, ast.Name) and kw.value.id == "True"):
                                    func_name = f"subprocess.{node.func.attr}"
                                    is_injection_risk = True
                                    break
                
                # Check for direct imports: from subprocess import run
                elif isinstance(node.func, ast.Name):
                    if node.func.id in SUBPROCESS_FUNCS:
                        for kw in node.keywords:
                            if kw.arg == "shell":
                                if (isinstance(kw.value, ast.Constant) and kw.value.value is True) or \
                                   (isinstance(kw.value, ast.Name) and kw.value.id == "True"):
                                    func_name = node.func.id
                                    is_injection_risk = True
                                    break

                if is_injection_risk:
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
                        description=f"Potential command injection risk in call to '{func_name}()' with shell=True or direct shell execution.",
                        recommendation="Avoid running shell commands with raw string formatting or shell=True. Pass arguments as a list of strings instead, or use safe APIs."
                    ))

        return findings
