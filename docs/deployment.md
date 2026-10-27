# Portable deployment baseline

No deployment has been performed. Hosting choice, DNS, TLS and costs require owner decisions. The supplied Docker image is the baseline for any existing host that runs Linux containers; no Azure SDK or managed service is required.

```sh
docker build -t authenticated-mcp:local .
docker run --rm --name authenticated-mcp --env-file .env \
  -p 127.0.0.1:8000:8000 --read-only --tmpfs /tmp \
  --cap-drop ALL --security-opt no-new-privileges authenticated-mcp:local
```

The image runs as numeric non-root user 10001, installs only locked runtime dependencies and copies only app source. `.env` and keys are excluded. Python and uv versions are pinned, and the Python base image is pinned by its resolved digest. Keep the lock and Python patch current through tested updates.

For local inspection, GET `/healthz` returns 200 and unauthenticated POST `/mcp` returns 401. Do not expose loopback HTTP to remote clients. Put a public HTTPS reverse proxy in front for real OAuth. Set MCP_PUBLIC_URL to the exact canonical HTTPS `/mcp` URL before running; metadata must never be built from an untrusted Host header. Preserve Authorization, WWW-Authenticate, Accept and MCP headers, pass all transport methods, and disable response buffering if enabling streaming later. Set body/header size limits, request timeouts and rate limits at the edge. Avoid logging request headers, bodies, query strings or tokens at every layer. No arbitrary forwarded headers are trusted.

Firewall: public ingress only HTTPS to the proxy, internal TCP 8000 only from that proxy; outbound HTTPS to login.microsoftonline.com for discovery/JWKS and necessary DNS. Certificate validation stays enabled. Do not replace API validation with platform authentication that drops/rewrites tokens. The health route is public liveness; monitor authentication failures separately without identity/token data.

## Azure guidance — host undecided, UNTESTED

Confirm the existing personal subscription's tenant and Entra privileges independently. The owner must select an existing container-capable host (for example an existing VM or an already-provisioned container platform), confirm pricing and network/TLS configuration, and authorize any later changes. No `az` provisioning commands or infrastructure resources are included. Adapt the Docker run contract to that host's port, environment and reverse-proxy facilities; verify all MCP methods and metadata routes over the external URL. Built-in platform authentication can conflict with direct Bearer validation; inspect its behavior before using it. No paid service or secret store has been created.

This API has no client secret. Treat environment configuration as private operational data; OAuth client credentials belong in the client platform's protected settings, never image build arguments or source. Bind `.env` only at runtime and restrict local permissions.

Release only after live acceptance gates pass. Tag the image with the reviewed git commit, retain the previous image/config, and verify metadata, health, member success and non-member denial. Roll back by restoring that previous image and compatible configuration; do not weaken authorization to restore service. Stateless transport needs no persisted session store.

Redacted application examples:

```json
{"event":"auth_allowed"}
{"event":"auth_denied","status":401,"reason":"invalid_token"}
{"event":"auth_denied","status":403,"reason":"access_denied"}
```

## GitHub Actions → existing Azure App Service `voice-mcp`

The owner authorized direct Python source deployment on 2026-10-27. This supersedes
“host undecided” above for this particular host; the portable Docker baseline remains
available. `.github/workflows/deploy-azure.yml` deploys pushes to `main` and supports
manual reruns on `main`. Changes are submitted through a PR; only Rajesh merges to
`main`. Feature-branch pushes and PR checks never deploy. Deployments are serialized and only run after `make check`.
The target is `https://voice-mcp-a9d2g0bpfaaebjhq.westus3-01.azurewebsites.net`.

The owner enters the **repository** secret `AZURE_WEBAPP_PUBLISH_PROFILE` in GitHub.
The workflow checks presence as a boolean, then passes the value only to the pinned
Azure deployment action. Never paste a profile into code, a chat, or a workflow log.
SCM basic authentication was enabled by the owner; this workflow does not modify it.

The ZIP contains only `app/`, `startup.sh`, `.deployment`, `DEPLOYMENT_COMMIT` and
runtime `requirements.txt` exported from `uv.lock` with hashes and `--require-hashes`.
It excludes `.env`, local virtualenvs, tests and credentials. The repository-owned
`.deployment` file requests Kudu/Oryx build automation for this source package, so
Azure installs the exact locked runtime packages. No Azure app-setting APIs are called.
Do not use run-from-package mode with this remote-build strategy. If a host override
prevents the remote build, the owner must inspect it; the workflow does not change
Azure settings to compensate.

### Owner configuration prerequisite — not assumed or changed by the workflow

Verify these in the existing `voice-mcp` App Service before expecting healthy startup:

- Linux runtime **Python 3.12**.
- **Settings → Configuration → General settings → Startup Command:** `bash startup.sh`.
  This ASGI factory is not auto-detected as Flask/Django. With a publish profile,
  the deployment action cannot set the startup command; the owner controls it.
- Runtime environment variables from the README: `MCP_PUBLIC_URL` must equal
  `https://voice-mcp-a9d2g0bpfaaebjhq.westus3-01.azurewebsites.net/mcp`;
  `AUTH_PROVIDER=entra`; actual `TENANT_ID`; exact tenant-specific `OIDC_ISSUER`;
  `JWT_AUDIENCE` verified against a real API access token; `REQUIRED_SCOPES=mcp.access`;
  actual `ALLOWED_GROUP_IDS`; `LOG_LEVEL=INFO`. Discovery URL is optional.
  No example tenant/group/audience values are uploaded or filled automatically.
- Existing Entra resource URI/scope alignment, TLS and firewall policy still require
  the owner's verification; deployment does not create or edit Entra registrations.

A successful Azure deploy step proves source delivery/build acceptance, not healthy
startup. The next step independently retries `/healthz`, canonical resource metadata,
and an unauthenticated `/mcp` 401 challenge. A failed readiness step after successful
deployment must be reported separately. These probes use no credentials and cannot
prove a real Entra sign-in, group membership result, or ChatGPT/Claude compatibility.
After owner configuration is corrected, rerun the failed workflow or dispatch it on
`main`. A missing secret fails before any deployment is attempted.

References checked 2026-10-27: [App Service Python startup/build](https://learn.microsoft.com/en-us/azure/app-service/configure-language-python),
[Azure deployment action limitations](https://github.com/Azure/webapps-deploy), and
[Kudu repository deployment settings](https://github.com/projectkudu/kudu/wiki/Configurable-settings).
