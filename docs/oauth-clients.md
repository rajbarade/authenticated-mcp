# Client connection verification

Both outcomes are **UNTESTED / owner-required**, not passed. No public endpoint, registered OAuth clients, tenant credentials, or real access tokens were available. Instructions below are a verification plan, not an assertion of compatibility.

## Common preflight

Fetch `/.well-known/oauth-protected-resource/mcp`; check canonical resource, qualified scopes and tenant authorization server. Verify an unauthenticated `/mcp` call returns its metadata URL in a 401 Bearer challenge. Fetch the advertised tenant's OIDC metadata and inspect authorization/token endpoints, `code_challenge_methods_supported` and registration capabilities. Use a preregistered client; do not assume Entra supports DCR or CIMD. Confirm scope/resource requests actually produce this API's v2 access token. No proxy or alternate provider is included as a workaround.

## ChatGPT — UNTESTED

In the account's MCP/plugin management UI, add the canonical remote URL and select OAuth with a predefined client if available. Copy the exact callback shown in that UI into the Entra client registration; do not guess a universal callback. Supply the registered client credentials only through that UI. Connect, consent, list tools and invoke `hello_world` as both a member and a non-member. Record plan/UI, client ID, redirect URI, date, scopes, audience and redacted outcome privately.

Current [OpenAI authentication documentation](https://developers.openai.com/plugins/build/auth) supports predefined clients and requires discovery to advertise S256 PKCE. **Compatibility gate:** if the actual Entra discovery omits `code_challenge_methods_supported`/S256, ChatGPT's documented requirement is unmet even if Entra supports PKCE operationally. Record BLOCKED, not passed. If this UI only offers DCR/CIMD and cannot use the registered client, also record BLOCKED. The API must not forge Entra metadata to bypass this check.

## Claude — UNTESTED

Under **Customize → Connectors → Add custom connector**, enter the remote URL, choose sign-in, and select **Use your own OAuth client** when available. Register the exact displayed callback in Entra and supply the corresponding client details. Connect, consent, enable the connector for a conversation and call `hello_world`. Repeat as a non-member. Record the same evidence independently from ChatGPT.

The current [Claude connector guide](https://support.claude.com/en/articles/11175166-get-started-with-custom-connectors-using-remote-mcp) describes published identity, automatic registration and own-client choices. Use the own-client route for this direct Entra pilot; do not presume published identity or automatic registration works with Entra. If your account UI lacks the required option, or discovery/resource/consent fails, record the actual blocker and stop.

## Evidence boundary for S256

The OpenAI source above, under “Publish OAuth metadata from your authorization server,” explicitly requires `code_challenge_methods_supported` to include `S256` and says omission is unsupported. This is a documented client requirement checked on 2026-10-25. We have not fetched the owner's tenant discovery document or attempted a ChatGPT connection; no missing-field observation or live failure has been recorded. Treat this as a conditional acceptance gate, not a confirmed Entra incompatibility.

## Acceptance record

| Client | OAuth + PKCE | Observed audience | Tool success | Non-member 403 | Outcome |
| --- | --- | --- | --- | --- | --- |
| ChatGPT | Not run | Not inspected | Not run | Not run | UNTESTED |
| Claude | Not run | Not inspected | Not run | Not run | UNTESTED |

Reviewed official docs on 2026-10-25. UI and provider behavior require live confirmation; at least one real client must pass before the specification's definition of done is satisfied.
