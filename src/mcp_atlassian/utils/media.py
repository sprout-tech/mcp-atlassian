"""Shared media type detection and attachment download utilities."""

import base64
import binascii
import logging
import math
import mimetypes
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Maximum attachment size for inline download/upload (50 MB).
# Used by both Jira and Confluence server tools to gate in-memory transfers.
ATTACHMENT_MAX_BYTES: int = 50 * 1024 * 1024

# Maximum number of inline (base64) attachments accepted in a single tool call.
ATTACHMENT_MAX_COUNT: int = 10

# Encoded length ceiling for ATTACHMENT_MAX_BYTES of raw content (base64).
# 4 * ceil(n / 3) characters; allow a small pad for whitespace the caller may
# have included before strip.
ATTACHMENT_MAX_BASE64_CHARS: int = 4 * math.ceil(ATTACHMENT_MAX_BYTES / 3) + 8

_IMAGE_MIME_TYPES = frozenset(
    {
        "image/png",
        "image/jpeg",
        "image/gif",
        "image/webp",
        "image/svg+xml",
        "image/bmp",
    }
)

_AMBIGUOUS_MIME_TYPES = frozenset({"application/octet-stream", "application/binary"})

_IMAGE_EXTENSIONS = frozenset(
    {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".bmp"}
)


def is_image_attachment(
    media_type: str | None, filename: str | None
) -> tuple[bool, str]:
    """Detect whether an attachment is an image.

    Uses two-tier detection: explicit MIME type check, then filename
    extension fallback for ambiguous or missing MIME types.

    Args:
        media_type: The MIME type reported by the API.
        filename: The attachment filename.

    Returns:
        Tuple of (is_image, resolved_mime_type).
    """
    if media_type and media_type in _IMAGE_MIME_TYPES:
        return True, media_type

    if (media_type in _AMBIGUOUS_MIME_TYPES or media_type is None) and filename:
        ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        if ext in _IMAGE_EXTENSIONS:
            guessed = mimetypes.guess_type(filename)[0] or "image/png"
            return True, guessed

    return False, media_type or "application/octet-stream"


def sanitize_attachment_filename(filename: str) -> str:
    """Return a basename-only attachment filename.

    Strips any directory components (``../``, absolute paths) so caller-
    supplied names cannot influence filesystem paths if content is later
    written to disk. Rejects empty names and ``.`` / ``..``.

    Args:
        filename: Caller-supplied attachment filename.

    Returns:
        Sanitized basename.

    Raises:
        ValueError: If the filename is missing or reduces to an invalid name.
    """
    if not isinstance(filename, str) or not filename.strip():
        raise ValueError("Attachment filename is required")

    safe_name = Path(filename.strip()).name
    if not safe_name or safe_name in {".", ".."}:
        msg = f"Attachment filename is invalid: {filename!r}"
        raise ValueError(msg)
    return safe_name


def decode_inline_attachment(
    file: Mapping[str, Any] | dict[str, Any],
    *,
    max_bytes: int = ATTACHMENT_MAX_BYTES,
    max_base64_chars: int | None = None,
) -> tuple[str, str, bytes]:
    """Decode a base64 attachment descriptor into upload-ready bytes.

    Applies pre-decode and post-decode size gates, validates base64, and
    sanitizes the filename. Intended for chat-paste / remote-MCP uploads
    where content arrives as ``ImageContent.data`` (or equivalent) rather
    than a server-local file path.

    Args:
        file: A mapping with ``filename``, optional ``mime_type``, and
            base64-encoded ``base64`` content.
        max_bytes: Maximum decoded payload size in bytes.
        max_base64_chars: Maximum encoded string length before decode.
            Defaults to the shared ``ATTACHMENT_MAX_BASE64_CHARS`` when
            ``max_bytes`` is the default; otherwise derived from
            ``max_bytes``.

    Returns:
        A tuple of ``(filename, mime_type, content_bytes)``.

    Raises:
        ValueError: If the descriptor is malformed, oversized, empty, or
            not valid base64.
    """
    if not isinstance(file, Mapping):
        raise ValueError("Each attachment must be an object")

    filename_raw = file.get("filename")
    if not isinstance(filename_raw, str):
        raise ValueError("Attachment filename is required")
    safe_filename = sanitize_attachment_filename(filename_raw)

    mime_type = file.get("mime_type")
    if mime_type is None or mime_type == "":
        mime_type = mimetypes.guess_type(safe_filename)[0] or "application/octet-stream"
    if not isinstance(mime_type, str) or not mime_type.strip():
        msg = f"Attachment '{safe_filename}' mime_type must be a string"
        raise ValueError(msg)
    mime_type = mime_type.strip()

    encoded = file.get("base64")
    if not isinstance(encoded, str) or not encoded.strip():
        msg = f"Attachment '{safe_filename}' is missing base64 content"
        raise ValueError(msg)
    encoded = encoded.strip()

    if max_base64_chars is None:
        if max_bytes == ATTACHMENT_MAX_BYTES:
            max_base64_chars = ATTACHMENT_MAX_BASE64_CHARS
        else:
            max_base64_chars = 4 * math.ceil(max_bytes / 3) + 8

    if len(encoded) > max_base64_chars:
        msg = (
            f"Attachment '{safe_filename}' base64 payload exceeds the "
            f"{max_bytes // (1024 * 1024)} MiB inline limit"
        )
        raise ValueError(msg)

    try:
        content = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError) as exc:
        msg = f"Attachment '{safe_filename}' has invalid base64 content"
        raise ValueError(msg) from exc

    if not content:
        msg = f"Attachment '{safe_filename}' is empty"
        raise ValueError(msg)
    if len(content) > max_bytes:
        msg = (
            f"Attachment '{safe_filename}' exceeds the "
            f"{max_bytes // (1024 * 1024)} MiB inline limit"
        )
        raise ValueError(msg)

    return safe_filename, mime_type, content


def fetch_and_encode_attachment(
    fetch_fn: Callable[[str], bytes | None],
    url: str,
    filename: str,
    mime_type: str | None = None,
    max_bytes: int = ATTACHMENT_MAX_BYTES,
) -> tuple[str | None, str | None, int]:
    """Fetch and base64-encode an attachment.

    Handles size-limit checks, fetching, encoding, and MIME type
    resolution in one place.

    Args:
        fetch_fn: Callable that takes a URL and returns raw bytes,
            or None on failure.
        url: The URL to fetch the attachment from.
        filename: The filename for MIME type detection fallback.
        mime_type: Explicit MIME type. When None the type is guessed
            from *filename* with ``application/octet-stream`` as the
            fallback.
        max_bytes: Maximum allowed file size in bytes.

    Returns:
        A 3-tuple ``(base64_data, resolved_mime_type, fetched_bytes)``.

        On success all three fields are populated.  On failure the
        first two are ``None`` and *fetched_bytes* distinguishes
        the failure mode:

        * ``fetched_bytes == 0`` -- fetch returned ``None`` or
          raised an exception.
        * ``fetched_bytes > 0``  -- downloaded data exceeded
          *max_bytes* (the actual size is returned so callers can
          report it).
    """
    try:
        data_bytes = fetch_fn(url)
    except Exception:
        logger.warning(
            "Failed to fetch attachment '%s' from %s",
            filename,
            url,
            exc_info=True,
        )
        return None, None, 0

    if data_bytes is None:
        logger.warning(
            "Fetch returned None for attachment '%s'",
            filename,
        )
        return None, None, 0

    actual_size = len(data_bytes)

    if actual_size > max_bytes:
        logger.warning(
            "Attachment '%s' fetched size %d exceeds limit %d",
            filename,
            actual_size,
            max_bytes,
        )
        return None, None, actual_size

    encoded = base64.b64encode(data_bytes).decode("ascii")

    if mime_type is None:
        mime_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"

    return encoded, mime_type, actual_size
