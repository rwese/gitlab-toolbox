"""Base GitLab API client using glab CLI."""

import json
import subprocess
import sys
from typing import Any, Dict, List, Optional

from rich.console import Console

console = Console(file=sys.stderr)


class GitLabClient:
    """Base wrapper for GitLab API using glab CLI."""

    # Class variable to store the hostname
    _hostname: Optional[str] = None
    # Class variable to store the repository path
    _repo_path: Optional[str] = None
    # Class variable to enable debug mode
    _debug: bool = False

    @classmethod
    def set_hostname(cls, hostname: Optional[str]) -> None:
        """Set the GitLab hostname for all API calls.

        Args:
            hostname: The GitLab hostname (e.g., 'gitlab.com')
        """
        cls._hostname = hostname

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
        """Run a GraphQL query using glab CLI.

        Args:
            query: GraphQL query string
            variables: Optional variables for the query

        Returns:
            Parsed JSON response
        """
        import json

        # For GraphQL, we need to pass variables as JSON
        if variables:
            # Convert variables to JSON string
            variables_json = json.dumps(variables)
            cmd = [
                "glab",
                "api",
                "graphql",
                "-f",
                f"query={query}",
                "-f",
                f"variables={variables_json}",
            ]
        else:
            cmd = ["glab", "api", "graphql", "-f", f"query={query}"]

        try:
            if cls._debug:
                console.print(f"[dim]Running GraphQL: {query}[/dim]")
                if variables:
                    console.print(f"[dim]Variables: {variables}[/dim]")
                console.print(f"[dim]Command: {' '.join(cmd)}[/dim]")
                if cls._repo_path:
                    console.print(f"[dim]Working directory: {cls._repo_path}[/dim]")

            result = subprocess.run(
                cmd, capture_output=True, text=True, check=True, cwd=cls._repo_path
            )

            if cls._debug and result.stdout:
                console.print(
                    f"[dim]GraphQL Response: {result.stdout[:200]}{'...' if len(result.stdout) > 200 else ''}[/dim]"
                )

            response = json.loads(result.stdout)
            return response
        except subprocess.CalledProcessError as e:
            error_output = e.stdout.strip() if e.stdout else e.stderr.strip()
            try:
                if "{" in error_output:
                    json_start = error_output.index("{")
                    json_str = error_output[json_start:]
                    if "}glab:" in json_str:
                        json_str = json_str[: json_str.index("}glab:") + 1]
                    error_data = json.loads(json_str)
                    if "errors" in error_data:
                        # Handle GraphQL errors
                        for error in error_data["errors"]:
                            console.print(
                                f"[red]GitLab GraphQL error:[/red] {error.get('message', error)}"
                            )
                    elif "message" in error_data:
                        msg = error_data["message"]
                        if isinstance(msg, dict) and "base" in msg:
                            base_msgs = msg["base"]
                            if isinstance(base_msgs, list):
                                console.print(
                                    f"[red]GitLab GraphQL error:[/red] {' '.join(base_msgs)}"
                                )
                            else:
                                console.print(f"[red]GitLab GraphQL error:[/red] {msg}")
                        else:
                            console.print(f"[red]GitLab GraphQL error:[/red] {msg}")
                    else:
                        console.print(f"[red]GitLab GraphQL error:[/red] {error_data}")
                else:
                    console.print(f"[red]GitLab GraphQL error:[/red] {error_output}")
            except json.JSONDecodeError:
                console.print(f"[red]GitLab GraphQL error:[/red] {error_output}")
            raise

    @classmethod
    def _run_glab_command(
        cls, endpoint: str, params: Optional[Dict] = None, method: str = "GET"
    ) -> Any:
        """Run a glab API command and return JSON result.

        Args:
            endpoint: The API endpoint to call
            params: Optional query parameters (for GET) or body fields (for POST/PUT/PATCH)
            method: HTTP method (GET, POST, PUT, DELETE, etc.)

        Returns:
            Parsed JSON response (dict or list)
        """
        cmd = ["glab", "api", endpoint]

        if method != "GET":
            cmd.extend(["-X", method])
            # For POST/PUT/PATCH, pass params as request body fields
            if params:
                for key, value in params.items():
                    cmd.extend(["-f", f"{key}={value}"])
        else:
            # For GET, pass params as query string
            if params:
                query_string = "&".join([f"{key}={value}" for key, value in params.items()])
                endpoint_with_params = f"{endpoint}?{query_string}"
                cmd = ["glab", "api", endpoint_with_params]

        try:
            # Debug: print the command being run
            if cls._debug:
                console.print(f"[dim]Running: {' '.join(cmd)}[/dim]")
                if cls._repo_path:
                    console.print(f"[dim]Working directory: {cls._repo_path}[/dim]")

            result = subprocess.run(
                cmd, capture_output=True, text=True, check=True, cwd=cls._repo_path
            )

            if cls._debug and result.stdout:
                console.print(
                    f"[dim]Response: {result.stdout[:200]}{'...' if len(result.stdout) > 200 else ''}[/dim]"
                )

            return json.loads(result.stdout) if result.stdout else []
        except subprocess.CalledProcessError as e:
            # Parse GitLab API error message if available
            # Check both stdout and stderr for error message
            error_output = e.stdout.strip() if e.stdout else e.stderr.strip()

            try:
                # Try to extract JSON error from output
                if "{" in error_output:
                    json_start = error_output.index("{")
                    # Find the end of JSON (before any glab-specific error text)
                    json_str = error_output[json_start:]
                    # Try to find the end of the JSON object
                    if "}glab:" in json_str:
                        json_str = json_str[: json_str.index("}glab:") + 1]

                    error_data = json.loads(json_str)
                    if "message" in error_data:
                        # Handle nested message structure
                        msg = error_data["message"]
                        if isinstance(msg, dict) and "base" in msg:
                            # Extract base message array and join
                            base_msgs = msg["base"]
                            if isinstance(base_msgs, list):
                                console.print(f"[red]GitLab API error:[/red] {' '.join(base_msgs)}")
                            else:
                                console.print(f"[red]GitLab API error:[/red] {base_msgs}")
                        else:
                            console.print(f"[red]GitLab API error:[/red] {msg}")
                    else:
                        console.print(f"[red]Error running glab command:[/red] {error_output}")
                else:
                    console.print(f"[red]Error running glab command:[/red] {error_output}")
            except (ValueError, json.JSONDecodeError):
                console.print(f"[red]Error running glab command:[/red] {error_output}")
            return [] if "list" in endpoint or "groups" in endpoint else {}
        except json.JSONDecodeError as e:
            console.print(f"[red]Error parsing JSON:[/red] {e}")
            return []

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
            result = cls._run_glab_command(endpoint, params)

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
