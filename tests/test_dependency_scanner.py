import json
import os

import pytest

from services.security_service.application.dependency_scanner import (
    query_generation,
    scan_dependencies,
)
from services.security_service.application.security_analysis_service import SecurityAnalysisService


def _osv(vulns_by_key=None, fail=None):
    calls = []
    fail = set(fail or [])

    def query(name, ecosystem, version):
        calls.append((name, ecosystem, version))
        if (ecosystem, name) in fail or name in fail:
            return "unavailable", [], "timeout"
        payload = (vulns_by_key or {}).get((ecosystem, name, version), [])
        return "succeeded", payload, None

    query.calls = calls
    return query


def _write(root, relative, text):
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def test_requirements_pyproject_and_constraints(tmp_path):
    _write(tmp_path, "requirements.txt", "requests[security]==2.28.1\nDjango>=4.2\n# comment\n")
    _write(
        tmp_path,
        "pyproject.toml",
        '[project]\ndependencies = [\n  "flask==2.2.0",\n  "httpx>=0.24",\n]\n',
    )
    _write(tmp_path, "requirements/dev.txt", "pytest==7.4.0\n")
    scan = scan_dependencies(str(tmp_path), osv_query=_osv())
    found = {(item.name, item.ecosystem, item.version, item.constraint) for item in scan.dependencies}
    assert ("requests", "PyPI", "2.28.1", "==2.28.1") in found
    assert ("Django", "PyPI", None, ">=4.2") in found
    assert ("flask", "PyPI", "2.2.0", "==2.2.0") in found
    assert ("httpx", "PyPI", None, ">=0.24") in found
    assert ("pytest", "PyPI", "7.4.0", "==7.4.0") in found
    assert any(item.name == "requests" and item.manifest_path == "requirements.txt" for item in scan.dependencies)


def test_package_json_lock_maven_and_ecosystems(tmp_path):
    _write(
        tmp_path,
        "package.json",
        json.dumps({"dependencies": {"lodash": "^4.17.15"}, "devDependencies": {"left-pad": "1.0.0"}}),
    )
    _write(
        tmp_path,
        "package-lock.json",
        json.dumps({
            "packages": {
                "": {"name": "app", "version": "1.0.0"},
                "node_modules/lodash": {"version": "4.17.21"},
                "node_modules/left-pad": {"version": "1.0.0"},
                "node_modules/lodash/node_modules/nested-dep": {"version": "0.1.0"},
            }
        }),
    )
    _write(
        tmp_path,
        "pom.xml",
        """<project>
          <dependencyManagement><dependencies>
            <dependency><groupId>org.example</groupId><artifactId>bom</artifactId><version>1.0.0</version></dependency>
          </dependencies></dependencyManagement>
          <dependencies>
            <dependency><groupId>org.apache.logging.log4j</groupId><artifactId>log4j-core</artifactId><version>2.14.1</version></dependency>
          </dependencies>
        </project>""",
    )
    _write(tmp_path, "build.gradle", 'implementation "com.google.guava:guava:31.1-jre"\n')
    scan = scan_dependencies(str(tmp_path), osv_query=_osv())
    by_name = {item.name: item for item in scan.dependencies}
    assert by_name["lodash"].ecosystem == "npm"
    assert by_name["lodash"].version == "4.17.21"
    assert by_name["lodash"].constraint == "^4.17.15"
    assert by_name["lodash"].dependency_type == "direct"
    assert by_name["left-pad"].version == "1.0.0"
    assert by_name["nested-dep"].dependency_type == "transitive"
    assert by_name["org.apache.logging.log4j:log4j-core"].ecosystem == "Maven"
    assert by_name["org.apache.logging.log4j:log4j-core"].version == "2.14.1"
    assert by_name["com.google.guava:guava"].version == "31.1-jre"
    assert "org.example:bom" not in by_name


def test_lockfile_priority_dedup_and_query_shape(tmp_path):
    _write(tmp_path, "pyproject.toml", '[project]\ndependencies = ["requests>=2.0", "flask==2.0.0"]\n')
    _write(
        tmp_path,
        "poetry.lock",
        '[[package]]\nname = "requests"\nversion = "2.31.0"\ncategory = "main"\n\n'
        '[[package]]\nname = "urllib3"\nversion = "1.26.18"\ncategory = "main"\n',
    )
    query = _osv()
    scan = scan_dependencies(str(tmp_path), osv_query=query)
    requests = [item for item in scan.dependencies if item.name == "requests"]
    assert len(requests) == 1
    assert requests[0].version == "2.31.0"
    assert requests[0].constraint == ">=2.0"
    assert requests[0].dependency_type == "direct"
    urllib = next(item for item in scan.dependencies if item.name == "urllib3")
    assert urllib.dependency_type == "transitive"
    assert query_generation("lodash", "npm", "4.17.21") == {
        "package": {"name": "lodash", "ecosystem": "npm"},
        "version": "4.17.21",
    }
    assert query_generation("org.apache.logging.log4j:log4j-core", "Maven", "2.14.1")["package"]["ecosystem"] == "Maven"
    assert ("flask", "PyPI", "2.0.0") in query.calls
    assert ("urllib3", "PyPI", "1.26.18") in query.calls
    assert query.calls.count(("requests", "PyPI", "2.31.0")) == 1


def test_vulnerable_clean_unknown_and_severity_are_not_invented(tmp_path):
    _write(tmp_path, "package.json", json.dumps({"dependencies": {"lodash": "4.17.20", "left-pad": "1.0.0", "missing": "9.9.9"}}))
    query = _osv({
        ("npm", "lodash", "4.17.20"): [{
            "id": "GHSA-test",
            "summary": "Prototype pollution",
            "references": [{"url": "https://example.test/ghsa"}],
            "affected": [{"ranges": [{"events": [{"fixed": "4.17.21"}]}]}],
            "database_specific": {"severity": "HIGH"},
        }],
        ("npm", "left-pad", "1.0.0"): [],
        ("npm", "missing", "9.9.9"): [],
    })
    scan = scan_dependencies(str(tmp_path), osv_query=query)
    assert scan.lookup_status == "succeeded"
    assert len(scan.vulnerabilities) == 1
    vuln = scan.vulnerabilities[0]
    assert vuln.vuln_id == "GHSA-test"
    assert vuln.severity == "HIGH"
    assert vuln.fixed_in == ["4.17.21"]
    assert vuln.references == ["https://example.test/ghsa"]
    no_severity = {
        "id": "GHSA-nosev",
        "summary": "No severity field",
    }
    _write(tmp_path, "requirements.txt", "")
    scan2 = scan_dependencies(str(tmp_path), osv_query=_osv({
        ("npm", "lodash", "4.17.20"): [no_severity],
        ("npm", "left-pad", "1.0.0"): [],
        ("npm", "missing", "9.9.9"): [],
    }))
    unlabeled = next(item for item in scan2.vulnerabilities if item.vuln_id == "GHSA-nosev")
    assert unlabeled.severity is None
    finding = next(item for item in scan2.to_findings() if item.cwe_id == "GHSA-nosev")
    assert finding.severity.value == "INFO"


def test_malformed_unsupported_and_lookup_failure_are_not_clean(tmp_path):
    _write(tmp_path, "package.json", "{")
    _write(tmp_path, "Cargo.toml", "[package]\nname='x'\n")
    _write(tmp_path, "requirements.txt", "flask==1.0.0\nnot a requirement !!!\n")
    query = _osv(fail={"flask"})
    scan = scan_dependencies(str(tmp_path), osv_query=query)
    assert any("package.json" in error for error in scan.parse_errors)
    assert "Cargo.toml" in scan.unsupported
    assert scan.lookup_status == "unavailable"
    assert scan.vulnerabilities == []
    rules = {item.rule_id for item in scan.to_findings()}
    assert "DEPENDENCY_LOOKUP_UNAVAILABLE" in rules
    assert "DEPENDENCY_MANIFEST_ERROR" in rules
    assert scan.lookup_status != "succeeded"

    partial = scan_dependencies(str(tmp_path), osv_query=_osv(
        vulns_by_key={("PyPI", "flask", "1.0.0"): [{"id": "PYSEC-1", "summary": "demo", "database_specific": {"severity": "LOW"}}]},
        fail={"other"},
    ))
    _write(tmp_path, "requirements.txt", "flask==1.0.0\n")
    _write(tmp_path, "pyproject.toml", '[project]\ndependencies=["other==1.2.3"]\n')
    partial = scan_dependencies(str(tmp_path), osv_query=_osv(
        vulns_by_key={("PyPI", "flask", "1.0.0"): [{"id": "PYSEC-1", "summary": "demo", "database_specific": {"severity": "LOW"}}]},
        fail={"other"},
    ))
    assert partial.lookup_status == "partial"
    assert any(item.vuln_id == "PYSEC-1" for item in partial.vulnerabilities)
    assert partial.lookup_errors


def test_repository_boundary_and_no_command_execution(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    outside = tmp_path / "outside"
    repo.mkdir()
    outside.mkdir()
    (outside / "requirements.txt").write_text("secretpkg==1.2.3\n", encoding="utf-8")
    (repo / "requirements.txt").write_text("-r ../outside/requirements.txt\nsafe==1.0.0\n", encoding="utf-8")
    (repo / "requirements").mkdir()
    os.symlink(outside / "requirements.txt", repo / "requirements" / "linked.txt")

    def explode(*_args, **_kwargs):
        raise AssertionError("dependency scanning must not execute a process")

    monkeypatch.setattr("subprocess.run", explode, raising=False)
    monkeypatch.setattr(os, "system", explode)
    scan = scan_dependencies(str(repo), osv_query=_osv())
    names = {item.name for item in scan.dependencies}
    assert "safe" in names
    assert "secretpkg" not in names
    assert all("outside" not in item.manifest_path for item in scan.dependencies)


def test_security_scan_uses_repository_manifests_without_double_counting(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "vuln.py").write_text('API_KEY = "sk-secret12345"\neval("x")\n', encoding="utf-8")
    (repo / "requirements.txt").write_text("requests==2.28.1\n", encoding="utf-8")
    (repo / "package.json").write_text(json.dumps({"dependencies": {"lodash": "^4.17.15"}}), encoding="utf-8")
    repository = type("Repo", (), {})()
    repository.get_nodes_by_repository = lambda _repo_id: [
        {"type": "Repository", "id": "repo-1", "name": "repo", "path": str(repo)},
        {"type": "File", "id": "py", "name": "vuln.py", "path": "vuln.py"},
        {"type": "File", "id": "req", "name": "requirements.txt", "path": "requirements.txt"},
    ]
    service = SecurityAnalysisService(repository)
    report = service.run_security_scan("repo-1")
    dependency_findings = [item for item in report.findings if item.rule_id == "DEPENDENCY_RISK"]
    assert any("requests" in item.code_snippet for item in dependency_findings)
    assert len([item for item in dependency_findings if "requests" in item.code_snippet]) == 1


def test_empty_repository_is_not_a_false_vulnerability_result(tmp_path):
    scan = scan_dependencies(str(tmp_path), osv_query=_osv())
    assert scan.lookup_status == "no_manifests"
    assert scan.dependencies == []
    assert scan.vulnerabilities == []
    assert scan.to_findings() == []
