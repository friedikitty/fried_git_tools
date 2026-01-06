#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unit tests for git_sync_util module.

Run with: python -m pytest test_git_sync_util.py
Or: python test_git_sync_util.py
"""

import unittest
from git_sync_util import sanitize_remote_url


class TestSanitizeRemoteUrl(unittest.TestCase):
    """Test cases for sanitize_remote_url function."""

    def test_empty_url(self):
        """Test that empty URLs are returned as-is."""
        self.assertEqual(sanitize_remote_url(""), "")
        self.assertEqual(sanitize_remote_url(None), None)

    def test_no_auth_https(self):
        """Test URLs without authentication are returned as-is."""
        url = "https://github.com/user/repo.git"
        self.assertEqual(sanitize_remote_url(url), url)

    def test_no_auth_http(self):
        """Test HTTP URLs without authentication."""
        url = "http://example.com/repo.git"
        self.assertEqual(sanitize_remote_url(url), url)

    def test_token_only_https(self):
        """Test HTTPS URLs with token only (no username)."""
        url = "https://ghp_token123@github.com/user/repo.git"
        expected = "https://***@github.com/user/repo.git"
        self.assertEqual(sanitize_remote_url(url), expected)

    def test_user_token_https(self):
        """Test HTTPS URLs with user:token format."""
        url = "https://user:token456@github.com/user/repo.git"
        expected = "https://user:***@github.com/user/repo.git"
        self.assertEqual(sanitize_remote_url(url), expected)

    def test_x_access_token(self):
        """Test GitHub x-access-token format."""
        url = "https://x-access-token:ghp_abc123@github.com/user/repo.git"
        expected = "https://x-access-token:***@github.com/user/repo.git"
        self.assertEqual(sanitize_remote_url(url), expected)

    def test_oauth_token(self):
        """Test OAuth token format."""
        url = "https://oauth2:token_xyz@gitlab.com/user/repo.git"
        expected = "https://oauth2:***@gitlab.com/user/repo.git"
        self.assertEqual(sanitize_remote_url(url), expected)

    def test_ssh_git_standard(self):
        """Test standard SSH git@ format (should not be masked)."""
        url = "git@github.com:user/repo.git"
        self.assertEqual(sanitize_remote_url(url), url)

    def test_ssh_git_protocol(self):
        """Test ssh://git@ format (should not be masked)."""
        url = "ssh://git@github.com/user/repo.git"
        self.assertEqual(sanitize_remote_url(url), url)

    def test_ssh_with_token(self):
        """Test SSH URL with token (should be masked)."""
        url = "ssh://token123@github.com/user/repo.git"
        expected = "ssh://***@github.com/user/repo.git"
        self.assertEqual(sanitize_remote_url(url), expected)

    def test_ssh_with_user_token(self):
        """Test SSH URL with user:token format."""
        url = "ssh://user:token456@github.com/user/repo.git"
        expected = "ssh://user:***@github.com/user/repo.git"
        self.assertEqual(sanitize_remote_url(url), expected)

    def test_url_with_port(self):
        """Test URL with port number."""
        url = "https://user:token@github.com:443/user/repo.git"
        expected = "https://user:***@github.com:443/user/repo.git"
        self.assertEqual(sanitize_remote_url(url), expected)

    def test_url_with_port_token_only(self):
        """Test URL with port and token only."""
        url = "https://token@github.com:443/user/repo.git"
        expected = "https://***@github.com:443/user/repo.git"
        self.assertEqual(sanitize_remote_url(url), expected)

    def test_git_plus_https(self):
        """Test git+https:// URL format."""
        url = "git+https://token@github.com/user/repo.git"
        expected = "git+https://***@github.com/user/repo.git"
        self.assertEqual(sanitize_remote_url(url), expected)

    def test_git_plus_https_user_token(self):
        """Test git+https:// with user:token."""
        url = "git+https://user:token@github.com/user/repo.git"
        expected = "git+https://user:***@github.com/user/repo.git"
        self.assertEqual(sanitize_remote_url(url), expected)

    def test_url_with_path_and_query(self):
        """Test URL with path and query parameters."""
        url = "https://user:token@github.com/user/repo.git?ref=main&depth=1"
        expected = "https://user:***@github.com/user/repo.git?ref=main&depth=1"
        self.assertEqual(sanitize_remote_url(url), expected)

    def test_url_with_fragment(self):
        """Test URL with fragment."""
        url = "https://user:token@github.com/user/repo.git#main"
        expected = "https://user:***@github.com/user/repo.git#main"
        self.assertEqual(sanitize_remote_url(url), expected)

    def test_custom_hostname(self):
        """Test URL with custom hostname."""
        url = "https://token@git.example.com/user/repo.git"
        expected = "https://***@git.example.com/user/repo.git"
        self.assertEqual(sanitize_remote_url(url), expected)

    def test_long_token(self):
        """Test with a long token."""
        long_token = "a" * 100
        url = f"https://{long_token}@github.com/user/repo.git"
        expected = "https://***@github.com/user/repo.git"
        self.assertEqual(sanitize_remote_url(url), expected)

    def test_special_characters_in_token(self):
        """Test token with special characters."""
        url = "https://user:token-123_abc@github.com/user/repo.git"
        expected = "https://user:***@github.com/user/repo.git"
        self.assertEqual(sanitize_remote_url(url), expected)

    def test_multiple_at_signs(self):
        """Test URL that might have multiple @ signs (edge case)."""
        # This is an invalid URL but should be handled gracefully
        url = "https://user:pass@host@example.com/repo.git"
        # Should mask the first credentials
        result = sanitize_remote_url(url)
        self.assertIn("***", result)
        self.assertNotIn("pass", result)

    def test_ssh_custom_port(self):
        """Test SSH URL with custom port."""
        url = "ssh://git@github.com:2222/user/repo.git"
        # Standard git@ with port should not be masked
        self.assertEqual(sanitize_remote_url(url), url)

    def test_ssh_custom_port_with_token(self):
        """Test SSH URL with custom port and token."""
        url = "ssh://token@github.com:2222/user/repo.git"
        expected = "ssh://***@github.com:2222/user/repo.git"
        self.assertEqual(sanitize_remote_url(url), expected)

    def test_bitbucket_format(self):
        """Test Bitbucket URL format."""
        url = "https://user:token@bitbucket.org/user/repo.git"
        expected = "https://user:***@bitbucket.org/user/repo.git"
        self.assertEqual(sanitize_remote_url(url), expected)

    def test_gitlab_format(self):
        """Test GitLab URL format."""
        url = "https://oauth2:token@gitlab.com/user/repo.git"
        expected = "https://oauth2:***@gitlab.com/user/repo.git"
        self.assertEqual(sanitize_remote_url(url), expected)

    def test_azure_devops_format(self):
        """Test Azure DevOps URL format."""
        url = "https://token@dev.azure.com/org/project/_git/repo"
        expected = "https://***@dev.azure.com/org/project/_git/repo"
        self.assertEqual(sanitize_remote_url(url), expected)

    def test_azure_devops_user_token(self):
        """Test Azure DevOps with user:token."""
        url = "https://user:token@dev.azure.com/org/project/_git/repo"
        expected = "https://user:***@dev.azure.com/org/project/_git/repo"
        self.assertEqual(sanitize_remote_url(url), expected)

    def test_my_remote_url(self):
        """Test my remote URL."""
        url = "https://oauth2:glpat-xK9mP2vL8nQ4rY6wZ3tA@git-internal.nie.somegame.com/some/some.git"
        expected = "https://oauth2:***@git-internal.nie.somegame.com/some/some.git"
        self.assertEqual(sanitize_remote_url(url), expected)


if __name__ == "__main__":
    unittest.main()
