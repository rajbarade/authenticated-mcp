# authenticated-mcp

Portable FastMCP Streamable HTTP server with a single provider-neutral `hello_world(name="world")` tool. Direct delegated Entra access tokens are required on every `/mcp` request. Signature/claims are verified before the group policy and before MCP dispatch.

**Status:** automated security/MCP tests pass. The owner reports an Entra Inspector connection and a greeting from `hello_world("Rani")` (reported as “Hello Rani”; repository output is `Hello, Rani!`). This is a user-reported positive member flow, not independent verification of token claims or authorization negatives. Actual token inspection, non-member denial, ChatGPT and Claude remain unverified. A new work tenant needs its own registrations, group, consent and host configuration; personal objects do not transfer.

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

## Reuse in another repository or tenant

The runtime and tools contain no personal-tenant credentials. Tests use synthetic IDs.
A work/customer deployment needs new tenant-specific configuration; do not copy a
personal `.env`, publish profile, Inspector cache or token. Detailed tenant provisioning
and consent are handled by the organization's administrators outside this repository.

For v2 access tokens, Microsoft's documented expected `aud` is the **API application
client ID**, not the Inspector/client application's ID. Plan `JWT_AUDIENCE` accordingly,
then verify it against an actual signed API access token before live acceptance; do not
add guessed fallback audiences. [Microsoft claims reference](https://learn.microsoft.com/en-us/entra/identity-platform/access-token-claims-reference).

## Optional App Service source deployment

This section supersedes the earlier pilot-specific deployment targets in `docs/deployment.md`.

Deployment is **disabled by default**, including after copying this repository. The
workflow requires main and `ENABLE_AZURE_DEPLOYMENT=true`; PR/feature-branch pushes
never deploy. All changes go through a PR and owner merge. No settings are created
by the workflow. After reviewing the intended destination, its owner configures:

| Location | Name | Value |
| --- | --- | --- |
| GitHub repository variable | `AZURE_WEBAPP_NAME` | Target App Service resource name |
| GitHub repository variable | `MCP_PUBLIC_URL` | `https://<MCP_HOST>/mcp` |
| GitHub repository secret | `AZURE_WEBAPP_PUBLISH_PROFILE` | Profile for that same target, entered by owner |
| GitHub repository variable | `ENABLE_AZURE_DEPLOYMENT` | Literal `true`, set last to opt in |

GitHub variables do not configure Azure runtime settings. The target must separately
use Linux Python 3.12, Startup Command **`bash startup.sh`**, and the real environment
values in the configuration table above. Publish-profile authentication must be approved
by the host owner. The API and the public Inspector client do not need a client secret
in this server. No Azure/Entra settings are changed by the workflow.

The ZIP contains source plus runtime requirements exported with hashes from `uv.lock`.
`.deployment` requests Kudu/Oryx remote build; `.env`, local virtualenvs and development
packages are excluded. Do not combine this strategy with run-from-package mode.
A missing target fails before upload; absent/false opt-in skips deployment. The probe
has no default hostname and checks only the explicitly configured resource.

**Migration:** existing installations must now set the three repository variables
above before the next deployment. Merging this change alone does not deploy unless
those variables have already been explicitly configured. A skipped job leaves the
running application unchanged. Copying source does not copy GitHub secrets or Entra
registrations/permissions; review any imported repository settings before opting in.

Upload success, healthy startup and real OAuth acceptance are separate milestones.
Placeholder security settings intentionally prevent startup. Do not weaken validation
or repeatedly redeploy to bypass missing tenant setup. After configuration, verify
health 200, canonical metadata and unauthenticated MCP 401, then separately verify
actual token claims, member success and non-member 403. Retain a reviewed known-good
commit/configuration for rollback through the normal PR process.

The current repository and Git history already contain earlier setup documentation
and personal-pilot provenance. This portability change is not a history sanitization
or publication approval; review the intended import scope under work policy before
transferring it. No repository visibility change is required for a private import.
