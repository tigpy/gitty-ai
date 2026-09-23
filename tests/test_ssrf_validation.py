import ipaddress
import pytest
from unittest.mock import patch, MagicMock

from libs.shared_kernel.validation import (
    prepare_repository_clone_url,
    validate_repository_url,
    extract_nat64_ipv4,
    is_private_ip,
)
from services.scanner_service.infrastructure.github_repository_scanner import GithubRepositoryScanner


def _public_resolver(hostname):
    return ["8.8.8.8"]


def _private_resolver(hostname):
    return ["10.1.2.3"]


class _Response:
    def __init__(self, status, location=None):
        self.status = status
        self.headers = {"Location": location} if location else {}

    def read(self, _n=0):
        return b""

    def close(self):
        return None

    def getcode(self):
        return self.status


class _Opener:
    def __init__(self, responses):
        self.responses = list(responses)
        self.requested = []

    def open(self, request, timeout=None):
        self.requested.append(request.full_url)
        if not self.responses:
            raise AssertionError("unexpected request")
        return self.responses.pop(0)


def test_public_https_repository_urls_are_allowed():
    urls = [
        "https://github.com/torvalds/linux",
        "https://gitlab.com/org/repo-name",
        "https://bitbucket.org/user/repo",
    ]
    for url in urls:
        assert validate_repository_url(url, resolver=_public_resolver) == url


def test_canonical_public_ip_is_allowed():
    assert validate_repository_url("https://8.8.8.8/repo.git") == "https://8.8.8.8/repo.git"
    assert validate_repository_url("https://[2001:4860:4860::8888]/repo.git") == "https://[2001:4860:4860::8888]/repo.git"


@pytest.mark.parametrize("url", [
    "https://localhost/repo.git",
    "https://127.0.0.1/repo.git",
    "https://[::1]/repo.git",
    "https://10.0.0.1/repo.git",
    "https://192.168.1.20/repo.git",
    "https://172.16.5.5/repo.git",
    "https://169.254.169.254/latest/meta-data",
    "https://[fe80::1]/repo.git",
    "https://[fc00::1]/repo.git",
    "https://224.0.0.1/repo.git",
    "https://[ff02::1]/repo.git",
    "https://0.0.0.0/repo.git",
    "https://[::]/repo.git",
    "https://100.64.0.1/repo.git",
    "https://[::ffff:127.0.0.1]/repo.git",
    "https://[::ffff:10.1.2.3]/repo.git",
    "http://127.0.0.1/repo.git",
    "file:///etc/passwd",
])
def test_blocked_literals_and_schemes(url):
    with pytest.raises(ValueError):
        validate_repository_url(url)


@pytest.mark.parametrize("url", [
    "https://2130706433/repo.git",          # decimal 127.0.0.1
    "https://0x7f000001/repo.git",          # hex 127.0.0.1
    "https://0177.0.0.1/repo.git",          # octal loopback
    "https://127.1/repo.git",               # short inet_aton form
    "https://10.1/repo.git",                # short private form
    "https://0xA9FEA9FE/latest",            # hex 169.254.169.254
])
def test_alternate_ip_representations_are_blocked(url):
    with pytest.raises(ValueError):
        validate_repository_url(url)


def test_dns_hostname_resolving_to_private_address_is_blocked():
    with pytest.raises(ValueError, match="non-public"):
        validate_repository_url("https://evil.example/repo.git", resolver=_private_resolver)


def test_mixed_public_and_private_dns_answers_are_blocked():
    def resolver(_hostname):
        return ["8.8.8.8", "127.0.0.1"]

    with pytest.raises(ValueError, match="non-public"):
        validate_repository_url("https://evil.example/repo.git", resolver=resolver)


def test_link_local_dns_answer_is_blocked():
    def resolver(_hostname):
        return ["169.254.169.254"]

    with pytest.raises(ValueError, match="non-public"):
        validate_repository_url("https://metadata.example/repo.git", resolver=resolver)


def test_ipv6_loopback_dns_answer_is_blocked():
    def resolver(_hostname):
        return ["::1"]

    with pytest.raises(ValueError, match="non-public"):
        validate_repository_url("https://loop.example/repo.git", resolver=resolver)


def test_redirect_to_private_address_is_rejected(tmp_path):
    opener = _Opener([
        _Response(302, "https://127.0.0.1/internal.git/info/refs?service=git-upload-pack"),
    ])
    with pytest.raises(ValueError):
        prepare_repository_clone_url(
            "https://public.example/repo.git",
            resolver=_public_resolver,
            opener=opener,
        )

    scanner = GithubRepositoryScanner()
    with patch("subprocess.run") as mock_run, patch(
        "libs.shared_kernel.validation.build_non_redirect_opener",
        return_value=opener,
    ), patch(
        "libs.shared_kernel.validation.default_dns_resolver",
        side_effect=lambda host: ["8.8.8.8"],
    ):
        opener.responses = [
            _Response(302, "https://10.0.0.8/secret.git/info/refs?service=git-upload-pack"),
        ]
        with pytest.raises(ValueError):
            scanner.clone_or_fetch("https://public.example/repo.git", str(tmp_path / "repo"))
        mock_run.assert_not_called()


def test_redirect_to_public_repository_is_used_and_git_will_not_follow_again(tmp_path):
    final = "https://github.com/torvalds/linux.git"
    opener = _Opener([
        _Response(302, final + "/info/refs?service=git-upload-pack"),
        _Response(200),
    ])
    resolved = prepare_repository_clone_url(
        "https://example.com/old-name",
        resolver=_public_resolver,
        opener=opener,
    )
    assert resolved == final

    scanner = GithubRepositoryScanner()
    scan_opener = _Opener([
        _Response(302, final + "/info/refs?service=git-upload-pack"),
        _Response(200),
    ])
    with patch("subprocess.run") as mock_run, patch(
        "libs.shared_kernel.validation.build_non_redirect_opener",
        return_value=scan_opener,
    ), patch(
        "libs.shared_kernel.validation.default_dns_resolver",
        side_effect=lambda host: ["8.8.8.8"],
    ):
        mock_run.return_value = MagicMock(returncode=0)
        scanner.clone_or_fetch("https://example.com/old-name", str(tmp_path / "repo"))
        cmd = mock_run.call_args[0][0]
        assert "http.followRedirects=false" in cmd
        assert "credential.helper=" in cmd
        assert "core.symlinks=false" in cmd
        assert final in cmd
        assert cmd.index("--") < cmd.index(final)


def test_embedded_credentials_and_argument_flags_still_rejected():
    with pytest.raises(ValueError, match="credentials"):
        validate_repository_url("https://user:pass@github.com/org/repo.git", resolver=_public_resolver)
    with pytest.raises(ValueError, match="hyphen"):
        validate_repository_url("--upload-pack=touch /tmp/pwned")


def test_nat64_exact_observed_address_extracted_and_allowed():
    """
    RFC 6052 NAT64 well-known prefix address 64:ff9b::14cf:4952 embeds
    public IPv4 20.207.73.82. Verify correct extraction and non-rejection.
    """
    v6 = ipaddress.IPv6Address("64:ff9b::14cf:4952")
    extracted = extract_nat64_ipv4(v6)
    assert extracted == ipaddress.IPv4Address("20.207.73.82")
    assert not is_private_ip("64:ff9b::14cf:4952")

    # Allowed when returned by DNS resolver
    url = "https://github.com/owner/repo.git"
    assert validate_repository_url(url, resolver=lambda _: ["64:ff9b::14cf:4952"]) == url

    # Allowed as an IPv6 literal
    literal_url = "https://[64:ff9b::14cf:4952]/owner/repo.git"
    assert validate_repository_url(literal_url) == literal_url


@pytest.mark.parametrize("nat64_ip,embedded_ipv4", [
    ("64:ff9b::808:808", "8.8.8.8"),
    ("64:ff9b::101:101", "1.1.1.1"),
    ("64:ff9b::9564:ae91", "149.100.174.145"),
])
def test_nat64_public_ipv4_destinations_are_allowed(nat64_ip, embedded_ipv4):
    v6 = ipaddress.IPv6Address(nat64_ip)
    assert extract_nat64_ipv4(v6) == ipaddress.IPv4Address(embedded_ipv4)
    assert not is_private_ip(nat64_ip)
    url = "https://example.com/repo.git"
    assert validate_repository_url(url, resolver=lambda _: [nat64_ip]) == url
    assert validate_repository_url(f"https://[{nat64_ip}]/repo.git") == f"https://[{nat64_ip}]/repo.git"


@pytest.mark.parametrize("nat64_ip,description", [
    ("64:ff9b::7f00:1", "127.0.0.1 (loopback)"),
    ("64:ff9b::a00:1", "10.0.0.1 (private 10.x.x.x)"),
    ("64:ff9b::c0a8:101", "192.168.1.1 (private 192.168.x.x)"),
    ("64:ff9b::ac10:1", "172.16.0.1 (private 172.16.x.x)"),
    ("64:ff9b::a9fe:a9fe", "169.254.169.254 (link-local)"),
    ("64:ff9b::e000:1", "224.0.0.1 (multicast)"),
    ("64:ff9b::", "0.0.0.0 (unspecified)"),
])
def test_nat64_private_and_loopback_destinations_are_rejected(nat64_ip, description):
    assert is_private_ip(nat64_ip)
    with pytest.raises(ValueError, match="non-public"):
        validate_repository_url("https://example.com/repo.git", resolver=lambda _: [nat64_ip])
    with pytest.raises(ValueError, match="private/loopback"):
        validate_repository_url(f"https://[{nat64_ip}]/repo.git")

