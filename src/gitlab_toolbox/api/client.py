"""Base GitLab API client using HTTP requests."""

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
from rich.console import Console

console = Console(file=sys.stderr)


class GitLabClient:
    """Base wrapper for GitLab API using HTTP requests."""

    # Class variable to store the GitLab instance URL
    _base_url: Optional[str] = None
    # Class variable to store the personal access token
    _token: Optional[str] = None
    # Class variable to store the repository path
    _repo_path: Optional[str] = None
    # Class variable to enable debug mode
    _debug: bool = False
    # Default timeout for requests
    _timeout: int = 30

    @classmethod
    def set_base_url(cls, base_url: Optional[str]) -> None:
        """Set the GitLab instance base URL for all API calls.

        Args:
            base_url: The GitLab instance URL (e.g., 'https://gitlab.com')
        """
        cls._base_url = base_url.rstrip("/") if base_url else None

    @classmethod
    def set_token(cls, token: Optional[str]) -> None:
        """Set the personal access token for authentication.

        Args:
            token: GitLab personal access token
        """
        cls._token = token

    @classmethod
    def _read_glab_config(cls) -> tuple[Optional[str], Optional[str]]:
        """Read configuration from glab config files.

        Prefers hosts that have tokens configured over the default host.

        Returns:
            Tuple of (base_url, token) or (None, None) if not found
        """
        import yaml

        # Try to read from glab config file
        config_paths = [
            Path.home() / ".config" / "glab-cli" / "config.yml",
            Path.home() / ".glab-cli" / "config.yml",
        ]

        for config_path in config_paths:
            if config_path.exists():
                try:
                    with open(config_path, "r") as f:
                        config = yaml.safe_load(f)

                    hosts = config.get("hosts", {})
                    default_host = config.get("host", "gitlab.com")

                    # First, try to find any host that has a token
                    for host_name, host_config in hosts.items():
                        token = host_config.get("token")
                        if token and token.strip():
                            # Construct base URL
                            api_protocol = host_config.get("api_protocol", "https")
                            api_host = host_config.get("api_host", host_name)
                            base_url = f"{api_protocol}://{api_host}"
                            return base_url, token

                    # If no host has a token, fall back to the default host (even without token)
                    if default_host in hosts:
                        host_config = hosts[default_host]
                        api_protocol = host_config.get("api_protocol", "https")
                        api_host = host_config.get("api_host", default_host)
                        base_url = f"{api_protocol}://{api_host}"
                        return base_url, None

                except Exception as e:
                    if cls._debug:
                        console.print(f"[dim]Error reading glab config {config_path}: {e}[/dim]")
                    continue

        return None, None

    @classmethod
    def configure_from_env(cls) -> None:
        """Configure client from environment variables and glab config.

        Priority order (same as glab):
        1. Environment variables
        2. glab config files
        3. Defaults
        """
        # First try environment variables
        base_url = os.getenv("GITLAB_URL") or os.getenv("CI_SERVER_URL")

        token = (
            os.getenv("GITLAB_TOKEN")
            or os.getenv("GL_TOKEN")
            or os.getenv("CI_JOB_TOKEN")
            or os.getenv("CI_API_TOKEN")
            or os.getenv("GITLAB_ACCESS_TOKEN")
        )

        # If we don't have both URL and token from env, try glab config
        if not (base_url and token):
            config_url, config_token = cls._read_glab_config()
            if config_url and not base_url:
                base_url = config_url
            if config_token and not token:
                token = config_token

        # Set defaults if still not configured
        if not base_url:
            base_url = "https://gitlab.com"

        cls.set_base_url(base_url)
        if token:
            cls.set_token(token)

    @classmethod
    def set_hostname(cls, hostname: Optional[str]) -> None:
        """Set the GitLab hostname for all API calls (legacy method).

        Args:
            hostname: The GitLab hostname (e.g., 'gitlab.com')
        """
        if hostname:
            base_url = f"https://{hostname}"
            cls.set_base_url(base_url)
        else:
            cls._base_url = None

    @classmethod
    def set_repo_path(cls, repo_path: Optional[str]) -> None:
        """Set the repository path for all API calls.

        Args:
            repo_path: The path to a Git repository that uses the target GitLab instance
        """
        cls._repo_path = repo_path

    @classmethod
    def set_debug(cls, debug: bool) -> None:
        """Enable or disable debug mode.

        Args:
            debug: Whether to enable debug mode
        """
        cls._debug = debug

    @classmethod
    def _run_graphql_query(cls, query: str, variables: Optional[Dict] = None) -> Any:
        """Run a GraphQL query using HTTP requests.

        Args:
            query: GraphQL query string
            variables: Optional variables for the query

        Returns:
            Parsed JSON response
        """
        if not cls._base_url:
            cls.configure_from_env()
        if not cls._base_url:
            raise ValueError(
                "GitLab base URL not configured. Call set_base_url() or configure_from_env() first."
            )

        url = f"{cls._base_url}/api/graphql"
        headers = {"Content-Type": "application/json"}
        if cls._token:
            headers["Authorization"] = f"Bearer {cls._token}"

        payload = {"query": query}
        if variables:
            payload["variables"] = variables

        try:
            if cls._debug:
                console.print(f"[dim]GraphQL URL: {url}[/dim]")
                console.print(f"[dim]Query: {query[:100]}{'...' if len(query) > 100 else ''}[/dim]")
                if variables:
                    console.print(f"[dim]Variables: {variables}[/dim]")

            response = requests.post(url, json=payload, headers=headers, timeout=cls._timeout)
            response.raise_for_status()

            result = response.json()

            if cls._debug:
                console.print(
                    f"[dim]GraphQL Response: {str(result)[:200]}{'...' if len(str(result)) > 200 else ''}[/dim]"
                )

            # Check for GraphQL errors
            if "errors" in result:
                for error in result["errors"]:
                    console.print(f"[red]GitLab GraphQL error:[/red] {error.get('message', error)}")
                raise requests.HTTPError(f"GraphQL errors: {result['errors']}")

            return result

        except requests.RequestException as e:
            console.print(f"[red]GitLab GraphQL request failed:[/red] {e}")
            raise

    @classmethod
    def _run_api_request(
        cls, endpoint: str, params: Optional[Dict] = None, method: str = "GET"
    ) -> Any:
        """Run a GitLab API request and return JSON result.

        Args:
            endpoint: The API endpoint to call (e.g., 'groups', 'projects/123')
            params: Optional query parameters (for GET) or body data (for POST/PUT/PATCH)
            method: HTTP method (GET, POST, PUT, DELETE, etc.)

        Returns:
            Parsed JSON response (dict or list)
        """
        if not cls._base_url:
            cls.configure_from_env()
        if not cls._base_url:
            raise ValueError(
                "GitLab base URL not configured. Call set_base_url() or configure_from_env() first."
            )

        url = f"{cls._base_url}/api/v4/{endpoint}"

        headers = {"Content-Type": "application/json"}
        if cls._token:
            headers["Authorization"] = f"Bearer {cls._token}"

        try:
            if cls._debug:
                console.print(f"[dim]{method} {url}[/dim]")
                if params and method == "GET":
                    console.print(f"[dim]Query params: {params}[/dim]")
                elif params and method != "GET":
                    console.print(f"[dim]Body: {params}[/dim]")

            if method == "GET":
                response = requests.get(url, headers=headers, params=params, timeout=cls._timeout)
            elif method == "POST":
                response = requests.post(url, headers=headers, json=params, timeout=cls._timeout)
            elif method == "PUT":
                response = requests.put(url, headers=headers, json=params, timeout=cls._timeout)
            elif method == "PATCH":
                response = requests.patch(url, headers=headers, json=params, timeout=cls._timeout)
            elif method == "DELETE":
                response = requests.delete(url, headers=headers, timeout=cls._timeout)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")

            response.raise_for_status()
            result = response.json()

            if cls._debug:
                console.print(
                    f"[dim]Response: {str(result)[:200]}{'...' if len(str(result)) > 200 else ''}[/dim]"
                )

            return result

        except requests.HTTPError as e:
            # Try to parse GitLab API error response
            try:
                error_data = e.response.json() if e.response.content else {}
                if "message" in error_data:
                    msg = error_data["message"]
                    if isinstance(msg, dict) and "base" in msg:
                        base_msgs = msg["base"]
                        if isinstance(base_msgs, list):
                            console.print(f"[red]GitLab API error:[/red] {' '.join(base_msgs)}")
                        else:
                            console.print(f"[red]GitLab API error:[/red] {msg}")
                    else:
                        console.print(f"[red]GitLab API error:[/red] {msg}")
                elif "error" in error_data:
                    console.print(f"[red]GitLab API error:[/red] {error_data['error']}")
                else:
                    console.print(f"[red]GitLab API error:[/red] {error_data}")
            except (ValueError, json.JSONDecodeError):
                console.print(
                    f"[red]GitLab API error:[/red] {e.response.text if e.response else str(e)}"
                )
            raise
        except requests.RequestException as e:
            console.print(f"[red]GitLab API request failed:[/red] {e}")
            raise

    # Legacy alias for backward compatibility
    @classmethod
    def _run_glab_command(
        cls, endpoint: str, params: Optional[Dict] = None, method: str = "GET"
    ) -> Any:
        """Legacy method for backward compatibility."""
        return cls._run_api_request(endpoint, params, method)

    @classmethod
    def paginate(
        cls,
        endpoint: str,
        params: Optional[Dict] = None,
        per_page: int = 100,
        limit: Optional[int] = None,
    ) -> List[Dict]:
        """Fetch all pages from a paginated endpoint.

        Args:
            endpoint: The API endpoint to call
            params: Optional query parameters
            per_page: Number of items per page (default 100, max 100)
            limit: Maximum number of items to fetch (None for all)

        Returns:
            List of all items from all pages (up to limit)
        """
        params = params or {}

        # Optimize per_page based on limit to avoid unnecessary API calls
        if limit:
            per_page = min(limit, per_page)

        params["per_page"] = str(per_page)

        items = []
        page = 1

        while True:
            params["page"] = str(page)
            result = cls._run_api_request(endpoint, params)

            if not result or not isinstance(result, list):
                break

            items.extend(result)

            # Check if we've hit the limit
            if limit and len(items) >= limit:
                items = items[:limit]
                break

            page += 1

            # Check if there are more pages
            if len(result) < per_page:
                break

        return items
