"""
Runtime authentication selection for interactive repository discovery.

Description:
    Detects environment tokens, GitHub/GitLab CLI login tokens, Device Code
    availability, and one-time token entry. The selected token is only mirrored
    into the current process environment for downstream clone compatibility.
Classes:
    AuthChoice:
        Authentication method and runtime values selected interactively.
    AuthMethodStatus:
        Availability details for one authentication method.
Functions:
    build_auth_method_statuses:
        Build ordered authentication options for a provider.
    choose_auto_auth_status:
        Choose a safe non-interactive authentication method when available.
    resolve_auth_choice:
        Resolve the selected authentication method to an access token.
    run_tui_auth_selection:
        Resolve runtime authentication and display labels.
    run_tui_auth_selector:
        Prompt for authentication for all enabled interactive providers.
"""

from __future__ import annotations

import os
import shutil
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

from analyze_git_repo_loc.i18n import tr
from analyze_git_repo_loc.remote.remote_auth import (
    build_host_provider_env_var,
    build_host_token_env_var,
    get_cli_token,
)
from analyze_git_repo_loc.remote.remote_oauth import (
    DEFAULT_GITHUB_SCOPES,
    DEFAULT_GITLAB_SCOPES,
    DeviceCodeLoginError,
    fetch_github_device_code_token,
    fetch_gitlab_device_code_token,
)

GITHUB_DEVICE_CLIENT_ID = ""
GITLAB_DOTCOM_DEVICE_CLIENT_ID = ""
PROMPT_TOOLKIT_REQUIRED_MESSAGE = (
    "prompt_toolkit is required for interactive runs. "
    "Install dependencies with `uv sync --active`."
)


@dataclass(frozen=True)
class AuthChoice:
    """Authentication method selected at runtime."""

    method: str
    token: str | None = None
    client_id: str | None = None


@dataclass(frozen=True)
class AuthMethodStatus:
    """Availability of one interactive authentication method."""

    method: str
    label: str
    available: bool
    detail: str
    token: str | None = None
    client_id: str | None = None


def _provider_label(provider: str) -> str:
    if provider == "github":
        return "GitHub"
    if provider == "gitlab":
        return "GitLab"
    return provider


def _env_var_for_provider(provider: str) -> str:
    if provider == "github":
        return "GITHUB_TOKEN"
    if provider == "gitlab":
        return "GITLAB_TOKEN"
    raise DeviceCodeLoginError(f"Unsupported provider '{provider}'.")


def _command_for_provider(provider: str) -> str:
    if provider == "github":
        return "gh"
    if provider == "gitlab":
        return "glab"
    raise DeviceCodeLoginError(f"Unsupported provider '{provider}'.")


def _hostname_from_base_url(provider: str, base_url: str) -> str:
    if provider == "github" and base_url.rstrip("/") == "https://api.github.com":
        return "github.com"
    parsed = urlparse(base_url)
    return (
        parsed.hostname
        or base_url.replace("https://", "").replace("http://", "").split("/")[0]
    )


def get_device_client_id(provider: str, base_url: str) -> str | None:
    """
    Return the built-in Device Code client ID for a provider when available.

    Args:
        provider (str): `github` or `gitlab`.
        base_url (str): Provider API or instance base URL.

    Returns:
        str | None: Public OAuth client ID, or None when not configured.
    """
    if provider == "github":
        return (
            os.getenv("ANALYZE_GIT_REPO_LOC_GITHUB_CLIENT_ID")
            or GITHUB_DEVICE_CLIENT_ID
            or None
        )
    if provider == "gitlab":
        hostname = _hostname_from_base_url(provider, base_url)
        if hostname == "gitlab.com":
            return (
                os.getenv("ANALYZE_GIT_REPO_LOC_GITLAB_CLIENT_ID")
                or GITLAB_DOTCOM_DEVICE_CLIENT_ID
                or None
            )
        return None
    raise DeviceCodeLoginError(f"Unsupported provider '{provider}'.")


def build_auth_method_statuses(
    *,
    provider: str,
    base_url: str,
    env: Mapping[str, str] | None = None,
    command_exists: Callable[[str], bool] | None = None,
    cli_token_getter: Callable[[str, str], str | None] = get_cli_token,
    device_client_id_getter: Callable[[str, str], str | None] = get_device_client_id,
) -> list[AuthMethodStatus]:
    """
    Build ordered authentication method statuses for a provider.

    Args:
        provider (str): `github` or `gitlab`.
        base_url (str): Provider API or instance base URL.
        env (Mapping): Environment variables.
        command_exists (Callable | None): Command existence checker.
        cli_token_getter (Callable): CLI token getter.
        device_client_id_getter (Callable): Device client ID getter.

    Returns:
        list[AuthMethodStatus]: Ordered method statuses.
    """
    env = os.environ if env is None else env
    command_exists = command_exists or (
        lambda command: shutil.which(command) is not None
    )
    env_var = _env_var_for_provider(provider)
    env_token = env.get(env_var)
    command = _command_for_provider(provider)
    cli_token = (
        cli_token_getter(provider, base_url) if command_exists(command) else None
    )
    client_id = device_client_id_getter(provider, base_url)
    hostname = _hostname_from_base_url(provider, base_url)
    self_hosted_gitlab = provider == "gitlab" and hostname != "gitlab.com"
    device_available = bool(client_id) or self_hosted_gitlab
    if client_id:
        device_detail = "available"
    elif self_hosted_gitlab:
        device_detail = "OAuth client_id will be entered for this run"
    else:
        device_detail = "OAuth client_id is not configured"
    return [
        AuthMethodStatus(
            method="env_token",
            label=f"{env_var} environment variable",
            available=bool(env_token),
            detail="available" if env_token else f"{env_var} is not set",
            token=env_token,
        ),
        AuthMethodStatus(
            method="cli",
            label=f"{command} CLI login",
            available=bool(cli_token),
            detail=(
                "logged in" if cli_token else f"{command} is missing or not logged in"
            ),
            token=cli_token,
        ),
        AuthMethodStatus(
            method="device_code",
            label="Browser Device Code login",
            available=device_available,
            detail=device_detail,
            client_id=client_id,
        ),
        AuthMethodStatus(
            method="one_time_token",
            label="Paste token for this run",
            available=True,
            detail="stored only in this process",
        ),
    ]


def choose_auto_auth_status(
    statuses: list[AuthMethodStatus],
) -> AuthMethodStatus | None:
    """Return a safe non-interactive authentication method when available."""
    for status in statuses:
        if status.method in {"env_token", "cli"} and status.available:
            return status
    return None


def resolve_auth_choice(
    *,
    provider: str,
    base_url: str,
    choice: AuthChoice,
) -> str:
    """
    Resolve a selected authentication choice to a token.

    Args:
        provider (str): `github` or `gitlab`.
        base_url (str): Provider API or instance base URL.
        choice (AuthChoice): Runtime authentication choice.

    Returns:
        str: Access token.
    """
    env_var = _env_var_for_provider(provider)
    token = choice.token
    if choice.method == "device_code":
        if not choice.client_id:
            raise DeviceCodeLoginError("OAuth Device Code login requires a client_id.")
        if provider == "github":
            token = fetch_github_device_code_token(
                client_id=choice.client_id,
                scopes=DEFAULT_GITHUB_SCOPES,
            )
        elif provider == "gitlab":
            token = fetch_gitlab_device_code_token(
                base_url=base_url,
                client_id=choice.client_id,
                scopes=DEFAULT_GITLAB_SCOPES,
            )
        else:
            raise DeviceCodeLoginError(f"Unsupported provider '{provider}'.")
    if not token:
        raise DeviceCodeLoginError(f"{choice.method} did not provide a token.")
    os.environ[env_var] = token
    return token


def _prompt_choice(provider: str, statuses: list[AuthMethodStatus]) -> AuthMethodStatus:
    try:
        from prompt_toolkit import prompt  # pyright: ignore[reportMissingImports]
    except ImportError as ex:
        raise RuntimeError(PROMPT_TOOLKIT_REQUIRED_MESSAGE) from ex

    print()
    print(tr("auth.provider_title", provider=_provider_label(provider)))
    for index, status in enumerate(statuses, start=1):
        mark = "available" if status.available else "unavailable"
        print(f"{index}. {status.label} [{mark}] - {status.detail}")
    default_index = next(
        index for index, status in enumerate(statuses, start=1) if status.available
    )
    while True:
        raw = prompt(f"Select authentication method [{default_index}]: ").strip()
        try:
            selected = default_index if not raw else int(raw)
        except ValueError:
            print(tr("auth.enter_number"))
            continue
        if 1 <= selected <= len(statuses):
            status = statuses[selected - 1]
            if status.available:
                return status
            print(tr("auth.not_available", label=status.label))
        else:
            print(tr("auth.enter_number"))


def _prompt_one_time_token(provider: str) -> str:
    try:
        from prompt_toolkit import prompt  # pyright: ignore[reportMissingImports]
    except ImportError as ex:
        raise RuntimeError(PROMPT_TOOLKIT_REQUIRED_MESSAGE) from ex
    return prompt(
        f"Paste {_provider_label(provider)} token: ", is_password=True
    ).strip()


def _prompt_gitlab_device_client_id() -> str:
    try:
        from prompt_toolkit import prompt  # pyright: ignore[reportMissingImports]
    except ImportError as ex:
        raise RuntimeError(PROMPT_TOOLKIT_REQUIRED_MESSAGE) from ex
    return prompt(tr("auth.gitlab_client_id_prompt")).strip()


def _choice_from_status(provider: str, status: AuthMethodStatus) -> AuthChoice:
    if status.method in {"env_token", "cli"}:
        return AuthChoice(method=status.method, token=status.token)
    if status.method == "device_code":
        client_id = status.client_id
        if provider == "gitlab" and not client_id:
            client_id = _prompt_gitlab_device_client_id()
        return AuthChoice(method=status.method, client_id=client_id)
    return AuthChoice(method=status.method, token=_prompt_one_time_token(provider))


def _auth_label(provider: str, status: AuthMethodStatus) -> str:
    if status.method == "env_token":
        return _env_var_for_provider(provider)
    if status.method == "cli":
        return _command_for_provider(provider)
    if status.method == "device_code":
        return "device code"
    return "one-time token"


def _set_host_token(base_url: str, provider: str, token: str) -> None:
    parsed = urlparse(base_url)
    if parsed.hostname:
        os.environ[build_host_token_env_var(parsed.hostname)] = token
        os.environ[build_host_provider_env_var(parsed.hostname)] = provider


def run_tui_auth_selection(
    settings: Any,
    *,
    auto: bool = False,
) -> tuple[dict[str, str], dict[str, str]]:
    """
    Resolve authentication for enabled GitHub/GitLab providers.

    Args:
        settings (Any): TUI settings from `remote_catalog.load_tui_settings`.
        auto (bool): If True, skip prompts when env or CLI auth is available.

    Returns:
        tuple[dict[str, str], dict[str, str]]: Tokens and non-secret source labels.
    """
    tokens: dict[str, str] = {}
    labels: dict[str, str] = {}
    provider_configs = [
        (
            "github",
            settings.providers.github.enabled,
            settings.providers.github.api_base_url,
        ),
        (
            "gitlab",
            settings.providers.gitlab.enabled,
            settings.providers.gitlab.base_url,
        ),
    ]
    for provider, enabled, base_url in provider_configs:
        if not enabled:
            continue
        statuses = build_auth_method_statuses(provider=provider, base_url=base_url)
        status = choose_auto_auth_status(statuses) if auto else None
        if status is None:
            status = _prompt_choice(provider, statuses)
        token = resolve_auth_choice(
            provider=provider,
            base_url=base_url,
            choice=_choice_from_status(provider, status),
        )
        tokens[provider] = token
        _set_host_token(base_url, provider, token)
        labels[provider] = _auth_label(provider, status)
    return tokens, labels


def run_tui_auth_selector(settings: Any, *, auto: bool = False) -> dict[str, str]:
    """
    Prompt for authentication for enabled GitHub/GitLab providers.

    Args:
        settings (Any): TUI settings from `remote_catalog.load_tui_settings`.
        auto (bool): If True, skip prompts when env or CLI auth is available.

    Returns:
        dict[str, str]: Provider tokens keyed by `github` / `gitlab`.
    """
    tokens, _ = run_tui_auth_selection(settings, auto=auto)
    return tokens
