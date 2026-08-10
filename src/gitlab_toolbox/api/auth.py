"""Read-only authentication checks and glab credential fallback."""

import os
from typing import Optional

import requests

from .client import GitLabClient


class AuthAPI:
    """Checks GitLab authentication without managing credentials."""

    @staticmethod
    def get_current_user() -> Optional[dict]:
        """Fetch the current authenticated user, if any."""
        try:
            return GitLabClient._run_api_request("user", suppress_errors=True)
        except requests.RequestException:
            return None

    @staticmethod
    def _environment_token() -> Optional[str]:
        """Return the first configured token environment variable."""
        return (
            os.getenv("GITLAB_TOKEN")
            or os.getenv("GL_TOKEN")
            or os.getenv("CI_JOB_TOKEN")
            or os.getenv("CI_API_TOKEN")
            or os.getenv("GITLAB_ACCESS_TOKEN")
        )

    @classmethod
    def _check_token(cls, gitlab_url: str, token: str) -> Optional[dict]:
        """Validate a token against ``/user`` without changing client state."""
        original_url = GitLabClient._base_url
        original_token = GitLabClient._token
        GitLabClient.set_base_url(gitlab_url)
        GitLabClient.set_token(token)
        try:
            return cls.get_current_user()
        finally:
            GitLabClient.set_base_url(original_url)
            GitLabClient.set_token(original_token)

    @classmethod
    def check_auth_with_url(cls, gitlab_url: str, token: Optional[str] = None) -> dict:
        """Check authentication, falling back to existing glab credentials.

        An explicit token or an environment token is validated first. Only after it
        is unavailable or invalid is the existing credential for the same GitLab
        host read from the user's glab configuration. This method never creates,
        modifies, or deletes glab credentials.
        """
        hostname = gitlab_url.replace("https://", "").replace("http://", "").rstrip("/")
        result = {
            "hostname": hostname,
            "base_url": gitlab_url,
            "api_protocol": "https",
            "is_authenticated": False,
            "username": None,
            "user_id": None,
            "user_email": None,
            "token_source": None,
            "error": "No token available",
            "is_gitlab_com": hostname == "gitlab.com",
        }

        same_client_host = (GitLabClient._base_url or "").rstrip("/") == gitlab_url.rstrip("/")
        configured_token = token or cls._environment_token()
        if not configured_token and same_client_host:
            configured_token = GitLabClient._token
        configured_source = "command option" if token else "configured token"
        if configured_token:
            user_data = cls._check_token(gitlab_url, configured_token)
            if user_data:
                return cls._authenticated_result(result, user_data, configured_source)
            result["error"] = "Invalid token"

        # Only consult glab after no configured credential authenticated. It must
        # belong to the requested host and must not repeat the failed token.
        _, glab_token = GitLabClient._read_glab_config(gitlab_url)
        if glab_token and glab_token != configured_token:
            user_data = cls._check_token(gitlab_url, glab_token)
            if user_data:
                return cls._authenticated_result(result, user_data, "glab authentication")
            result["error"] = "Invalid token"

        return result

    @staticmethod
    def _authenticated_result(result: dict, user_data: dict, source: str) -> dict:
        """Populate a successful authentication-status response."""
        result.update(
            {
                "is_authenticated": True,
                "username": user_data.get("username"),
                "user_id": user_data.get("id"),
                "user_email": user_data.get("email"),
                "token_source": source,
                "error": None,
            }
        )
        return result
