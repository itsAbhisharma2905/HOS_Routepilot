"""Small stdlib HTTP adapter shared by external provider services."""

import json
import socket
from collections.abc import Mapping
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .errors import (
    MalformedProviderResponseError,
    ProviderHTTPError,
    ProviderTimeoutError,
    ProviderUnavailableError,
)


def fetch_json(
    base_url: str,
    path: str,
    *,
    params: Mapping[str, Any],
    headers: Mapping[str, str],
    timeout_seconds: float,
    provider_name: str,
) -> Any:
    """GET JSON from a provider and normalize transport failures."""

    query = urlencode({key: value for key, value in params.items() if value is not None})
    url = f"{base_url.rstrip('/')}/{path.lstrip('/')}"
    if query:
        url = f"{url}?{query}"
    request = Request(url, headers=dict(headers), method="GET")

    try:
        with urlopen(request, timeout=timeout_seconds) as response:  # noqa: S310 - URL is configured by the server.
            response_status = getattr(response, "status", None) or response.getcode()
            if response_status >= 400:
                raise ProviderHTTPError(
                    f"{provider_name} returned HTTP {response_status}.",
                )
            raw_body = response.read()
    except HTTPError as exc:
        raise ProviderHTTPError(
            f"{provider_name} returned HTTP {exc.code}.",
        ) from exc
    except (TimeoutError, socket.timeout) as exc:
        raise ProviderTimeoutError(f"{provider_name} did not respond in time.") from exc
    except URLError as exc:
        raise ProviderUnavailableError(f"{provider_name} could not be reached.") from exc
    except OSError as exc:
        raise ProviderUnavailableError(f"{provider_name} could not be reached.") from exc

    try:
        return json.loads(raw_body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError, TypeError) as exc:
        raise MalformedProviderResponseError(
            f"{provider_name} returned invalid JSON.",
        ) from exc
