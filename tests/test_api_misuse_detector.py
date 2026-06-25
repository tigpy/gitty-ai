import ast
from libs.events.schemas import Severity
from services.security_service.domain.rules.eval_rule import EvalRule
from services.security_service.domain.rules.pickle_rule import PickleRule
from services.security_service.domain.rules.subprocess_rule import SubprocessRule
from services.security_service.domain.rules.debug_config_rule import DebugConfigRule

def test_eval_exec_detection():
    rule = EvalRule()
    content = """
eval("x + 1")
exec("import os")
compile("y = 1", "<string>", "exec")
print("hello") # safe
"""
    tree = ast.parse(content)
    findings = rule.evaluate(tree, content, "app.py")
    assert len(findings) == 3
    assert any("eval" in f.code_snippet for f in findings)
    assert any("exec" in f.code_snippet for f in findings)
    assert any("compile" in f.code_snippet for f in findings)

def test_pickle_deserialization_detection():
    rule = PickleRule()
    content = """
import pickle
import yaml
import marshal

pickle.loads(b"data")
marshal.loads(b"data")
yaml.load("data") # unsafe without SafeLoader
yaml.load("data", Loader=yaml.SafeLoader) # safe
"""
    tree = ast.parse(content)
    findings = rule.evaluate(tree, content, "app.py")
    assert len(findings) == 3
    
    finding_snippets = [f.code_snippet for f in findings]
    assert any("pickle.loads" in s for s in finding_snippets)
    assert any("marshal.loads" in s for s in finding_snippets)
    assert any('yaml.load("data")' in s for s in finding_snippets)
    assert not any("yaml.SafeLoader" in s for s in finding_snippets)

def test_subprocess_command_injection_detection():
    rule = SubprocessRule()
    content = """
import os
import subprocess

os.system("ls")
subprocess.run("ls", shell=True)
subprocess.Popen(["ls"], shell=True)
subprocess.run(["ls", "-l"]) # safe (shell=False by default)
"""
    tree = ast.parse(content)
    findings = rule.evaluate(tree, content, "app.py")
    assert len(findings) == 3
    
    finding_snippets = [f.code_snippet for f in findings]
    assert any("os.system" in s for s in finding_snippets)
    assert any('subprocess.run("ls", shell=True)' in s for s in finding_snippets)
    assert any('subprocess.Popen(["ls"], shell=True)' in s for s in finding_snippets)
    assert not any('subprocess.run(["ls", "-l"])' in s for s in finding_snippets)
    
    for f in findings:
        assert f.severity == Severity.CRITICAL

def test_debug_config_detection():
    rule = DebugConfigRule()
    content = """
DEBUG = True
app.run(debug=True)
run(host="localhost", debug=True)
DEBUG = False # safe
"""
    tree = ast.parse(content)
    findings = rule.evaluate(tree, content, "config.py")
    assert len(findings) == 3
    
    finding_snippets = [f.code_snippet for f in findings]
    assert any("DEBUG = True" in s for s in finding_snippets)
    assert any("app.run(debug=True)" in s for s in finding_snippets)
    assert any("run(host=\"localhost\", debug=True)" in s for s in finding_snippets)
    assert not any("DEBUG = False" in s for s in finding_snippets)
