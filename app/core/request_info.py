import ipaddress

import httpx
from fastapi import Request


def client_ip(request: Request) -> str:
    """Prefers X-Forwarded-For (set by a reverse proxy in front of this
    plain-HTTP backend) over the raw socket peer, which would otherwise
    just be the proxy's own address.
    """
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "Unknown"


def parse_user_agent(user_agent: str | None) -> tuple[str, str]:
    """Best-effort (device, browser) split from a raw User-Agent string —
    substring checks only, no dependency, sufficient for the handful of
    platforms/engines a real admin actually connects from.
    """
    ua_lower = (user_agent or "").lower()

    if "windows" in ua_lower:
        device = "Windows"
    elif "mac os" in ua_lower or "macintosh" in ua_lower:
        device = "Mac"
    elif "android" in ua_lower:
        device = "Android"
    elif "iphone" in ua_lower or "ipad" in ua_lower:
        device = "iOS"
    elif "linux" in ua_lower:
        device = "Linux"
    else:
        device = "Unknown"

    if "edg/" in ua_lower:
        browser = "Edge"
    elif "opr/" in ua_lower or "opera" in ua_lower:
        browser = "Opera"
    elif "chrome/" in ua_lower and "chromium" not in ua_lower:
        browser = "Chrome"
    elif "firefox/" in ua_lower:
        browser = "Firefox"
    elif "safari/" in ua_lower and "chrome/" not in ua_lower:
        browser = "Safari"
    else:
        browser = "Unknown"

    return device, browser


def _is_private(ip: str) -> bool:
    try:
        return ipaddress.ip_address(ip).is_private
    except ValueError:
        return True  # unparsable (e.g. "Unknown") — nothing to look up


async def resolve_location(ip: str) -> str:
    """City/country via ip-api.com's free JSON endpoint (no key required).
    Private/loopback IPs are never sent to it — they're not resolvable
    anyway and would just waste the request. Any failure (timeout, non-200,
    unexpected shape) degrades to "Unknown" rather than raising, since a
    flaky third-party lookup should never break login.
    """
    if _is_private(ip):
        return "Local network"

    try:
        async with httpx.AsyncClient(timeout=2.5) as client:
            response = await client.get(f"http://ip-api.com/json/{ip}", params={"fields": "status,city,country"})
            data = response.json()
    except (httpx.HTTPError, ValueError):
        return "Unknown"

    if data.get("status") != "success":
        return "Unknown"
    parts = [p for p in (data.get("city"), data.get("country")) if p]
    return ", ".join(parts) if parts else "Unknown"
