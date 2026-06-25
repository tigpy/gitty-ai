import ast
import hashlib
from typing import List
from libs.events.schemas import Severity
from .base_rule import SecurityRule
from ..entities.security_finding import SecurityFinding

WEAK_ALGS = {"md5", "sha1"}

class WeakCryptoRule(SecurityRule):
    @property
    def id(self) -> str:
        return "WEAK_CRYPTO"

    @property
    def name(self) -> str:
        return "Weak Cryptography Detection"

    @property
    def severity(self) -> Severity:
        return Severity.MEDIUM

    @property
    def cwe_id(self) -> str:
        return "CWE-327"

    @property
    def owasp_category(self) -> str:
        return "A02:2021-Cryptographic Failures"

    def evaluate(self, tree: ast.AST, file_content: str, file_path: str) -> List[SecurityFinding]:
        findings = []
        lines = file_content.splitlines()

        # Track imports to resolve directly called weak crypto functions
        imported_weak_cryptos = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.module == "hashlib":
                    for name in node.names:
                        if name.name in WEAK_ALGS:
                            imported_weak_cryptos.add(name.asname or name.name)
                elif node.module in ("Crypto.Cipher", "Cryptodome.Cipher", "cryptography.hazmat.primitives.ciphers.algorithms"):
                    for name in node.names:
                        if name.name == "DES":
                            imported_weak_cryptos.add(name.asname or name.name)

        for node in ast.walk(tree):
            # 1. Check imports themselves as a minor finding or indicator
            if isinstance(node, ast.Import):
                for name in node.names:
                    if name.name == "DES":
                        line_idx = node.lineno - 1
                        snippet = lines[line_idx] if line_idx < len(lines) else ""
                        finding_id = hashlib.sha256(f"{file_path}:{node.lineno}:{self.id}:import_des".encode()).hexdigest()
                        findings.append(SecurityFinding(
                            id=finding_id,
                            rule_id=self.id,
                            severity=self.severity,
                            cwe_id=self.cwe_id,
                            owasp_category=self.owasp_category,
                            confidence="MEDIUM",
                            file_path=file_path,
                            line_number=node.lineno,
                            code_snippet=snippet.strip(),
                            description="Import of weak/broken cryptographic cipher 'DES'.",
                            recommendation="Replace 'DES' with a secure cipher such as AES (Advanced Encryption Standard)."
                        ))

            # 2. Check function calls
            if isinstance(node, ast.Call):
                func_name = None
                is_weak = False
                
                # Check for hashlib.md5() or hashlib.sha1() or DES.new()
                if isinstance(node.func, ast.Attribute):
                    if isinstance(node.func.value, ast.Name):
                        full_name = f"{node.func.value.id}.{node.func.attr}"
                        if full_name in ("hashlib.md5", "hashlib.sha1", "DES.new", "DES.new_cipher"):
                            func_name = full_name
                            is_weak = True
                # Check for direct calls to imported names
                elif isinstance(node.func, ast.Name):
                    if node.func.id in imported_weak_cryptos or node.func.id in ("md5", "sha1", "DES"):
                        func_name = node.func.id
                        is_weak = True

                if is_weak:
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
                        description=f"Use of weak/broken cryptographic algorithm/cipher '{func_name}()'.",
                        recommendation="Use secure hashing algorithms like SHA-256 or SHA-3, and secure symmetric ciphers like AES."
                    ))

        return findings
