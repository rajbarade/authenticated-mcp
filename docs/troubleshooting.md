# Troubleshooting

Client errors intentionally omit sensitive JWT details. Logs show only `auth_allowed` or `auth_denied` with status/reason; use private configuration and local claim inspection to diagnose. Never enable header/body debug dumps.

| Symptom | Check and correction |
| --- | --- |
| Startup fails | All required variables, canonical tenant/group UUIDs, exact tenant v2 issuer, HTTPS `/mcp`, nonempty audience/scopes |
| 401 without token | Expected; follow `WWW-Authenticate` resource_metadata URL |
| Missing metadata challenge | Proxy may strip headers or intercept 401; preserve it and well-known routes |
| invalid signature / unknown kid | Correct API access token, RS256, tenant discovery and JWKS egress; wait up to 30 seconds after new kid, retry; never disable verification |
| Issuer outage | Valid cached keys work for at most five minutes; stale keys fail closed; restore trusted HTTPS egress |
| Wrong iss/tid/ver | Use tenant-specific authority and v2 API tokens; do not use common or v1 issuer |
| Wrong aud | Inspect an actual verified API access token; correct client API permission/resource and exact JWT_AUDIENCE; no multiple guessed values |
| Expired/future token | Refresh token through client, verify host time synchronization; zero extra clock leeway |
| Missing scp / ID token / app-only | Request delegated access token for this API through user code+PKCE flow |
| 403 insufficient_scope | Request qualified scope from metadata and consent; compare short scp value to REQUIRED_SCOPES |
| 403 access_denied | Compare group UUIDs; access-token group claims must be enabled; acquire new token after group changes |
| Missing groups / overage | Denied by design; no Graph fallback. Reduce membership or scope a future authorized enhancement |
| Redirect mismatch | Copy exact client UI callback to the correct Entra client registration; check scheme/path and tenant |
| Consent error | Check delegated API permission, allowed consent policy and owner/admin consent |
| OAuth discovery/client registration blocked | Check client's predefined-client option and actual S256 metadata; see oauth-clients.md; do not add a proxy implicitly |
| Healthy but cannot authenticate | Health is process liveness, not Entra reachability or configuration validation against a live tenant |

For any live failure, record client name/version, deployed commit, time and redacted status; never include an access token, refresh token, client secret, or authorization code.
