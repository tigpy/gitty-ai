import ast
from libs.events.schemas import Severity
from services.security_service.domain.rules.weak_crypto_rule import WeakCryptoRule

def test_weak_crypto_hashlib_attributes():
    rule = WeakCryptoRule()
    file_path = "test_crypto.py"
    
    content = """
import hashlib
h1 = hashlib.md5(b"test").hexdigest()
h2 = hashlib.sha1(b"test").hexdigest()
h3 = hashlib.sha256(b"test").hexdigest() # secure
"""
    tree = ast.parse(content)
    findings = rule.evaluate(tree, content, file_path)
    
    finding_snippets = {f.code_snippet for f in findings}
    assert len(findings) == 2
    assert any("hashlib.md5" in s for s in finding_snippets)
    assert any("hashlib.sha1" in s for s in finding_snippets)
    assert not any("sha256" in s for s in finding_snippets)
    
    for f in findings:
        assert f.severity == Severity.MEDIUM
        assert f.cwe_id == "CWE-327"
        assert f.owasp_category == "A02:2021-Cryptographic Failures"

def test_weak_crypto_imports_and_direct_calls():
    rule = WeakCryptoRule()
    file_path = "test_crypto.py"
    
    content = """
from hashlib import md5
from Crypto.Cipher import DES

h = md5(b"test")
cipher = DES.new(key, DES.MODE_ECB)
"""
    tree = ast.parse(content)
    findings = rule.evaluate(tree, content, file_path)
    
    finding_rules = [f.code_snippet for f in findings]
    assert len(findings) >= 2
    assert any("md5" in s for s in finding_rules)
    assert any("DES.new" in s or "DES" in s for s in finding_rules)
