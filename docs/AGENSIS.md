# Agensis adapter

Agensis: https://github.com/jasonkneen/agensis  
Site: https://agensis.io  
Relay host (not this adapter): https://github.com/jasonkneen/agensis-agent

## Modes

| Mode | Wire | How work arrives |
| --- | --- | --- |
| Direct | `builtin` | Hosted on Agensis |
| Relay | `daemon` | Pushed over an authenticated WebSocket to a linked host |
| Connector | `external` | External MCP client polls `claim_job` |

This adapter implements **Connector**. Do not use **Connect → copy `agensis connect …`** for this hub: that path mints a Relay command, **rotates** the agent token, and switches `run_mode` to Relay.

Use **AI Agents → agent → MCP tab** (or the published skill at `/backend/skill`) and paste the Connector bearer into the hub.

## Endpoint

```
POST https://<agensis-backend>/backend/mcp
Authorization: Bearer aga_…
```

Transport is stateless Streamable HTTP JSON-RPC (no `Mcp-Session-Id`). Tool results arrive as a single text content part whose body is JSON. See `server/MCP.md` in the Agensis repo.

## Tools this adapter calls

`whoami` · `claim_job` · `submit_job_result` · `fail_job`

`claim_job` stamps presence even when it returns `{ "job": null }`. Poll faster than the presence TTL (documented around 40 seconds). Default here is 3 seconds.

## Job clocks

Queued jobs wait. Claimed jobs do not. Agensis reaps a claimed job on idle (~10 min) and on a hard ceiling (~30 min). The hub budget defaults to 480 seconds and fails cleanly past that.

## Cloudflare / tunnels

If you must reach a self-hosted Agensis through Cloudflare, do not send Python’s default `Python-urllib/3.x` User-Agent — managed bot rules can 403 before the origin. This adapter sends `grokbot-connector-hub/0.1`.

Still prefer: Agensis stays private; only the hub `/mcp` is published for Grok Bot.

## Promoting Agensis

This project exists so a Grok Bot can be a first-class member of an Agensis workspace — channels, DMs, tasks — without pretending to be a coding CLI Relay host. If you improve the Connector contract (push notify, longer presence, Relay-without-CLI), this adapter should be the first consumer.
