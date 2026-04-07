"""Authentication API operations."""

import os
import subprocess
import sys
from pathlib import Path
from typing import Optional

import requests
import yaml
from rich.console import Console

console = Console(file=sys.stderr)


class AuthAPI:
    """Handles authentication operations with GitLab instances."""

    @staticmethod
    def get_current_user() -> Optional[dict]:
        """Fetch the current authenticated user from GitLab API.

        Returns:
            User data dict or None if not authenticated
        """
        from .client import GitLabClient

        try:
            result = GitLabClient._run_api_request("user")
            return result
        except requests.HTTPError:
            return None
        except Exception:
            return None

    @staticmethod
    def check_auth_with_url(gitlab_url: str, token: Optional[str] = None) -> dict:
        """Check authentication status for a specific GitLab URL.

        Args:
            gitlab_url: The GitLab instance URL
            token: Optional token to check (uses configured token if not provided)

        Returns:
            Dict with authentication status info
        """
        from .client import GitLabClient

        hostname = gitlab_url.replace("https://", "").replace("http://", "").rstrip("/")
        is_gitlab_com = hostname == "gitlab.com"

        result = {
            "hostname": hostname,
            "base_url": gitlab_url,
            "api_protocol": "https",
            "is_authenticated": False,
            "username": None,
            "user_id": None,
            "user_email": None,
            "token_source": None,
            "token_name": None,
            "git_protocol": None,
            "error": None,
            "is_gitlab_com": is_gitlab_com,
        }

        # Check for token from various sources
        actual_token = token
        token_source = None

        if not actual_token:
            # Check environment variables
            actual_token = (
                os.getenv("GITLAB_TOKEN")
                or os.getenv("GL_TOKEN")
                or os.getenv("CI_JOB_TOKEN")
                or os.getenv("CI_API_TOKEN")
                or os.getenv("GITLAB_ACCESS_TOKEN")
            )
            if actual_token:
                token_source = "environment variable"

        if not actual_token:
            # Check glab config
            glab_token, glab_host, glab_source = AuthAPI._read_glab_auth(hostname)
            if glab_token:
                actual_token = glab_token
                token_source = glab_source or "glab config"

        if actual_token:
            result["token_source"] = token_source

        # Try to authenticate
        if actual_token:
            # Temporarily set token to test
            original_url = GitLabClient._base_url
            original_token = GitLabClient._token

            GitLabClient.set_base_url(gitlab_url)
            GitLabClient.set_token(actual_token)

            try:
                user_data = AuthAPI.get_current_user()
                if user_data:
                    result["is_authenticated"] = True
                    result["username"] = user_data.get("username")
                    result["user_id"] = user_data.get("id")
                    result["user_email"] = user_data.get("email")
                else:
                    result["error"] = "Invalid token"
            except Exception as e:
                result["error"] = str(e)
            finally:
                # Restore original settings
                GitLabClient.set_base_url(original_url)
                GitLabClient.set_token(original_token)

        return result

    @staticmethod
    def _read_glab_auth(hostname: str) -> tuple:
        """Read authentication from glab config.

        Args:
            hostname: The hostname to look for

        Returns:
            Tuple of (token, hostname, source) or (None, None, None)
        """
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

                    # Try exact hostname match
                    if hostname in hosts:
                        host_config = hosts[hostname]
                        token = host_config.get("token")
                        if token and token.strip():
                            return token, hostname, "glab config file"

                    # Try to find any host with a token
                    for host_name, host_config in hosts.items():
                        token = host_config.get("token")
                        if token and token.strip():
                            return token, host_name, "glab config file"

                except Exception:
                    continue

        return None, None, None

    @staticmethod
    def login_with_token(gitlab_url: str, token: str, token_name: str = "gitlab-toolbox") -> bool:
        """Store authentication token in glab config.

        Args:
            gitlab_url: The GitLab instance URL
            token: The personal access token
            token_name: Name for the token in config

        Returns:
            True if successful, False otherwise
        """
        hostname = gitlab_url.replace("https://", "").replace("http://", "").rstrip("/")

        # Validate token first
        from .client import GitLabClient

        original_url = GitLabClient._base_url
        original_token = GitLabClient._token

        GitLabClient.set_base_url(gitlab_url)
        GitLabClient.set_token(token)

        try:
            user_data = AuthAPI.get_current_user()
            if not user_data:
                console.print("[red]Invalid token - could not authenticate.[/red]")
                return False
        except Exception as e:
            console.print(f"[red]Authentication failed: {e}[/red]")
            return False
        finally:
            GitLabClient.set_base_url(original_url)
            GitLabClient.set_token(original_token)

        # Now configure glab
        try:
            # Try using glab CLI
            result = subprocess.run(
                ["glab", "auth", "login", "--hostname", hostname, "--token", token],
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode == 0:
                console.print(f"[green]Successfully authenticated to {hostname}.[/green]")
                return True

            # Fallback: write config directly
            console.print("[yellow]glab CLI not available, writing config directly...[/yellow]")
            AuthAPI._write_glab_config(hostname, token)
            return True

        except FileNotFoundError:
            # glab not installed, write config directly
            console.print("[yellow]glab CLI not found, writing config directly...[/yellow]")
            return AuthAPI._write_glab_config(hostname, token)
        except Exception as e:
            console.print(f"[red]Failed to configure authentication: {e}[/red]")
            return False

    @staticmethod
    def _write_glab_config(hostname: str, token: str) -> bool:
        """Write authentication config directly.

        Args:
            hostname: The GitLab hostname
            token: The authentication token

        Returns:
            True if successful
        """
        config_dir = Path.home() / ".config" / "glab-cli"
        config_dir.mkdir(parents=True, exist_ok=True)
        config_path = config_dir / "config.yml"

        config = {}
        if config_path.exists():
            try:
                with open(config_path, "r") as f:
                    config = yaml.safe_load(f) or {}
            except Exception:
                pass

        if "hosts" not in config:
            config["hosts"] = {}

        config["hosts"][hostname] = {
            "token": token,
            "api_protocol": "https",
            "git_protocol": "https",
        }

        try:
            with open(config_path, "w") as f:
                yaml.dump(config, f, default_flow_style=False)
            console.print(f"[green]Configuration saved to {config_path}[/green]")
            return True
        except Exception as e:
            console.print(f"[red]Failed to write config: {e}[/red]")
            return False

    @staticmethod
    def logout(hostname: Optional[str] = None) -> bool:
        """Remove authentication for a hostname.

        Args:
            hostname: The hostname to logout from (uses configured if not provided)

        Returns:
            True if successful
        """
        from .client import GitLabClient

        if not hostname:
            hostname = (
                GitLabClient._base_url.replace("https://", "").replace("http://", "").rstrip("/")
            )

        try:
            # Try glab CLI first
            result = subprocess.run(
                ["glab", "auth", "logout", "--hostname", hostname],
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result.returncode == 0:
                console.print(f"[green]Logged out from {hostname}.[/green]")
                return True

        except FileNotFoundError:
            pass
        except Exception:
            pass

        # Fallback: modify config directly
        return AuthAPI._remove_glab_auth(hostname)

    @staticmethod
    def _remove_glab_auth(hostname: str) -> bool:
        """Remove authentication from glab config.

        Args:
            hostname: The hostname to remove

        Returns:
            True if successful
        """
        config_path = Path.home() / ".config" / "glab-cli" / "config.yml"

        if not config_path.exists():
            console.print(f"[yellow]No configuration found for {hostname}.[/yellow]")
            return True

        try:
            with open(config_path, "r") as f:
                config = yaml.safe_load(f) or {}

            if "hosts" in config and hostname in config["hosts"]:
                del config["hosts"][hostname]
                console.print(f"[green]Removed authentication for {hostname}.[/green]")
            else:
                console.print(f"[yellow]No authentication found for {hostname}.[/yellow]")

            with open(config_path, "w") as f:
                yaml.dump(config, f, default_flow_style=False)

            return True

        except Exception as e:
            console.print(f"[red]Failed to remove authentication: {e}[/red]")
            return False

    @staticmethod
    def login_interactive() -> bool:
        """Start interactive login flow using glab.

        Returns:
            True if successful
        """
        try:
            console.print("[cyan]Starting interactive GitLab authentication...[/cyan]")
            result = subprocess.run(
                ["glab", "auth", "login", "--interactive"],
                capture_output=True,
                text=True,
                timeout=120,
            )

            if result.returncode == 0:
                console.print("[green]Successfully authenticated.[/green]")
                return True
            else:
                if result.stderr:
                    console.print(f"[red]{result.stderr}[/red]")
                return False

        except FileNotFoundError:
            console.print("[red]glab CLI not found. Please install glab first.[/red]")
            console.print("Visit: https://gitlab.com/gitlab-org/cli")
            return False
        except Exception as e:
            console.print(f"[red]Authentication failed: {e}[/red]")
            return False
