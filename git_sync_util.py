# -*- coding: utf-8 -*-
"""
Git Sync Utility Functions

This module contains utility functions for git sync operations.
"""

import re
from urllib.parse import urlparse, urlunparse, ParseResult


def sanitize_remote_url(url: str) -> str:
    """Sanitize remote URL by masking authentication tokens.

    Masks tokens in various URL formats:
    - https://token@host.com/repo.git -> https://***@host.com/repo.git
    - https://user:token@host.com/repo.git -> https://user:***@host.com/repo.git
    - ssh://git@host.com/repo.git -> ssh://git@host.com/repo.git (no change if no token)
    - git@host.com:user/repo.git -> git@host.com:user/repo.git (no change)

    Args:
        url: Remote URL that may contain authentication tokens

    Returns:
        Sanitized URL with tokens masked as ***
    """
    if not url:
        return url

    # Handle SSH URLs (git@host.com:user/repo.git) - these don't typically have tokens in the URL
    if url.startswith("git@") and "://" not in url:
        # Standard SSH format: git@host.com:user/repo.git - no tokens, return as-is
        return url

    # Handle standard URLs (http, https, git+https, ssh://, etc.)
    try:
        parsed = urlparse(url)

        # Check if URL has authentication credentials
        # parsed.password is None if not present, empty string if present but empty
        has_password = parsed.password is not None and parsed.password != ""
        has_username = parsed.username is not None

        # For SSH URLs with "git" username and no password, this is standard and safe
        if (
            parsed.scheme in ("ssh", "")
            and parsed.username == "git"
            and not has_password
        ):
            return url

        if has_password or (has_username and parsed.username not in ("git",)):
            # URL contains authentication info - mask it
            if has_password:
                # Has user:password format - mask password, keep username
                masked_netloc = f"{parsed.username}:***@{parsed.hostname}"
            elif has_username:
                # Has username only (likely a token) - mask username
                # Exception: "git" username is standard for SSH, already handled above
                masked_netloc = f"***@{parsed.hostname}"
            else:
                # Shouldn't happen, but handle it
                masked_netloc = f"***@{parsed.hostname}"

            # Add port if present
            if parsed.port:
                masked_netloc = masked_netloc.replace(
                    f"@{parsed.hostname}", f"@{parsed.hostname}:{parsed.port}"
                )

            # Reconstruct URL with masked credentials
            sanitized = urlunparse(
                ParseResult(
                    scheme=parsed.scheme,
                    netloc=masked_netloc,
                    path=parsed.path,
                    params=parsed.params,
                    query=parsed.query,
                    fragment=parsed.fragment,
                )
            )
            return sanitized
        else:
            # No authentication info, return as-is
            return url
    except Exception:
        # If parsing fails, use regex fallback
        # Match patterns like ://user:token@ or ://token@
        # First handle user:token format
        sanitized = re.sub(r"://([^:@]+):[^@]+@", r"://\1:***@", url)
        # Then handle token-only format (but not common usernames like 'git')
        sanitized = re.sub(r"://(?!git@)[^@]+@", r"://***@", sanitized)
        return sanitized



def deep_merge(target, source):
    """
    Recursively merge source dictionary into target dictionary.
    
    :param target: Target dictionary (will be modified)
    :param source: Dictionary to merge into target
    :return: Merged target dictionary
    """
    for key, value in source.items():
        # Core logic: if key exists and both values are dictionaries, recursively merge
        if (key in target and 
            isinstance(target[key], dict) and 
            isinstance(value, dict)):
            deep_merge(target[key], value)
        else:
            # Otherwise (key does not exist, or one of the values is not a dictionary), overwrite/add
            target[key] = value
    return target