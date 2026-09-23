"""Static dependency discovery and OSV lookup.

Manifests are parsed as data. Package managers are never executed. A failed
vulnerability lookup is reported as unavailable, not as a clean scan.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple

from libs.events.schemas import Severity
from ..domain.entities.security_finding import SecurityFinding
from ..infrastructure.vulnerability_db import VulnerabilityDB

OSV_QUERY_URL = "https://api.osv.dev/v1/query"
OSV_QUERY_BATCH_URL = "https://api.osv.dev/v1/querybatch"
MAX_MANIFEST_BYTES = 2_000_000
MAX_MANIFESTS = 200
SKIP_DIRECTORIES = {
    ".git",
    ".hg",
    ".svn",
    "node_modules",
    "venv",
    ".venv",
    "dist",
    "build",
    "__pycache__",
    "site-packages",
}
MANIFEST_NAMES = {
    "requirements.txt",
    "pyproject.toml",
    "pipfile",
    "poetry.lock",
    "uv.lock",
    "package.json",
    "package-lock.json",
    "npm-shrinkwrap.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "pom.xml",
    "build.gradle",
    "build.gradle.kts",
    "gradle.lockfile",
}
UNSUPPORTED_NAMES = {
    "cargo.toml",
    "go.mod",
    "gemfile",
    "composer.json",
    "packages.config",
    "podfile",
}
LOCKFILE_NAMES = {
    "poetry.lock",
    "uv.lock",
    "package-lock.json",
    "npm-shrinkwrap.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "gradle.lockfile",
}
_REQ_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.\-]*")
_REQ_SPEC = re.compile(
    r"^(?P<name>[A-Za-z0-9][A-Za-z0-9_.\-]*)"
    r"(?:\[[^\]]+\])?"
    r"\s*(?P<op>===|==|~=|!=|>=|<=|>|<)?\s*"
    r"(?P<version>[A-Za-z0-9][A-Za-z0-9.*+\-]*)?"
)
_GRADLE_DEP = re.compile(
    r"""(?:implementation|api|compileOnly|runtimeOnly|compile|runtime)\s*\(?\s*['\"]([^'\"]+)['\"]"""
)
_YARN_VERSION = re.compile(r'^\s+version\s+"([^"]+)"')
_PNPM_PACKAGE = re.compile(
    r"""^\s+['\"]?(?:/)?(@?[^'\":\s@]+)@([^'\":\s(]+)['\"]?\s*:\s*$"""
)


@dataclass
class Dependency:
    name: str
    ecosystem: str
    manifest_path: str
    version: Optional[str] = None
    constraint: Optional[str] = None
    dependency_type: str = "direct"
    source_kind: str = "manifest"
    line_number: int = 1

    @property
    def identity(self) -> str:
        return f"{self.ecosystem}:{_normalize_name(self.ecosystem, self.name)}"


@dataclass
class Vulnerability:
    dependency: Dependency
    vuln_id: str
    summary: Optional[str] = None
    severity: Optional[str] = None
    severity_vector: Optional[str] = None
    references: List[str] = field(default_factory=list)
    affected: List[str] = field(default_factory=list)
    fixed_in: List[str] = field(default_factory=list)
    source: str = "OSV"


@dataclass
class DependencyScan:
    manifests: List[str] = field(default_factory=list)
    dependencies: List[Dependency] = field(default_factory=list)
    vulnerabilities: List[Vulnerability] = field(default_factory=list)
    parse_errors: List[str] = field(default_factory=list)
    unsupported: List[str] = field(default_factory=list)
    lookup_errors: List[str] = field(default_factory=list)
    lookup_status: str = "no_manifests"

    def to_findings(self) -> List[SecurityFinding]:
        findings: List[SecurityFinding] = []
        for vuln in self.vulnerabilities:
            dep = vuln.dependency
            severity = _severity_or_info(vuln.severity)
            version_text = dep.version or dep.constraint or "unspecified"
            summary = vuln.summary or "No summary provided by the advisory."
            fixed = f" Fixed in: {', '.join(vuln.fixed_in)}." if vuln.fixed_in else ""
            severity_note = vuln.severity or "not provided"
            description = (
                f"Package '{dep.name}' ({dep.ecosystem} {version_text}, {dep.dependency_type}) "
                f"matches {vuln.vuln_id}. Severity: {severity_note}. {summary}{fixed}"
            )
            findings.append(_finding(
                rule_id="DEPENDENCY_RISK",
                severity=severity,
                file_path=dep.manifest_path,
                line_number=dep.line_number,
                snippet=_snippet(dep),
                description=description,
                recommendation=_recommendation(dep, vuln),
                cwe_id=vuln.vuln_id,
                token=f"{dep.manifest_path}:{dep.name}:{vuln.vuln_id}",
            ))
        for message in self.parse_errors:
            findings.append(_finding(
                rule_id="DEPENDENCY_MANIFEST_ERROR",
                severity=Severity.INFO,
                file_path=_path_from_message(message),
                line_number=1,
                snippet=message[:180],
                description=message,
                recommendation="Fix the manifest syntax. This file was not treated as vulnerability-free.",
                token=message,
            ))
        if self.lookup_status in {"unavailable", "partial"}:
            detail = "; ".join(self.lookup_errors) or "vulnerability service unavailable"
            findings.append(_finding(
                rule_id="DEPENDENCY_LOOKUP_UNAVAILABLE",
                severity=Severity.INFO,
                file_path=self.manifests[0] if self.manifests else "dependencies",
                line_number=1,
                snippet=detail[:180],
                description=(
                    "Dependency vulnerability lookup did not complete "
                    f"({self.lookup_status}). This is not a clean result. {detail}"
                ),
                recommendation="Retry the scan when the vulnerability service is reachable.",
                token=f"lookup:{self.lookup_status}:{detail}",
            ))
        return findings


OsvQuery = Callable[[str, str, str], Tuple[str, List[dict], Optional[str]]]


def scan_dependencies(repo_path: str, osv_query: Optional[OsvQuery] = None) -> DependencyScan:
    scan = DependencyScan()
    root = _validated_root(repo_path)
    if root is None:
        scan.lookup_status = "invalid_repository"
        scan.parse_errors.append(f"Repository path is not a directory: {repo_path}")
        return scan

    discovered = _discover(root)
    scan.manifests = [item[0] for item in discovered if item[1] == "supported"]
    scan.unsupported = [item[0] for item in discovered if item[1] == "unsupported"]
    parsed: List[Dependency] = []
    for relative, kind in discovered:
        if kind != "supported":
            continue
        absolute = os.path.join(root, relative)
        try:
            text = _read_manifest(root, absolute)
        except ValueError as exc:
            scan.parse_errors.append(f"{relative}: {exc}")
            continue
        try:
            parsed.extend(_parse_manifest(relative, text))
        except Exception as exc:
            scan.parse_errors.append(f"{relative}: malformed manifest ({exc.__class__.__name__})")
    scan.dependencies = _prefer_lockfiles(parsed)
    if not scan.manifests and not scan.unsupported and not scan.parse_errors:
        scan.lookup_status = "no_manifests"
        return scan

    query = osv_query or query_osv
    local_hits = 0
    attempted = 0
    failed = 0
    seen_queries = set()

    # Collect dependencies that require remote lookup
    remote_dependencies: List[Dependency] = []
    for dependency in scan.dependencies:
        local = _local_pypi_vulnerability(dependency)
        if local is not None:
            scan.vulnerabilities.append(local)
            local_hits += 1
            continue
        if not dependency.version:
            continue
        key = (dependency.ecosystem, _normalize_name(dependency.ecosystem, dependency.name), dependency.version)
        if key in seen_queries:
            continue
        seen_queries.add(key)
        remote_dependencies.append(dependency)

    # If custom osv_query is provided (e.g. via tests or caller), use individual queries
    if osv_query is not None:
        for dependency in remote_dependencies:
            query_name = _normalize_name(dependency.ecosystem, dependency.name)
            status, vulns, error = query(query_name, dependency.ecosystem, dependency.version)
            attempted += 1
            if status != "succeeded":
                failed += 1
                scan.lookup_errors.append(
                    f"{dependency.ecosystem}:{dependency.name}@{dependency.version}: {error or status}"
                )
                continue
            for raw in vulns:
                scan.vulnerabilities.append(_vulnerability_from_osv(dependency, raw))
    else:
        # Use OSV batch API in chunks of 500
        batch_size = 500
        for i in range(0, len(remote_dependencies), batch_size):
            dep_batch = remote_dependencies[i:i + batch_size]
            batch_payload = [
                {
                    "package": {
                        "name": _normalize_name(d.ecosystem, d.name),
                        "ecosystem": d.ecosystem
                    },
                    "version": d.version
                }
                for d in dep_batch
            ]
            batch_status, batch_results, batch_err = query_osv_batch(batch_payload)
            if batch_status == "succeeded" and len(batch_results) == len(dep_batch):
                for dep, vulns in zip(dep_batch, batch_results):
                    attempted += 1
                    for raw in vulns:
                        scan.vulnerabilities.append(_vulnerability_from_osv(dep, raw))
            else:
                # Controlled fallback to individual queries for this batch
                for dep in dep_batch:
                    query_name = _normalize_name(dep.ecosystem, dep.name)
                    status, vulns, error = query_osv(query_name, dep.ecosystem, dep.version)
                    attempted += 1
                    if status != "succeeded":
                        failed += 1
                        scan.lookup_errors.append(
                            f"{dep.ecosystem}:{dep.name}@{dep.version}: {error or status}"
                        )
                        continue
                    for raw in vulns:
                        scan.vulnerabilities.append(_vulnerability_from_osv(dep, raw))

    if attempted and failed == attempted and local_hits == 0:
        scan.lookup_status = "unavailable"
    elif failed:
        scan.lookup_status = "partial"
    elif attempted or local_hits:
        scan.lookup_status = "succeeded"
    elif scan.dependencies:
        scan.lookup_status = "not_queried"
    else:
        scan.lookup_status = "no_dependencies"
    return scan


def query_osv_batch(
    queries: List[Dict[str, Any]],
    timeout: float = 10.0
) -> Tuple[str, List[List[dict]], Optional[str]]:
    """Return (status, results_list, error). status is succeeded or unavailable."""
    if not queries:
        return "succeeded", [], None
    try:
        import httpx
        response = httpx.post(
            OSV_QUERY_BATCH_URL,
            json={"queries": queries},
            timeout=timeout,
        )
    except Exception as exc:
        return "unavailable", [], exc.__class__.__name__

    if response.status_code == 200:
        try:
            payload = response.json()
        except Exception:
            return "unavailable", [], "invalid JSON"
        results = payload.get("results")
        if not isinstance(results, list):
            return "unavailable", [], "unexpected OSV batch payload"

        parsed: List[List[dict]] = []
        for item in results:
            if isinstance(item, dict):
                vulns = item.get("vulns") or []
                if isinstance(vulns, list):
                    parsed.append([v for v in vulns if isinstance(v, dict)])
                else:
                    parsed.append([])
            else:
                parsed.append([])
        return "succeeded", parsed, None

    return "unavailable", [], f"HTTP {response.status_code}"


def query_osv(name: str, ecosystem: str, version: str) -> Tuple[str, List[dict], Optional[str]]:
    """Return (status, vulnerabilities, error). status is succeeded or unavailable."""
    try:
        import httpx
        response = httpx.post(
            OSV_QUERY_URL,
            json={"package": {"name": name, "ecosystem": ecosystem}, "version": version},
            timeout=5.0,
        )
    except Exception as exc:
        return "unavailable", [], exc.__class__.__name__
    if response.status_code == 200:
        try:
            payload = response.json()
        except Exception:
            return "unavailable", [], "invalid JSON"
        vulns = payload.get("vulns") or []
        if not isinstance(vulns, list):
            return "unavailable", [], "unexpected OSV payload"
        return "succeeded", [item for item in vulns if isinstance(item, dict)], None
    if response.status_code in {408, 429} or response.status_code >= 500:
        return "unavailable", [], f"HTTP {response.status_code}"
    return "unavailable", [], f"HTTP {response.status_code}"


def _validated_root(repo_path: str) -> Optional[str]:
    if not repo_path or not os.path.isdir(repo_path):
        return None
    return os.path.realpath(repo_path)


def _discover(root: str) -> List[Tuple[str, str]]:
    found: List[Tuple[str, str]] = []
    for directory, dirnames, filenames in os.walk(root, followlinks=False):
        dirnames[:] = [name for name in dirnames if name not in SKIP_DIRECTORIES]
        depth = os.path.relpath(directory, root).count(os.sep)
        if os.path.relpath(directory, root) != "." and depth > 5:
            dirnames[:] = []
            continue
        for filename in sorted(filenames):
            if len(found) >= MAX_MANIFESTS:
                return found
            relative = os.path.relpath(os.path.join(directory, filename), root).replace("\\", "/")
            lowered = filename.lower()
            parent = os.path.basename(directory).lower()
            if lowered in MANIFEST_NAMES or (parent == "requirements" and lowered.endswith(".txt")):
                found.append((relative, "supported"))
            elif lowered in UNSUPPORTED_NAMES:
                found.append((relative, "unsupported"))
    return found


def _read_manifest(root: str, absolute: str) -> str:
    real = os.path.realpath(absolute)
    if not (real == root or real.startswith(root + os.sep)):
        raise ValueError("path escapes the repository")
    if os.path.islink(absolute):
        raise ValueError("symlink manifests are not read")
    if os.path.getsize(real) > MAX_MANIFEST_BYTES:
        raise ValueError("manifest exceeds size limit")
    with open(real, "r", encoding="utf-8", errors="replace") as handle:
        return handle.read(MAX_MANIFEST_BYTES)


def _parse_manifest(relative: str, text: str) -> List[Dependency]:
    name = os.path.basename(relative).lower()
    parent = os.path.basename(os.path.dirname(relative)).lower()
    if name == "requirements.txt" or (parent == "requirements" and name.endswith(".txt")):
        return _parse_requirements(relative, text)
    if name == "pyproject.toml":
        return _parse_pyproject(relative, text)
    if name == "pipfile":
        return _parse_pipfile(relative, text)
    if name in {"poetry.lock", "uv.lock"}:
        return _parse_toml_packages(relative, text, "PyPI")
    if name == "package.json":
        return _parse_package_json(relative, text)
    if name in {"package-lock.json", "npm-shrinkwrap.json"}:
        return _parse_npm_lock(relative, text)
    if name == "yarn.lock":
        return _parse_yarn_lock(relative, text)
    if name == "pnpm-lock.yaml":
        return _parse_pnpm_lock(relative, text)
    if name == "pom.xml":
        return _parse_pom(relative, text)
    if name in {"build.gradle", "build.gradle.kts"}:
        return _parse_gradle(relative, text)
    if name == "gradle.lockfile":
        return _parse_gradle_lock(relative, text)
    return []


def _parse_requirements(relative: str, text: str) -> List[Dependency]:
    dependencies = []
    for index, raw in enumerate(text.splitlines(), start=1):
        line = raw.split("#", 1)[0].strip()
        if not line or line.startswith("-"):
            continue
        requirement = re.sub(r"\[[^\]]+\]", "", line.split(";", 1)[0]).strip()
        match = _REQ_SPEC.match(requirement.replace(" ", ""))
        if not match or not _REQ_NAME.match(match.group("name") or ""):
            continue
        name = match.group("name")
        operator = match.group("op")
        version = match.group("version")
        exact = version if operator in {"==", "==="} else None
        constraint = f"{operator}{version}" if operator and version else None
        dependencies.append(Dependency(
            name=name,
            ecosystem="PyPI",
            manifest_path=relative,
            version=exact,
            constraint=constraint,
            dependency_type="direct",
            source_kind="manifest",
            line_number=index,
        ))
    return dependencies


def _parse_pyproject(relative: str, text: str) -> List[Dependency]:
    dependencies = []
    for section, names in _toml_string_lists(text).items():
        if section in {"project.dependencies"} or section.startswith("project.optional-dependencies"):
            for index, requirement in enumerate(names, start=1):
                dependencies.extend(_requirement_or_skip(relative, requirement, index))
    for section, pairs in _toml_string_pairs(text).items():
        if not section.startswith("tool.poetry") or not section.endswith("dependencies"):
            continue
        for name, value in pairs:
            if name == "python":
                continue
            dependencies.append(_loose_version(relative, "PyPI", name, value))
    return dependencies


def _parse_pipfile(relative: str, text: str) -> List[Dependency]:
    dependencies = []
    for section, pairs in _toml_string_pairs(text).items():
        if section not in {"packages", "dev-packages"}:
            continue
        for name, value in pairs:
            item = _loose_version(relative, "PyPI", name, value)
            item.dependency_type = "direct"
            dependencies.append(item)
    return dependencies


def _parse_toml_packages(relative: str, text: str, ecosystem: str) -> List[Dependency]:
    dependencies = []
    for block in re.split(r"(?m)^\[\[package\]\]\s*$", text)[1:]:
        name = _toml_value(block, "name")
        version = _toml_value(block, "version")
        if not name or not version:
            continue
        category = (_toml_value(block, "category") or "").lower()
        dependency_type = "resolved"
        if category == "dev":
            dependency_type = "resolved"
        dependencies.append(Dependency(
            name=name,
            ecosystem=ecosystem,
            manifest_path=relative,
            version=version,
            constraint=None,
            dependency_type=dependency_type,
            source_kind="lock",
            line_number=1,
        ))
    return dependencies


def _parse_package_json(relative: str, text: str) -> List[Dependency]:
    payload = json.loads(text)
    if not isinstance(payload, dict):
        raise ValueError("package.json root is not an object")
    dependencies = []
    for section in ("dependencies", "devDependencies", "optionalDependencies"):
        entries = payload.get(section) or {}
        if not isinstance(entries, dict):
            continue
        for name, value in entries.items():
            if not isinstance(name, str) or not isinstance(value, str):
                continue
            item = _loose_version(relative, "npm", name, value)
            item.dependency_type = "direct"
            dependencies.append(item)
    return dependencies


def _parse_npm_lock(relative: str, text: str) -> List[Dependency]:
    payload = json.loads(text)
    if not isinstance(payload, dict):
        raise ValueError("lockfile root is not an object")
    dependencies: List[Dependency] = []
    packages = payload.get("packages")
    if isinstance(packages, dict):
        for key, meta in packages.items():
            if not key or not isinstance(meta, dict):
                continue
            name = meta.get("name") or _npm_name_from_path(key)
            version = meta.get("version")
            if not name or not isinstance(version, str):
                continue
            nested = key.count("node_modules/") > 1
            dependencies.append(Dependency(
                name=name,
                ecosystem="npm",
                manifest_path=relative,
                version=version,
                dependency_type="transitive" if nested else "resolved",
                source_kind="lock",
            ))
        return dependencies
    _walk_npm_dependencies(payload.get("dependencies") or {}, relative, dependencies, transitive=False)
    return dependencies


def _walk_npm_dependencies(entries: dict, relative: str, output: List[Dependency], transitive: bool) -> None:
    if not isinstance(entries, dict):
        return
    for name, meta in entries.items():
        if not isinstance(meta, dict):
            continue
        version = meta.get("version")
        if isinstance(name, str) and isinstance(version, str):
            output.append(Dependency(
                name=name,
                ecosystem="npm",
                manifest_path=relative,
                version=version,
                dependency_type="transitive" if transitive else "resolved",
                source_kind="lock",
            ))
        _walk_npm_dependencies(meta.get("dependencies") or {}, relative, output, transitive=True)


def _parse_yarn_lock(relative: str, text: str) -> List[Dependency]:
    dependencies = []
    headers: List[str] = []
    for raw in text.splitlines():
        if raw.startswith("#") or not raw.strip():
            continue
        if not raw.startswith(" "):
            headers = [part.strip().strip('"').strip("'") for part in raw.rstrip(":").split(",")]
            continue
        match = _YARN_VERSION.match(raw)
        if not match:
            continue
        version = match.group(1)
        for header in headers:
            name = _yarn_name(header)
            if not name:
                continue
            dependencies.append(Dependency(
                name=name,
                ecosystem="npm",
                manifest_path=relative,
                version=version,
                dependency_type="resolved",
                source_kind="lock",
            ))
    return dependencies


def _parse_pnpm_lock(relative: str, text: str) -> List[Dependency]:
    dependencies = []
    in_packages = False
    for raw in text.splitlines():
        if raw.startswith("packages:"):
            in_packages = True
            continue
        if in_packages and raw and not raw.startswith(" "):
            in_packages = False
        if not in_packages:
            continue
        match = _PNPM_PACKAGE.match(raw)
        if not match:
            continue
        dependencies.append(Dependency(
            name=match.group(1),
            ecosystem="npm",
            manifest_path=relative,
            version=match.group(2),
            dependency_type="resolved",
            source_kind="lock",
        ))
    return dependencies


def _parse_pom(relative: str, text: str) -> List[Dependency]:
    if "<!DOCTYPE" in text.upper() or "<!ENTITY" in text.upper():
        raise ValueError("DTD is not allowed")
    root = ET.fromstring(text)
    parent_map = {child: parent for parent in root.iter() for child in list(parent)}
    dependencies = []
    for element in root.iter():
        if _local(element.tag) != "dependencies":
            continue
        if _has_ancestor(parent_map, element, "dependencyManagement"):
            continue
        for child in list(element):
            if _local(child.tag) != "dependency":
                continue
            group = _child_text(child, "groupId")
            artifact = _child_text(child, "artifactId")
            version = _child_text(child, "version")
            if not group or not artifact:
                continue
            exact = version if version and not version.startswith("$") else None
            dependencies.append(Dependency(
                name=f"{group}:{artifact}",
                ecosystem="Maven",
                manifest_path=relative,
                version=exact,
                constraint=version,
                dependency_type="direct",
                source_kind="manifest",
            ))
    return dependencies


def _parse_gradle(relative: str, text: str) -> List[Dependency]:
    dependencies = []
    for index, raw in enumerate(text.splitlines(), start=1):
        match = _GRADLE_DEP.search(raw)
        if not match:
            continue
        parts = match.group(1).split(":")
        if len(parts) < 2:
            continue
        version = parts[2] if len(parts) >= 3 else None
        exact = version if version and "$" not in version and version != "+" else None
        dependencies.append(Dependency(
            name=f"{parts[0]}:{parts[1]}",
            ecosystem="Maven",
            manifest_path=relative,
            version=exact,
            constraint=version,
            dependency_type="direct",
            source_kind="manifest",
            line_number=index,
        ))
    return dependencies


def _parse_gradle_lock(relative: str, text: str) -> List[Dependency]:
    dependencies = []
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line or line.startswith("empty="):
            continue
        coordinate = line.split("=", 1)[0]
        parts = coordinate.split(":")
        if len(parts) < 3:
            continue
        dependencies.append(Dependency(
            name=f"{parts[0]}:{parts[1]}",
            ecosystem="Maven",
            manifest_path=relative,
            version=parts[2],
            dependency_type="resolved",
            source_kind="lock",
        ))
    return dependencies


def _prefer_lockfiles(dependencies: Sequence[Dependency]) -> List[Dependency]:
    groups: Dict[str, List[Dependency]] = {}
    order: List[str] = []
    for dependency in dependencies:
        if dependency.identity not in groups:
            groups[dependency.identity] = []
            order.append(dependency.identity)
        groups[dependency.identity].append(dependency)
    selected: List[Dependency] = []
    for identity in order:
        rows = groups[identity]
        locked = [row for row in rows if row.source_kind == "lock" and row.version]
        manifests = [row for row in rows if row.source_kind == "manifest"]
        direct_names = {row.identity for row in manifests}
        constraint = next((row.constraint for row in manifests if row.constraint), None)
        manifest_path = manifests[0].manifest_path if manifests else None
        if locked:
            seen_versions = set()
            for row in locked:
                if row.version in seen_versions:
                    continue
                seen_versions.add(row.version)
                relation = row.dependency_type
                if identity in direct_names and relation in {"resolved", "transitive"}:
                    relation = "direct" if row.dependency_type != "transitive" else "direct"
                if identity in direct_names and row.dependency_type == "resolved":
                    relation = "direct"
                selected.append(Dependency(
                    name=row.name,
                    ecosystem=row.ecosystem,
                    manifest_path=manifest_path or row.manifest_path,
                    version=row.version,
                    constraint=constraint or row.constraint,
                    dependency_type=relation if identity in direct_names else (
                        "transitive" if row.dependency_type == "resolved" else row.dependency_type
                    ),
                    source_kind="lock",
                    line_number=row.line_number,
                ))
            continue
        seen = set()
        for row in manifests:
            key = (row.version, row.constraint, row.manifest_path)
            if key in seen:
                continue
            seen.add(key)
            selected.append(row)
    return selected


def _local_pypi_vulnerability(dependency: Dependency) -> Optional[Vulnerability]:
    if dependency.ecosystem != "PyPI":
        return None
    operator, version = _operator_and_version(dependency)
    if not operator or not version:
        return None
    seeded = VulnerabilityDB.match_local_seed(dependency.name, operator, version)
    if not seeded:
        return None
    return Vulnerability(
        dependency=dependency,
        vuln_id=seeded.get("cwe_id") or "CWE-1395",
        summary=seeded.get("description"),
        severity=getattr(seeded.get("severity"), "value", None) or str(seeded.get("severity")),
        fixed_in=[seeded["version"]] if seeded.get("version") else [],
        source="local_seed",
    )


def query_generation(name: str, ecosystem: str, version: str) -> dict:
    return {"package": {"name": name, "ecosystem": ecosystem}, "version": version}


def _vulnerability_from_osv(dependency: Dependency, raw: dict) -> Vulnerability:
    severity, vector = _osv_severity(raw)
    references = []
    for item in raw.get("references") or []:
        if isinstance(item, dict) and item.get("url"):
            references.append(str(item["url"]))
    affected: List[str] = []
    fixed: List[str] = []
    for entry in raw.get("affected") or []:
        if not isinstance(entry, dict):
            continue
        for version in entry.get("versions") or []:
            affected.append(str(version))
        for rng in entry.get("ranges") or []:
            if not isinstance(rng, dict):
                continue
            for event in rng.get("events") or []:
                if isinstance(event, dict) and event.get("fixed"):
                    fixed.append(str(event["fixed"]))
    return Vulnerability(
        dependency=dependency,
        vuln_id=str(raw.get("id") or "OSV"),
        summary=(raw.get("summary") or raw.get("details") or None),
        severity=severity,
        severity_vector=vector,
        references=references[:10],
        affected=affected[:20],
        fixed_in=fixed[:10],
        source="OSV",
    )


def _osv_severity(raw: dict) -> Tuple[Optional[str], Optional[str]]:
    labels = []
    vector = None
    for source in (raw.get("database_specific"), raw.get("ecosystem_specific")):
        if isinstance(source, dict) and source.get("severity"):
            labels.append(str(source["severity"]))
    for item in raw.get("severity") or []:
        if not isinstance(item, dict) or not item.get("score"):
            continue
        score = str(item["score"])
        if score.upper().startswith("CVSS"):
            vector = score
        else:
            labels.append(score)
    for label in labels:
        normalized = label.strip().upper()
        if normalized == "MODERATE":
            normalized = "MEDIUM"
        if normalized in {"CRITICAL", "HIGH", "MEDIUM", "LOW"}:
            return normalized, vector
    return None, vector


def _requirement_or_skip(relative: str, requirement: str, line: int) -> List[Dependency]:
    parsed = _parse_requirements(relative, requirement)
    for item in parsed:
        item.line_number = line
    return parsed


def _loose_version(relative: str, ecosystem: str, name: str, value: str) -> Dependency:
    text = value.strip().strip('"').strip("'")
    exact = text if re.fullmatch(r"\d+\.\d+(?:\.\d+)?[A-Za-z0-9.*+\-]*", text) else None
    if text.startswith("=="):
        exact = text[2:]
    return Dependency(
        name=name,
        ecosystem=ecosystem,
        manifest_path=relative,
        version=exact,
        constraint=None if exact and text == exact else text,
        dependency_type="direct",
        source_kind="manifest",
    )


def _operator_and_version(dependency: Dependency) -> Tuple[Optional[str], Optional[str]]:
    if dependency.version:
        return "==", dependency.version
    if dependency.constraint:
        match = re.match(r"(===|==|~=|!=|>=|<=|>|<)(.+)", dependency.constraint)
        if match:
            return match.group(1), match.group(2)
    return None, None


def _exact_version(dependency: Dependency) -> bool:
    return bool(dependency.version) and dependency.source_kind in {"manifest", "lock"}


def _normalize_name(ecosystem: str, name: str) -> str:
    if ecosystem == "PyPI":
        return re.sub(r"[-_.]+", "-", name).lower()
    return name


def _npm_name_from_path(path: str) -> Optional[str]:
    parts = [part for part in path.split("node_modules/") if part]
    if not parts:
        return None
    tail = parts[-1].strip("/")
    return tail or None


def _yarn_name(header: str) -> Optional[str]:
    if header.startswith("@"):
        scope, _, rest = header[1:].partition("/")
        name, _, _version = rest.partition("@")
        return f"@{scope}/{name}" if name else None
    name, _, _version = header.partition("@")
    return name or None


def _toml_value(block: str, key: str) -> Optional[str]:
    match = re.search(rf"(?m)^{key}\s*=\s*\"([^\"]+)\"", block)
    return match.group(1) if match else None


def _toml_string_lists(text: str) -> Dict[str, List[str]]:
    result: Dict[str, List[str]] = {}
    section = ""
    collecting = False
    key_name = ""
    for raw in text.splitlines():
        stripped = raw.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            collecting = False
            section = stripped.strip("[]").strip()
            continue
        if collecting:
            result.setdefault(f"{section}.{key_name}" if section else key_name, [])
            result[f"{section}.{key_name}" if section else key_name].extend(re.findall(r'"([^"]+)"', stripped))
            if "]" in stripped:
                collecting = False
            continue
        match = re.match(r"([A-Za-z0-9_-]+)\s*=\s*\[(.*)", stripped)
        if not match:
            continue
        key_name = match.group(1)
        bucket = f"{section}.{key_name}" if section else key_name
        result.setdefault(bucket, []).extend(re.findall(r'"([^"]+)"', match.group(2)))
        collecting = "]" not in match.group(2)
    return result


def _toml_string_pairs(text: str) -> Dict[str, List[Tuple[str, str]]]:
    result: Dict[str, List[Tuple[str, str]]] = {}
    section = ""
    for raw in text.splitlines():
        stripped = raw.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            section = stripped.strip("[]").strip()
            continue
        match = re.match(r'"?([A-Za-z0-9_.\-]+)"?\s*=\s*"([^"]*)"', stripped)
        if match and section:
            result.setdefault(section, []).append((match.group(1), match.group(2)))
    return result


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _child_text(element: ET.Element, name: str) -> Optional[str]:
    for child in list(element):
        if _local(child.tag) == name and child.text:
            return child.text.strip()
    return None


def _has_ancestor(parent_map, element: ET.Element, name: str) -> bool:
    current = element
    while current in parent_map:
        current = parent_map[current]
        if _local(current.tag) == name:
            return True
    return False


def _severity_or_info(label: Optional[str]) -> Severity:
    if label in {"CRITICAL", "HIGH", "MEDIUM", "LOW"}:
        return Severity[label]
    return Severity.INFO


def _snippet(dependency: Dependency) -> str:
    if dependency.version:
        return f"{dependency.name}=={dependency.version}"
    if dependency.constraint:
        return f"{dependency.name}{dependency.constraint}"
    return dependency.name


def _recommendation(dependency: Dependency, vuln: Vulnerability) -> str:
    if vuln.fixed_in:
        return f"Upgrade '{dependency.name}' to {', '.join(vuln.fixed_in)} or a newer unaffected release."
    return f"Review advisory {vuln.vuln_id} for '{dependency.name}'. No fixed version was provided."


def _finding(
    rule_id: str,
    severity: Severity,
    file_path: str,
    line_number: int,
    snippet: str,
    description: str,
    recommendation: str,
    token: str,
    cwe_id: Optional[str] = None,
) -> SecurityFinding:
    return SecurityFinding(
        id=hashlib.sha256(token.encode()).hexdigest(),
        rule_id=rule_id,
        severity=severity,
        cwe_id=cwe_id,
        owasp_category="A06:2021-Vulnerable and Outdated Components",
        confidence="HIGH" if severity != Severity.INFO else "LOW",
        file_path=file_path,
        line_number=line_number,
        code_snippet=snippet[:180],
        description=description[:500],
        recommendation=recommendation[:300],
    )


def _path_from_message(message: str) -> str:
    return message.split(":", 1)[0] or "manifest"
