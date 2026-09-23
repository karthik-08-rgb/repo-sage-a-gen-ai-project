import ipaddress
import re
import socket
from urllib.parse import urlparse
from app.core.exceptions import SecurityValidationException

# Blocked IP ranges (Private, Loopback, Link-Local, Cloud Metadata)
BLOCKED_NETWORKS = [
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("169.254.0.0/16"),       # Link-local / Cloud metadata (AWS/GCP/Azure)
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
]

ALLOWED_GIT_HOSTS = [
    "github.com",
    "gitlab.com",
    "bitbucket.org",
]

GIT_URL_REGEX = re.compile(
    r"^https://([a-zA-Z0-9\-\.]+)/([a-zA-Z0-9_\-\.]+)/([a-zA-Z0-9_\-\.]+?)(?:\.git)?/?$"
)


def validate_repository_url(url: str) -> str:
    """
    Validate Git URL against SSRF attacks and enforce HTTPS Git hosts.
    Ensures domain does not resolve to private/internal IP spaces.
    """
    cleaned_url = url.strip()
    if not cleaned_url.startswith("https://"):
        raise SecurityValidationException("Repository URL must use the HTTPS protocol.")

    match = GIT_URL_REGEX.match(cleaned_url)
    if not match:
        raise SecurityValidationException(
            "Invalid Git repository URL format. Example: https://github.com/octocat/Hello-World"
        )

    host, owner, repo = match.groups()
    host_lower = host.lower()

    # Verify allowed host or validate resolved IP
    try:
        addr_info = socket.getaddrinfo(host_lower, 443, proto=socket.IPPROTO_TCP)
        for _, _, _, _, sockaddr in addr_info:
            ip_str = sockaddr[0]
            ip_obj = ipaddress.ip_address(ip_str)
            for blocked in BLOCKED_NETWORKS:
                if ip_obj in blocked:
                    raise SecurityValidationException(
                        f"SSRF Protection: Host '{host_lower}' resolves to restricted network destination ({ip_str})."
                    )
    except socket.gaierror:
        raise SecurityValidationException(f"Could not resolve host '{host_lower}'.")

    return f"https://{host_lower}/{owner}/{repo}.git"
