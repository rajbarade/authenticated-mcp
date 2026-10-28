"""Credential-free checks for the deployed resource; never claims OAuth success."""

import json
import os
import time
import urllib.error
import urllib.request
from urllib.parse import urlsplit


def configured_resource() -> str:
    """Require an owner-supplied HTTPS resource; never fall back to a personal host."""
    resource = os.environ.get("MCP_PUBLIC_URL", "")
    url = urlsplit(resource)
    if (
        url.scheme != "https"
        or not url.hostname
        or url.path != "/mcp"
        or url.username
        or url.password
        or url.query
        or url.fragment
        or any(c.isspace() or c in '"\\' for c in resource)
    ):
        raise ValueError("Set MCP_PUBLIC_URL to the intended HTTPS resource ending in /mcp")
    return resource


def check(resource: str) -> None:
    base = resource.removesuffix("/mcp")
    metadata_url = base + "/.well-known/oauth-protected-resource/mcp"
    with urllib.request.urlopen(base + "/healthz", timeout=8) as response:
        if response.status != 200 or json.load(response) != {"status": "ok"}:
            raise ValueError("health endpoint did not return the MCP application's health response")
    with urllib.request.urlopen(metadata_url, timeout=8) as response:
        metadata = json.load(response)
        if metadata.get("resource") != resource:
            raise ValueError("metadata resource differs from the configured canonical URL")
        if not metadata.get("authorization_servers") or not metadata.get("scopes_supported"):
            raise ValueError("metadata is missing authorization server or scope discovery")
    request = urllib.request.Request(resource, data=b"{}", method="POST")
    try:
        with urllib.request.urlopen(request, timeout=8):
            raise ValueError("unauthenticated MCP request was not rejected")
    except urllib.error.HTTPError as error:
        if error.code != 401 or metadata_url not in error.headers.get("WWW-Authenticate", ""):
            raise ValueError("MCP must return 401 with its canonical discovery challenge") from None


def main() -> None:
    resource = configured_resource()
    for attempt in range(1, 25):
        try:
            check(resource)
        except (OSError, ValueError) as error:
            # Only exception type/status: no response bodies, headers or environment values.
            status = (
                error.code if isinstance(error, urllib.error.HTTPError) else type(error).__name__
            )
            print(f"Public endpoint check {attempt}/24 not ready ({status}).", flush=True)
            if attempt == 24:
                raise SystemExit(
                    "Source deployment completed but app readiness is unverified. Owner: check "
                    "Python 3.12, Startup Command 'bash startup.sh', Oryx build logs and required "
                    "Entra app settings in docs/deployment.md. No Azure settings were changed."
                ) from None
            time.sleep(10)
        else:
            message = (
                "Public checks passed: health 200, canonical protected-resource metadata, "
                "unauthenticated MCP 401 with discovery challenge. "
                "These checks do not verify real Entra authentication "
                "or ChatGPT/Claude compatibility."
            )
            print(message)
            if summary := os.environ.get("GITHUB_STEP_SUMMARY"):
                with open(summary, "a") as output:
                    output.write(message + "\n")
            return


if __name__ == "__main__":
    main()
