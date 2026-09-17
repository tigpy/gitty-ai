import re
import ipaddress
import urllib.parse
from fastapi import HTTPException

REPO_ID_REGEX = re.compile(r"^[a-zA-Z0-9_-]+$")

BLOCKED_HOSTNAMES = {
    "localhost",
    "127.0.0.1",
    "::1",
    "metadata.google.internal",
    "instance-data",
}

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


def is_private_ip(hostname: str) -> bool:
    """Check if a hostname resolves to or is a private/loopback/link-local IP address."""
    try:
        ip = ipaddress.ip_address(hostname)
        return (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_multicast
            or ip.is_reserved
            or ip.is_unspecified
        )
    except ValueError:
        # Not a raw IP literal
        return False


def validate_repository_url(url: str, allow_http: bool = False) -> str:
    """
    Validates repository URL to prevent argument injection (CWE-88) and SSRF (CWE-918).
    - Rejects URLs starting with hyphens or flags.
    - Requires http or https scheme (https by default).
    - Rejects localhost, loopback, private IP ranges, and cloud metadata endpoints.
    """
    if not url or not isinstance(url, str):
        raise ValueError("Repository URL is required and must be a string.")

    cleaned_url = url.strip()

    # CWE-88: Git argument injection protection
    if cleaned_url.startswith("-"):
        raise ValueError("Invalid repository URL: cannot start with a hyphen or command flag.")

    parsed = urllib.parse.urlparse(cleaned_url)

    allowed_schemes = ("https", "http") if allow_http else ("https",)
    if parsed.scheme.lower() not in allowed_schemes:
        raise ValueError(f"Invalid URL protocol '{parsed.scheme}'. Only HTTPS repository URLs are allowed.")

    hostname = (parsed.hostname or "").lower()
    if not hostname:
        raise ValueError("Invalid repository URL: missing hostname.")

    if hostname in BLOCKED_HOSTNAMES:
        raise ValueError(f"Access to '{hostname}' is blocked for security reasons.")

    if hostname.endswith(".local") or hostname.endswith(".internal"):
        raise ValueError(f"Access to internal domain '{hostname}' is blocked.")

    if is_private_ip(hostname):
        raise ValueError(f"Access to private/loopback IP '{hostname}' is blocked.")

    # Disallow credentials embedded in URL (e.g. https://user:pass@host) to avoid leaking in logs/subprocess
    if parsed.username or parsed.password:
        raise ValueError("Embedded credentials in repository URLs are not permitted.")

    return cleaned_url

