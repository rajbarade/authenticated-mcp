# authenticated-mcp

Portable FastMCP Streamable HTTP server with a single provider-neutral `hello_world(name="world")` tool. Direct delegated Entra access tokens are required on every `/mcp` request. Signature/claims are verified before the group policy and before MCP dispatch.

**Status:** local synthetic-token tests are implemented. Entra-issued audience inspection, public HTTPS, ChatGPT, and Claude are **UNTESTED / owner-required**. This is a draft implementation, not a completed live acceptance. No Azure resources or app registrations have been created.

## Five-minute local smoke test

Prerequisites: Python 3.12, [uv](https://docs.astral.sh/uv/) (CI uses 0.12.23), and optionally Docker. No cloud credentials are needed for tests.

```sh
uv sync --locked
make check
cp .env.example .env
uv run --locked uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8000 --no-access-log --no-proxy-headers
```

In a second terminal:

```sh
curl -i http://127.0.0.1:8000/healthz
curl -i http://127.0.0.1:8000/.well-known/oauth-protected-resource/mcp
curl -i -X POST http://127.0.0.1:8000/mcp
```

Expect health 200, public metadata 200, then 401 with `WWW-Authenticate` referencing the canonical HTTPS metadata URL. Example configuration only permits this smoke test; it cannot issue or accept real tokens. The test suite generates ephemeral RSA keys, mocks trusted discovery, and exercises actual MCP initialize, initialized notification, tools/list and tools/call without changing production trust.

## Configuration

| Setting | Contract |
| --- | --- |
| MCP_PUBLIC_URL | Exact external HTTPS URL ending `/mcp`; no query/fragment |
| AUTH_PROVIDER | `entra` only |
| TENANT_ID | Canonical tenant UUID; no common/organizations tenant |
| OIDC_ISSUER | `https://login.microsoftonline.com/<TENANT_ID>/v2.0` |
| OIDC_DISCOVERY_URL | Optional; same tenant's standard v2 discovery URL only |
| JWT_AUDIENCE | One exact audience verified from an actual API access token; no guessed fallback |
| REQUIRED_SCOPES | Space-separated short `scp` values; default `mcp.access` |
| ALLOWED_GROUP_IDS | Comma-separated group UUIDs; membership in any permits access |
| LOG_LEVEL | INFO, WARNING, ERROR or CRITICAL; no debug credential logging |

Public metadata advertises fully qualified scopes `<MCP_PUBLIC_URL>/<short scope>`. Keep the Application ID URI aligned with this URL. Environment variables override `.env`. Missing or unsafe configuration fails startup. No client secret belongs in this server.

## Map and guides

`HTTP → auth/middleware → auth/jwt_validator → auth/providers/entra → auth/policies → FastMCP → tools/hello`.

- [Architecture and security boundaries](docs/architecture.md)
- [Owner Entra setup](docs/entra-setup.md)
- [ChatGPT and Claude gates](docs/oauth-clients.md)
- [Testing and live acceptance record](docs/testing.md)
- [Troubleshooting](docs/troubleshooting.md)
- [Docker and Azure deployment guidance](docs/deployment.md)

The complete extracted supplied specification is preserved in [specification-source.txt](docs/specification-source.txt); the original DOCX remains unchanged in Library. All Python direct dependencies are exact-pinned in `pyproject.toml`; `uv.lock` pins the transitive graph and package hashes. Use `--locked` for every install.
