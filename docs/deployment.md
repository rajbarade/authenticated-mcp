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
