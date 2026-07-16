# Cloudflare Tunnel controls for shell-capable agents

Condensed deployment notes from official Cloudflare and Hermes documentation reviewed in July 2026. These are version-sensitive: inspect current docs, CLI help, and source before applying them.

## Cloudflare facts

Cloudflare’s self-hosted application documentation distinguishes a tunnel from Access:

- A published application route without an Access application is available to anyone on the Internet.
- Access applications are deny-by-default; a user must match an Allow policy.
- Access can require an identity provider, MFA, and expiring application sessions.
- Cloudflare recommends creating the Access application before publishing the tunnel route.
- Enable **Protect with Access** on `cloudflared` when available so the connector validates the Access application token on behalf of the origin. Origin-side token validation limits damage from routing or proxy misconfiguration.

Authoritative page:
https://developers.cloudflare.com/cloudflare-one/access-controls/applications/http-apps/self-hosted-public-app/

A safe edge policy for a personal agent normally allows one exact identity, requires IdP MFA, uses a bounded session duration, and has no broad bypass rule. Add a final tunnel ingress rule that returns an HTTP error for unmatched hostnames.

## Hermes remote-backend facts

Hermes Desktop connects to `hermes serve` (default port 9119), while messaging channels use the separate `hermes gateway` process. Do not secure one while accidentally publishing the other.

As observed in Hermes Agent v0.18.2:

- `hermes serve --host 127.0.0.1` is loopback/trusted mode; the gated OAuth/session-cookie middleware is off.
- Loopback mode protects sensitive API calls with an ephemeral local session token injected into the SPA. Publishing that UI through a local tunnel can allow a remote visitor to receive the same trusted token.
- A non-loopback bind such as `--host 0.0.0.0` engages the auth gate and refuses to start without a registered provider.
- The legacy `--insecure` option was hardened into a no-op for non-loopback binds. Recheck current behavior rather than relying on the flag in either direction.
- Loopback Host-header validation rejects non-loopback Host values to resist DNS rebinding. Configuring a proxy to rewrite the public hostname to `localhost` can make a tunnel work while also defeating the assumption that only a local operator sees the loopback UI. Host-header rejection is not authorization.
- `/api/status` is intentionally public. Command-capable chat and PTY WebSockets (`/api/ws`, `/api/pty`) use authenticated sessions/tickets in gated mode.
- Hermes recommends Nous OAuth or self-hosted OIDC for public exposure. The bundled single username/password provider is documented for trusted networks or VPNs only.

Authoritative pages:

- https://hermes-agent.nousresearch.com/docs/user-guide/desktop#connecting-to-a-remote-backend
- https://hermes-agent.nousresearch.com/docs/user-guide/features/web-dashboard#authentication-gated-mode

## Safer topology

```text
Internet
  -> Cloudflare Access (exact identity + MFA)
  -> Cloudflare Tunnel
  -> Hermes non-loopback bind with OAuth/OIDC gate
  -> dedicated unprivileged service account
  -> scoped tools, mounts, credentials, and network access
```

If only the owner’s devices connect, prefer Cloudflare private routing with WARP or a private overlay such as Tailscale. This avoids publishing a command surface under a public hostname.

## External verification

From a device outside the origin network:

1. Request the public status endpoint and confirm the application reports authentication required and the intended provider.
2. Request a sensitive endpoint such as configuration without either edge or application credentials; it must redirect to login or return an unauthorized response, never data.
3. Attempt anonymous connections to every command-capable WebSocket; each must fail before a session is created.
4. Confirm the origin port is unreachable through the router, public IP, and LAN paths that should not bypass Access.
5. Test logout, session expiry, MFA, and account revocation.
6. Inspect both Cloudflare Access logs and Hermes audit/application logs.

## Native-client compatibility caveat

Cloudflare Access naturally protects a browser dashboard, but a native desktop client may expect to call the application status endpoint, complete application OAuth, and open WebSockets without Cloudflare-specific headers. Do not assume it can complete an Access challenge. Confirm the client’s documented support and perform an end-to-end test. If incompatible, use private WARP/Tailscale reachability rather than adding unauthenticated Access bypasses.
