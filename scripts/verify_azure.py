"""Credential-free checks for the deployed resource; never claims OAuth success."""

import json
import os
import time
import urllib.error
import urllib.request

BASE = "https://voice-mcp-a9d2g0bpfaaebjhq.westus3-01.azurewebsites.net"
METADATA = BASE + "/.well-known/oauth-protected-resource/mcp"


def check() -> None:
    with urllib.request.urlopen(BASE + "/healthz", timeout=8) as response:
        if response.status != 200 or json.load(response) != {"status": "ok"}:
            raise ValueError("health endpoint did not return the MCP application's health response")
    with urllib.request.urlopen(METADATA, timeout=8) as response:
        metadata = json.load(response)
        if metadata.get("resource") != BASE + "/mcp":
            raise ValueError("metadata resource differs from the canonical voice-mcp URL")
        if not metadata.get("authorization_servers") or not metadata.get("scopes_supported"):
            raise ValueError("metadata is missing authorization server or scope discovery")
    request = urllib.request.Request(BASE + "/mcp", data=b"{}", method="POST")
    try:
        with urllib.request.urlopen(request, timeout=8):
            raise ValueError("unauthenticated MCP request was not rejected")
    except urllib.error.HTTPError as error:
        if error.code != 401 or METADATA not in error.headers.get("WWW-Authenticate", ""):
            raise ValueError("MCP must return 401 with its canonical discovery challenge") from None


def main() -> None:
    for attempt in range(1, 25):
        try:
            check()
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
                "Real Entra authentication and ChatGPT/Claude remain UNTESTED."
            )
            print(message)
            if summary := os.environ.get("GITHUB_STEP_SUMMARY"):
                with open(summary, "a") as output:
                    output.write(message + "\n")
            return


if __name__ == "__main__":
    main()
