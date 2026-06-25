import os
import ast
import pytest
from typing import Any
from unittest.mock import MagicMock
from libs.events.schemas import Severity
from services.security_service.domain.rules.dependency_risk_rule import DependencyRiskRule
from services.security_service.application.security_analysis_service import SecurityAnalysisService
from services.security_service.application.risk_scoring import calculate_security_score

class MockEventBus:
    def __init__(self):
        self.published = []

    def publish(self, topic: str, event: Any) -> None:
        self.published.append((topic, event))

# Need simple class to let Pydantic / typing work inside MockEventBus
from typing import Any

def test_dependency_risk_rule():
    rule = DependencyRiskRule()
    file_path = "requirements.txt"
    
    content = """
# Dependencies
requests==2.28.1
pyyaml<5.4
urllib3>=1.26.0
Django==4.2.1 # secure
"""
    findings = rule.evaluate(ast.parse(""), content, file_path)
    assert len(findings) == 3
    
    finding_packages = {f.code_snippet for f in findings}
    assert any("requests==2.28.1" in s for s in finding_packages)
    assert any("pyyaml<5.4" in s for s in finding_packages)
    assert any("urllib3>=1.26.0" in s for s in finding_packages)
    assert not any("Django" in s for s in finding_packages)
    
    for f in findings:
        assert f.cwe_id in ("CWE-1395", "CWE-502")
        assert f.owasp_category in ("A06:2021-Vulnerable and Outdated Components", "A08:2021-Software and Data Integrity Failures")

def test_risk_scoring():
    from services.security_service.domain.entities.security_finding import SecurityFinding
    # Deductions: Critical (-20), High (-10), Medium (-5), Low (-2)
    findings = [
        SecurityFinding(
            id="f1", rule_id="R1", severity=Severity.CRITICAL, confidence="HIGH",
            file_path="a.py", line_number=1, code_snippet="os.system()",
            description="", recommendation=""
        ),
        SecurityFinding(
            id="f2", rule_id="R2", severity=Severity.HIGH, confidence="HIGH",
            file_path="a.py", line_number=2, code_snippet="eval()",
            description="", recommendation=""
        ),
        SecurityFinding(
            id="f3", rule_id="R3", severity=Severity.MEDIUM, confidence="HIGH",
            file_path="a.py", line_number=3, code_snippet="hashlib.md5()",
            description="", recommendation=""
        ),
        SecurityFinding(
            id="f4", rule_id="R4", severity=Severity.LOW, confidence="HIGH",
            file_path="a.py", line_number=4, code_snippet="DEBUG = True",
            description="", recommendation=""
        ),
    ]
    
    # 100 - 20 - 10 - 5 - 2 = 63
    score = calculate_security_score(findings)
    assert score == 63

def test_security_analysis_service_orchestration(tmp_path):
    # Setup mock files
    repo_dir = tmp_path / "mock_repo"
    repo_dir.mkdir()
    
    # vulnerable python file
    f1 = repo_dir / "vuln.py"
    f1.write_text("""
API_KEY = "sk-secret12345"
eval("x")
""", encoding="utf-8")
    
    # requirements file
    f2 = repo_dir / "requirements.txt"
    f2.write_text("requests==2.28.1\n", encoding="utf-8")
    
    # Mock Repository
    mock_repo = MagicMock()
    repo_id = "test-sec-repo"
    mock_repo.get_nodes_by_repository.return_value = [
        {"type": "Repository", "id": repo_id, "name": "test_sec_repo", "path": str(repo_dir)},
        {"type": "File", "id": "f1_node", "name": "vuln.py", "path": "vuln.py"},
        {"type": "File", "id": "f2_node", "name": "requirements.txt", "path": "requirements.txt"}
    ]
    
    publisher = MockEventBus()
    service = SecurityAnalysisService(mock_repo, publisher=publisher)
    report = service.run_security_scan(repo_id)
    
    # Findings: Hardcoded secret (HIGH), eval (HIGH), requests dependency (HIGH)
    # Deductions: 3 * 10 = 30 -> Score 70
    assert report.critical_count == 0
    assert report.high_count == 3
    assert report.security_score == 70
    
    # Check published events
    topics = [t for t, e in publisher.published]
    assert "security.issue_detected" in topics
    assert "security.scan_completed" in topics
    assert len(topics) == 4 # 3 findings + 1 completed event
    
    comp_event = next(e for t, e in publisher.published if t == "security.scan_completed")
    assert comp_event.security_score == 70
    assert comp_event.summary["HIGH"] == 3
