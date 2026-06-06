"""
OAuth Device Code login helpers for interactive repository discovery.

Description:
    Implements GitHub OAuth Device Flow and GitLab Device Authorization Grant
    using standard-library HTTP calls. Tokens are returned to the caller and
    mirrored into process environment variables only for the current process.
Classes:
    DeviceAuthorization:
        Device authorization response shown to the user.
    DeviceCodeLoginError:
        Raised when Device Code login cannot complete.
Functions:
    fetch_github_device_code_token:
        Run GitHub Device Code login and return an access token.
    fetch_gitlab_device_code_token:
        Run GitLab Device Authorization Grant and return an access token.
"""

from __future__ import annotations

import json
import time
import webbrowser
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError
from urllib.parse import urlencode, urljoin
from urllib.request import Request, urlopen

from analyze_git_repo_loc.i18n import tr

DEVICE_CODE_GRANT_TYPE = "urn:ietf:params:oauth:grant-type:device_code"
DEFAULT_GITHUB_SCOPES = ("repo", "read:org")
DEFAULT_GITLAB_SCOPES = ("read_api", "read_repository")


@dataclass(frozen=True)
class DeviceAuthorization:
    """Device authorization details displayed before polling."""

    device_code: str
    user_code: str
    verification_uri: str
    expires_in: int
    interval: int


class DeviceCodeLoginError(ValueError):
    """Device Code login failed."""


def _post_form_json(url: str, data: dict[str, str]) -> dict[str, Any]:
    encoded = urlencode(data).encode("utf-8")
    request = Request(
        url,
        data=encoded,
        headers={
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "analyze-git-repo-loc",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=30) as response:
            raw = response.read().decode("utf-8")
    except HTTPError as ex:
        details = ""
        if ex.fp is not None:
            details = ex.fp.read().decode("utf-8", errors="replace").strip()
        suffix = f": {details}" if details else ""
        raise DeviceCodeLoginError(
            f"OAuth Device Code endpoint returned HTTP {ex.code} {ex.reason}{suffix}"
        ) from ex
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise DeviceCodeLoginError("OAuth response must be a JSON object.")
    return payload


def _read_device_authorization(payload: dict[str, Any]) -> DeviceAuthorization:
    try:
        device_code = str(payload["device_code"])
        user_code = str(payload["user_code"])
        verification_uri = str(payload["verification_uri"])
    except KeyError as ex:
        raise DeviceCodeLoginError(
            "OAuth device authorization response is incomplete."
        ) from ex
    return DeviceAuthorization(
        device_code=device_code,
        user_code=user_code,
        verification_uri=verification_uri,
        expires_in=int(payload.get("expires_in") or 900),
        interval=int(payload.get("interval") or 5),
    )


def _default_notify(authorization: DeviceAuthorization) -> None:
    print()
    print(tr("auth.device.required"))
    print(tr("auth.device.open", uri=authorization.verification_uri))
    print(tr("auth.device.code", code=authorization.user_code))
    print(tr("auth.device.waiting"))
    try:
        webbrowser.open(authorization.verification_uri)
    except (webbrowser.Error, OSError):
        # Ignore failures to open the browser (non-fatal for device flow)
        pass


def _poll_device_token(
    *,
    token_url: str,
    client_id: str,
    authorization: DeviceAuthorization,
    sleep: Callable[[float], None],
) -> str:
    interval = authorization.interval
    deadline = time.monotonic() + authorization.expires_in
    while time.monotonic() < deadline:
        sleep(interval)
        payload = _post_form_json(
            token_url,
            {
                "client_id": client_id,
                "device_code": authorization.device_code,
                "grant_type": DEVICE_CODE_GRANT_TYPE,
            },
        )
        access_token = payload.get("access_token")
        if isinstance(access_token, str) and access_token:
            return access_token

        error = str(payload.get("error") or "")
        if error == "authorization_pending":
            continue
        if error == "slow_down":
            interval += 5
            continue
        if error in {"access_denied", "expired_token", "token_expired"}:
            raise DeviceCodeLoginError(f"OAuth Device Code login failed: {error}")
        if error:
            raise DeviceCodeLoginError(f"OAuth Device Code login failed: {error}")
        raise DeviceCodeLoginError(
            "OAuth token response did not include an access token."
        )
    raise DeviceCodeLoginError("OAuth Device Code login expired before authorization.")


def fetch_github_device_code_token(
    *,
    client_id: str,
    scopes: tuple[str, ...],
    notify: Callable[[DeviceAuthorization], None] | None = None,
    sleep: Callable[[float], None] = time.sleep,
) -> str:
    """
    Run GitHub OAuth Device Flow and return an access token.

    Args:
        client_id (str): OAuth App client ID.
        scopes (tuple[str, ...]): OAuth scopes to request.
        notify (Callable | None): Callback that displays user code details.
        sleep (Callable): Sleep function used between polling attempts.

    Returns:
        str: Access token returned by GitHub.
    """
    authorization = _read_device_authorization(
        _post_form_json(
            "https://github.com/login/device/code",
            {"client_id": client_id, "scope": " ".join(scopes)},
        )
    )
    (notify or _default_notify)(authorization)
    return _poll_device_token(
        token_url="https://github.com/login/oauth/access_token",
        client_id=client_id,
        authorization=authorization,
        sleep=sleep,
    )


def fetch_gitlab_device_code_token(
    *,
    base_url: str,
    client_id: str,
    scopes: tuple[str, ...],
    notify: Callable[[DeviceAuthorization], None] | None = None,
    sleep: Callable[[float], None] = time.sleep,
) -> str:
    """
    Run GitLab Device Authorization Grant and return an access token.

    Args:
        base_url (str): GitLab instance base URL.
        client_id (str): OAuth application ID.
        scopes (tuple[str, ...]): OAuth scopes to request.
        notify (Callable | None): Callback that displays user code details.
        sleep (Callable): Sleep function used between polling attempts.

    Returns:
        str: Access token returned by GitLab.
    """
    normalized_base_url = base_url.rstrip("/")
    authorization = _read_device_authorization(
        _post_form_json(
            urljoin(f"{normalized_base_url}/", "oauth/authorize_device"),
            {"client_id": client_id, "scope": " ".join(scopes)},
        )
    )
    (notify or _default_notify)(authorization)
    return _poll_device_token(
        token_url=urljoin(f"{normalized_base_url}/", "oauth/token"),
        client_id=client_id,
        authorization=authorization,
        sleep=sleep,
    )
