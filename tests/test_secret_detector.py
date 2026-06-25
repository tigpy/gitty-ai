import ast
from libs.events.schemas import Severity
from services.security_service.domain.rules.hardcoded_secret_rule import HardcodedSecretRule

def test_hardcoded_secret_detection_ast():
    rule = HardcodedSecretRule()
    file_path = "test_secrets.py"
    
    # Positive cases
    content = """
API_KEY = "sk-admin12345"
aws_secret_access_key = "abcde12345fghij"
password = "supersecretpassword"
"""
    tree = ast.parse(content)
    findings = rule.evaluate(tree, content, file_path)
    
    finding_names = {f.code_snippet for f in findings}
    assert len(findings) == 3
    assert any("API_KEY" in s for s in finding_names)
    assert any("aws_secret_access_key" in s for s in finding_names)
    assert any("password" in s for s in finding_names)
    
    for f in findings:
        assert f.severity == Severity.HIGH
        assert f.cwe_id == "CWE-798"
        assert f.owasp_category == "A01:2021-Broken Access Control"

def test_hardcoded_secret_detection_placeholders():
    rule = HardcodedSecretRule()
    file_path = "test_secrets.py"
    
    # Placeholders should be skipped
    content = """
API_KEY = "sk-xxxxxxx"
password = "your_password"
aws_secret_access_key = "placeholder"
token = ""
"""
    tree = ast.parse(content)
    findings = rule.evaluate(tree, content, file_path)
    assert len(findings) == 0

def test_hardcoded_secret_detection_regex():
    rule = HardcodedSecretRule()
    file_path = "test_secrets.py"
    
    # Matches inside comments or non-AST formats using regex
    content = "# The db password = 'actual_password_123' in settings"
    tree = ast.parse(content)
    findings = rule.evaluate(tree, content, file_path)
    
    assert len(findings) == 1
    assert "password" in findings[0].code_snippet
    assert findings[0].line_number == 1
