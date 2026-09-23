import ipaddress
import re
import socket
import urllib.error
import urllib.parse
import urllib.request
from typing import Callable, List, Optional, Sequence

from fastapi import HTTPException

REPO_ID_REGEX = re.compile(r"^[a-zA-Z0-9_-]+$")
_HEX_RE = re.compile(r"^0x[0-9a-f]+$")
_DIGITS_RE = re.compile(r"^[0-9]+$")

BLOCKED_HOSTNAMES = {
    "localhost",
    "127.0.0.1",
    "::1",
    "metadata.google.internal",
    "instance-data",
}

_REDIRECT_STATUSES = {301, 302, 303, 307, 308}
_MAX_REDIRECTS = 5

Resolver = Callable[[str], Sequence[str]]


def validate_repository_id(repository_id: str) -> str:
    """
    Validates repository_id format to prevent directory traversal attacks.
    Enforces alphanumeric, dash, and underscore character constraints.
    """
    if not repository_id or not REPO_ID_REGEX.match(repository_id):
        raise HTTPException(
            status_code=400,
            detail="Invalid repository_id format. Only alphanumeric characters, dashes, and underscores are allowed."
        )
    return repository_id


_NAT64_WELL_KNOWN_PREFIX = ipaddress.IPv6Network("64:ff9b::/96")


def extract_nat64_ipv4(ip: ipaddress.IPv6Address) -> Optional[ipaddress.IPv4Address]:
    """
    Extract the embedded IPv4 address from an RFC 6052 NAT64 well-known prefix (64:ff9b::/96).
    Returns None if the address is not in this prefix.
    """
    if ip in _NAT64_WELL_KNOWN_PREFIX:
        return ipaddress.IPv4Address(ip.packed[-4:])
    return None


def _is_disallowed_ip(ip: ipaddress._BaseAddress) -> bool:
    """Reject addresses that are not globally routable, including mapped IPv4."""
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        return _is_disallowed_ip(ip.ipv4_mapped)
    """Reject addresses that are not globally routable, including mapped IPv4 and NAT64."""
    if isinstance(ip, ipaddress.IPv6Address):
        if ip.ipv4_mapped is not None:
            return _is_disallowed_ip(ip.ipv4_mapped)
        embedded_ipv4 = extract_nat64_ipv4(ip)
        if embedded_ipv4 is not None:
            return _is_disallowed_ip(embedded_ipv4)
    # is_global is not sufficient: some multicast addresses report is_global=True.
    return (
        not ip.is_global
        or ip.is_multicast
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_private
        or ip.is_reserved
        or ip.is_unspecified
        or bool(getattr(ip, "is_site_local", False))
    )


def is_private_ip(hostname: str) -> bool:
    """True when hostname is an IP literal in a blocked range, including mapped IPv6."""
    try:
        ip = ipaddress.ip_address(hostname)
    except ValueError:
        return False
    return _is_disallowed_ip(ip)


def _parse_obfuscated_ipv4(hostname: str) -> Optional[ipaddress.IPv4Address]:
    """
    Decode inet_aton-style literals that urlparse leaves as hostnames:
    decimal (2130706433), hex (0x7f000001), octal (0177.0.0.1), and short
    dotted forms (127.1). Returns None when the hostname is not an IP literal.
    """
    host = hostname.strip().lower()
    if _HEX_RE.fullmatch(host):
        value = int(host, 16)
        if value > 0xFFFFFFFF:
            raise ValueError(f"Invalid IPv4 literal '{hostname}'.")
        return ipaddress.IPv4Address(value)
    if _DIGITS_RE.fullmatch(host):
        value = int(host, 10)
        if value > 0xFFFFFFFF:
            return None
        return ipaddress.IPv4Address(value)
    if "." not in host:
        return None

    parts = host.split(".")
    if not 1 <= len(parts) <= 4:
        return None
    numbers: List[int] = []
    for part in parts:
        if part.startswith("0x"):
            if not _HEX_RE.fullmatch(part):
                return None
            numbers.append(int(part, 16))
        elif len(part) > 1 and part.startswith("0") and part.isdigit():
            try:
                numbers.append(int(part, 8))
            except ValueError:
                return None
        elif part.isdigit():
            numbers.append(int(part, 10))
        else:
            return None

    try:
        if len(numbers) == 4:
            if any(part > 255 for part in numbers):
                return None
            packed = (numbers[0] << 24) | (numbers[1] << 16) | (numbers[2] << 8) | numbers[3]
        elif len(numbers) == 3:
            if numbers[0] > 255 or numbers[1] > 255 or numbers[2] > 0xFFFF:
                return None
            packed = (numbers[0] << 24) | (numbers[1] << 16) | numbers[2]
        elif len(numbers) == 2:
            if numbers[0] > 255 or numbers[1] > 0xFFFFFF:
                return None
            packed = (numbers[0] << 24) | numbers[1]
        else:
            packed = numbers[0]
    except ValueError:
        return None
    if packed > 0xFFFFFFFF:
        return None
    return ipaddress.IPv4Address(packed)


def _literal_ip(hostname: str) -> Optional[ipaddress._BaseAddress]:
    try:
        return ipaddress.ip_address(hostname)
    except ValueError:
        pass
    return _parse_obfuscated_ipv4(hostname)


def default_dns_resolver(hostname: str) -> List[str]:
    """Resolve every A/AAAA address. Fail closed when DNS returns nothing."""
    try:
        infos = socket.getaddrinfo(hostname, None, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise ValueError(f"Could not resolve repository host '{hostname}': {exc}") from exc
    addresses = []
    for info in infos:
        address = info[4][0]
        if address not in addresses:
            addresses.append(address)
    if not addresses:
        raise ValueError(f"Could not resolve repository host '{hostname}'.")
    return addresses


def _assert_addresses_public(hostname: str, addresses: Sequence[str]) -> None:
    if not addresses:
        raise ValueError(f"Could not resolve repository host '{hostname}'.")
    for address in addresses:
        try:
            ip = ipaddress.ip_address(address.split("%", 1)[0])
        except ValueError as exc:
            raise ValueError(f"Resolver returned a non-IP address for '{hostname}'.") from exc
        if _is_disallowed_ip(ip):
            raise ValueError(
                f"Access to '{hostname}' is blocked because it resolves to non-public address '{ip}'."
            )


def validate_repository_url(
    url: str,
    allow_http: bool = False,
    resolver: Optional[Resolver] = None,
) -> str:
    """
    Validate a repository URL before it is queued or passed to git.

    Checks scheme, hostname, embedded credentials, obfuscated IP literals, and
    DNS. Every resolved address must be globally routable. This function does
    not follow HTTP redirects; clone-time redirect checks are separate so a
    redirect cannot skip the DNS check.
    """
    if not url or not isinstance(url, str):
        raise ValueError("Repository URL is required and must be a string.")

    cleaned_url = url.strip()
    if cleaned_url.startswith("-"):
        raise ValueError("Invalid repository URL: cannot start with a hyphen or command flag.")

    parsed = urllib.parse.urlparse(cleaned_url)
    allowed_schemes = ("https", "http") if allow_http else ("https",)
    if parsed.scheme.lower() not in allowed_schemes:
        raise ValueError(f"Invalid URL protocol '{parsed.scheme}'. Only HTTPS repository URLs are allowed.")

    hostname = (parsed.hostname or "").strip().lower().rstrip(".")
    if not hostname:
        raise ValueError("Invalid repository URL: missing hostname.")
    if "%" in hostname:
        raise ValueError("IPv6 zone identifiers are not allowed in repository URLs.")

    if hostname in BLOCKED_HOSTNAMES:
        raise ValueError(f"Access to '{hostname}' is blocked for security reasons.")
    if hostname.endswith(".local") or hostname.endswith(".internal"):
        raise ValueError(f"Access to internal domain '{hostname}' is blocked.")

    literal = _literal_ip(hostname)
    if literal is not None:
        if _is_disallowed_ip(literal):
            raise ValueError(f"Access to private/loopback IP '{literal}' is blocked.")
    else:
        lookup = resolver or default_dns_resolver
        _assert_addresses_public(hostname, list(lookup(hostname)))

    if parsed.username or parsed.password:
        raise ValueError("Embedded credentials in repository URLs are not permitted.")

    return cleaned_url


class _NoRedirect(urllib.request.HTTPErrorProcessor):
    """Return 3xx responses instead of letting urllib follow them."""

    def http_response(self, request, response):
        return response

    https_response = http_response


def build_non_redirect_opener():
    return urllib.request.build_opener(_NoRedirect)


def _discovery_url(clone_url: str) -> str:
    parsed = urllib.parse.urlsplit(clone_url)
    path = parsed.path.rstrip("/") + "/info/refs"
    return urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, path, "service=git-upload-pack", ""))


def _clone_url_from_location(current_probe: str, location: str) -> str:
    joined = urllib.parse.urljoin(current_probe, location)
    parsed = urllib.parse.urlsplit(joined)
    path = parsed.path
    marker = "/info/refs"
    if path.endswith(marker):
        path = path[: -len(marker)] or "/"
    return urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, path, "", ""))


def prepare_repository_clone_url(
    url: str,
    allow_http: bool = False,
    resolver: Optional[Resolver] = None,
    opener=None,
    max_redirects: int = _MAX_REDIRECTS,
) -> str:
    """
    Re-validate the clone URL, then inspect git's smart-HTTP discovery response
    without following redirects automatically.

    Each Location is validated again (scheme, DNS, and IP policy) before it can
    become the clone target. Git is still configured with http.followRedirects=false
    so a redirect after this check cannot reach a different host.
    """
    current = validate_repository_url(url, allow_http=allow_http, resolver=resolver)
    client = opener if opener is not None else build_non_redirect_opener()
    seen = set()

    for _ in range(max_redirects + 1):
        if current in seen:
            raise ValueError("Repository URL redirect loop was blocked.")
        seen.add(current)
        probe = _discovery_url(current)
        request = urllib.request.Request(probe, headers={"User-Agent": "git/2.39.0"}, method="GET")
        try:
            response = client.open(request, timeout=8)
        except urllib.error.HTTPError as exc:
            status = exc.code
            headers = exc.headers
            body_response = None
        except urllib.error.URLError as exc:
            raise ValueError(f"Could not verify repository redirects for '{current}': {exc.reason}") from exc
        else:
            status = getattr(response, "status", None) or response.getcode()
            headers = response.headers
            body_response = response

        if body_response is not None:
            try:
                body_response.read(128)
            finally:
                body_response.close()

        if status not in _REDIRECT_STATUSES:
            return current

        location = headers.get("Location") if headers is not None else None
        if not location:
            raise ValueError("Repository redirect was missing a Location header.")
        current = validate_repository_url(
            _clone_url_from_location(probe, location),
            allow_http=allow_http,
            resolver=resolver,
        )

    raise ValueError("Too many redirects while validating the repository URL.")
