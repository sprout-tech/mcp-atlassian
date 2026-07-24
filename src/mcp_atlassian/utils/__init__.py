"""
Utility functions for the MCP Atlassian integration.
This package provides various utility functions used throughout the codebase.
"""

from .date import parse_date
from .io import is_read_only_mode, validate_safe_path

# Export lifecycle utilities
from .lifecycle import (
    ensure_clean_exit,
    setup_signal_handlers,
)
from .logging import setup_logging
from .media import (
    ATTACHMENT_INLINE_MAX_BASE64_CHARS,
    ATTACHMENT_INLINE_MAX_BYTES,
    ATTACHMENT_MAX_BASE64_CHARS,
    ATTACHMENT_MAX_BYTES,
    ATTACHMENT_MAX_COUNT,
    decode_inline_attachment,
    fetch_and_encode_attachment,
    is_image_attachment,
    sanitize_attachment_filename,
)

# Export OAuth utilities
from .oauth import OAuthConfig, configure_oauth_session
from .ssl import (
    NoProxyAdapter,
    SSLIgnoreAdapter,
    configure_proxy_bypass,
    configure_ssl_verification,
)
from .urls import is_atlassian_cloud_url, resolve_relative_url, validate_url_for_ssrf

# Export all utility functions for backward compatibility
__all__ = [
    "ATTACHMENT_INLINE_MAX_BASE64_CHARS",
    "ATTACHMENT_INLINE_MAX_BYTES",
    "ATTACHMENT_MAX_BASE64_CHARS",
    "ATTACHMENT_MAX_BYTES",
    "ATTACHMENT_MAX_COUNT",
    "NoProxyAdapter",
    "SSLIgnoreAdapter",
    "configure_proxy_bypass",
    "configure_ssl_verification",
    "decode_inline_attachment",
    "is_atlassian_cloud_url",
    "is_image_attachment",
    "is_read_only_mode",
    "sanitize_attachment_filename",
    "validate_safe_path",
    "setup_logging",
    "parse_date",
    "parse_iso8601_date",
    "OAuthConfig",
    "configure_oauth_session",
    "resolve_relative_url",
    "setup_signal_handlers",
    "ensure_clean_exit",
    "fetch_and_encode_attachment",
    "validate_url_for_ssrf",
]
