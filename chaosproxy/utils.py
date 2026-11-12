from __future__ import annotations

import hashlib
from typing import Dict, List, Set, Tuple

HOP_BY_HOP_HEADERS: Set[str] = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailers",
    "transfer-encoding",
    "upgrade",
    "host",
}


def filter_request_headers(headers: Dict[str, str] | List[Tuple[bytes, bytes]]) -> Dict[str, str]:
    """Strip hop-by-hop headers and prepare headers for forwarding."""
    cleaned: Dict[str, str] = {}
    if isinstance(headers, list):
        for k_bytes, v_bytes in headers:
            k = k_bytes.decode("latin-1").lower()
            if k not in HOP_BY_HOP_HEADERS and not k.startswith("sec-"):
                cleaned[k] = v_bytes.decode("latin-1")
    else:
        for k, v in headers.items():
            k_lower = k.lower()
            if k_lower not in HOP_BY_HOP_HEADERS:
                cleaned[k] = v
    return cleaned


def filter_response_headers(headers: Dict[str, str]) -> Dict[str, str]:
    """Filter headers returned from upstream to downstream client."""
    cleaned: Dict[str, str] = {}
    for k, v in headers.items():
        k_lower = k.lower()
        # httpx automatically decodes gzip/br/deflate into .content, so strip content-encoding
        # to prevent downstream clients (like PowerShell or curl) from attempting double-decompression.
        if k_lower not in HOP_BY_HOP_HEADERS and k_lower not in ("content-length", "content-encoding"):
            cleaned[k] = v
    return cleaned


def compute_request_signature(method: str, path: str, query: str, body: bytes) -> str:
    """Generate a deterministic sha256 hash identifying this HTTP request."""
    hasher = hashlib.sha256()
    hasher.update(method.upper().encode("utf-8"))
    hasher.update(b":")
    hasher.update(path.encode("utf-8"))
    hasher.update(b"?")
    hasher.update(query.encode("utf-8"))
    hasher.update(b":")
    hasher.update(body)
    return hasher.hexdigest()


# Lightweight ANSI color formatter
class LogColor:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    RED = "\033[31m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    GRAY = "\033[90m"


def format_log(tag: str, status: int | str, method: str, path: str, detail: str = "") -> str:
    color = LogColor.GREEN
    if isinstance(status, int):
        if status >= 500:
            color = LogColor.RED
        elif status >= 400:
            color = LogColor.YELLOW
        elif status >= 300:
            color = LogColor.CYAN

    detail_str = f" {LogColor.GRAY}({detail}){LogColor.RESET}" if detail else ""
    return (
        f"{LogColor.BOLD}{tag:<16}{LogColor.RESET} "
        f"{color}{status:<3}{LogColor.RESET} "
        f"{LogColor.BOLD}{method:<6}{LogColor.RESET} "
        f"{path}{detail_str}"
    )
