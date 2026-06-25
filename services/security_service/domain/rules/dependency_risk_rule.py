import ast
import re
import hashlib
from typing import List
from libs.events.schemas import Severity
from .base_rule import SecurityRule
from ..entities.security_finding import SecurityFinding
from ...infrastructure.vulnerability_db import VulnerabilityDB

# Regex to capture package name, operator, and version
# e.g., requests==2.28.1, pyyaml<=5.4
DEP_PATTERN = re.compile(r'^([a-zA-Z0-9_\-\[\]]+)\s*(==|<=|>=|<|>)\s*([0-9a-zA-Z\.\-]+)')

class DependencyRiskRule(SecurityRule):
    @property
    def id(self) -> str:
        return "DEPENDENCY_RISK"

    @property
    def name(self) -> str:
        return "Dependency Risk Detection"

    @property
    def severity(self) -> Severity:
        return Severity.MEDIUM

    @property
    def cwe_id(self) -> str:
        return "CWE-1395"

    @property
    def owasp_category(self) -> str:
        return "A06:2021-Vulnerable and Outdated Components"

    def evaluate(self, tree: ast.AST, file_content: str, file_path: str) -> List[SecurityFinding]:
        findings = []
        
        # Only analyze requirements.txt files
        if not file_path.endswith("requirements.txt"):
            return findings

        lines = file_content.splitlines()
        for idx, line in enumerate(lines):
            line_no = idx + 1
            clean_line = line.strip()
            
            # Skip comments or empty lines
            if not clean_line or clean_line.startswith("#"):
                continue

            match = DEP_PATTERN.match(clean_line)
            if match:
                package = match.group(1)
                operator = match.group(2)
                version_str = match.group(3)

                vuln = VulnerabilityDB.check_vulnerability(package, operator, version_str)
                if vuln:
                    finding_id = hashlib.sha256(f"{file_path}:{line_no}:{self.id}:{package}".encode()).hexdigest()
                    findings.append(SecurityFinding(
                        id=finding_id,
                        rule_id=self.id,
                        severity=vuln["severity"],
                        cwe_id=vuln.get("cwe_id", self.cwe_id),
                        owasp_category=self.owasp_category,
                        confidence="HIGH",
                        file_path=file_path,
                        line_number=line_no,
                        code_snippet=clean_line,
                        description=f"Package '{package}' (version {version_str}) has a known vulnerability: {vuln['description']}",
                        recommendation=f"Upgrade '{package}' to version {vuln['version']} or newer."
                    ))

        return findings
