import hashlib
import re


def normalize_error_content(text: str) -> str:
    """
    Normalize stack frames/error text by stripping dynamic memory addresses (0x...)
    and timestamps before fingerprinting.
    """
    if not text or not isinstance(text, str):
        return ""
    # Strip hex memory addresses (e.g. 0x7f8b9c0d1e2f -> 0x<HEX>)
    norm = re.sub(r"0x[0-9a-fA-F]+", "0x<HEX>", text)
    # Strip ISO and standard date-time stamps
    norm = re.sub(
        r"\b\d{4}-\d{2}-\d{2}[T\s]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?\b",
        "<TIMESTAMP>",
        norm,
    )
    # Strip variable line numbers from file path headers if needed to canonicalize trace header
    norm = re.sub(r'(File ".*?", line )\d+', r"\g<1><LINE>", norm)
    return norm.strip()


def compute_canonical_fingerprint(
    app_name: str,
    exception_type: str,
    content_or_top_frame: str = "",
    error_file: str = "",
    line_number: str = "",
) -> str:
    """
    Computes a deterministic 16-character SHA-256 fingerprint across all services.
    """
    exc = exception_type or "UnknownError"
    if content_or_top_frame and isinstance(content_or_top_frame, str):
        norm_frame = normalize_error_content(content_or_top_frame)[:200]
    elif error_file or line_number:
        norm_frame = f"{error_file}:{line_number}"
    else:
        norm_frame = "no_frame"

    raw_fp = f"{app_name}:{exc}:{norm_frame}"
    return hashlib.sha256(raw_fp.encode("utf-8")).hexdigest()[:16]
