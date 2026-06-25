import os
import ast
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional
from libs.events.schemas import (
    Severity, 
    SecurityIssueDetectedV1, 
    CriticalSecurityFindingV1, 
    SecurityScanCompletedV1
)
from libs.core.message_bus.interfaces.event_bus import IEventBus
from ..domain.entities.security_finding import SecurityFinding
from ..domain.entities.security_report import SecurityReport
from ..domain.rules.hardcoded_secret_rule import HardcodedSecretRule
from ..domain.rules.eval_rule import EvalRule
from ..domain.rules.weak_crypto_rule import WeakCryptoRule
from ..domain.rules.pickle_rule import PickleRule
from ..domain.rules.subprocess_rule import SubprocessRule
from ..domain.rules.debug_config_rule import DebugConfigRule
from ..domain.rules.dependency_risk_rule import DependencyRiskRule
from .risk_scoring import calculate_security_score

class SecurityAnalysisService:
    def __init__(self, repository: Any, publisher: Optional[IEventBus] = None):
        self.repository = repository
        self.publisher = publisher
        self.rules = [
            HardcodedSecretRule(),
            EvalRule(),
            WeakCryptoRule(),
            PickleRule(),
            SubprocessRule(),
            DebugConfigRule(),
            DependencyRiskRule()
        ]

    def run_security_scan(self, repo_id: str) -> SecurityReport:
        """
        Runs the security scan on all files in the repository.
        Reads file contents, parses AST, runs rules, calculates score, and publishes events.
        """
        nodes = self.repository.get_nodes_by_repository(repo_id)
        
        # 1. Locate repository node to find root directory path
        repo_node = next((n for n in nodes if n["type"] == "Repository"), None)
        repo_path = repo_node.get("path", "") if repo_node else ""
        repo_name = repo_node.get("name", "unknown") if repo_node else "unknown"

        # Collect all file nodes (and also look for requirements.txt in the repo path if not indexed)
        file_nodes = [n for n in nodes if n["type"] == "File"]
        file_paths = {f.get("path") for f in file_nodes}

        # Include requirements.txt if present in the folder but not in the indexed nodes
        req_txt_path = "requirements.txt"
        if req_txt_path not in file_paths:
            if repo_path and os.path.exists(os.path.join(repo_path, req_txt_path)):
                file_paths.add(req_txt_path)

        all_findings: List[SecurityFinding] = []

        # 2. Scan each file
        for f_path in file_paths:
            abs_path = os.path.join(repo_path, f_path) if repo_path else f_path
            if not os.path.exists(abs_path):
                continue
                
            if repo_path:
                real_root = os.path.normcase(os.path.realpath(repo_path))
                real_file = os.path.normcase(os.path.realpath(abs_path))
                if not (real_file == real_root or real_file.startswith(real_root + os.path.sep)):
                    continue

            try:
                with open(abs_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
            except Exception:
                continue

            try:
                tree = ast.parse(content)
            except SyntaxError:
                # Use empty AST tree for non-python files (e.g. requirements.txt)
                tree = ast.Module(body=[], type_ignores=[])

            # Run all rules
            for rule in self.rules:
                try:
                    findings = rule.evaluate(tree, content, f_path)
                    all_findings.extend(findings)
                except Exception:
                    # Robust execution: don't let one rule failure crash the service
                    continue

        # 3. Calculate metrics
        critical_count = sum(1 for f in all_findings if f.severity == Severity.CRITICAL)
        high_count = sum(1 for f in all_findings if f.severity == Severity.HIGH)
        medium_count = sum(1 for f in all_findings if f.severity == Severity.MEDIUM)
        low_count = sum(1 for f in all_findings if f.severity == Severity.LOW)
        info_count = sum(1 for f in all_findings if f.severity == Severity.INFO)

        score = calculate_security_score(all_findings)

        report = SecurityReport(
            repository_id=repo_id,
            critical_count=critical_count,
            high_count=high_count,
            medium_count=medium_count,
            low_count=low_count,
            info_count=info_count,
            security_score=score,
            findings=all_findings
        )

        # 4. Publish Events via Message Bus
        if self.publisher:
            # Publish individual findings
            for finding in all_findings:
                issue_event = SecurityIssueDetectedV1(
                    event_id=str(uuid.uuid4()),
                    timestamp=datetime.now(timezone.utc),
                    repository_id=repo_id,
                    finding_id=finding.id,
                    rule_id=finding.rule_id,
                    severity=finding.severity,
                    cwe_id=finding.cwe_id,
                    owasp_category=finding.owasp_category,
                    confidence=finding.confidence,
                    file_path=finding.file_path,
                    line_number=finding.line_number,
                    description=finding.description
                )
                self.publisher.publish("security.issue_detected", issue_event)

                if finding.severity == Severity.CRITICAL:
                    crit_event = CriticalSecurityFindingV1(
                        event_id=str(uuid.uuid4()),
                        timestamp=datetime.now(timezone.utc),
                        repository_id=repo_id,
                        finding_id=finding.id,
                        rule_id=finding.rule_id,
                        cwe_id=finding.cwe_id,
                        file_path=finding.file_path,
                        line_number=finding.line_number,
                        description=finding.description
                    )
                    self.publisher.publish("security.critical_finding", crit_event)

            # Publish scan completed
            scan_completed = SecurityScanCompletedV1(
                event_id=str(uuid.uuid4()),
                timestamp=datetime.now(timezone.utc),
                repository_id=repo_id,
                scan_timestamp=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                security_score=score,
                summary={
                    "CRITICAL": critical_count,
                    "HIGH": high_count,
                    "MEDIUM": medium_count,
                    "LOW": low_count,
                    "INFO": info_count
                }
            )
            self.publisher.publish("security.scan_completed", scan_completed)

        return report
