# Security

## Tokens

| Token | Prefix | Lives in | Seen by |
| --- | --- | --- | --- |
| Port token | `gch_` | `ports.json` | Grok Bot connector |
| Admin token | `gcha_` | env | operator HTTP |
| Agensis Connector | `aga_` | `adapter_config` | hub → Agensis only |
| Grok webhook | `crsr_` | `webhook_auth` | hub → Grok webhook only |

Revoking a port rotates `gch_`. It does not rotate the Agensis token; do that in the Agensis UI if the bot was compromised.

Never commit `data/`, never paste `aga_` or `crsr_` into chat.

## Network

- Bind `127.0.0.1` unless you know you need otherwise.
- Publish `/mcp` (HTTPS) for Grok Bot. Do not publish Agensis.
- Tailscale / named Cloudflare tunnel to the hub is enough. Quick tunnels are a dev cable.

## Filesystem

Job ids must match `^[A-Za-z0-9._:-]{1,128}$`. Anything else is refused and failed back to Agensis.

Data directory is created `0700`; `ports.json` is `0600`.

## What this v0.1 does not do

- OAuth 2.1 on `/mcp` (Grok custom connectors can use a raw bearer; OAuth comes later)
- Mutual TLS
- Multi-tenant hosting of other people’s bots
- Encryption at rest beyond file mode bits
