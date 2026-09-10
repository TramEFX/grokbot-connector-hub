# Architecture

## USB metaphor

| USB | Here |
| --- | --- |
| Hub | `gch serve` |
| Port | one `(Grok Bot, room agent)` pair in `ports.json` |
| Device | Grok Bot: MCP client + webhook routine |
| Host controller | adapter (`agensis`, later `agensis-relay`, later others) |
| Plug in | `port-create` + connector install + webhook + adapter creds |
| Unplug | `port-revoke` (rotates the Grok-facing token) |

## Data flow

1. Someone @mentions the Agensis Connector agent.
2. Agensis queues a job and waits for a `claim_job` poller that is present.
3. The hub heartbeat (not the bot) calls `claim_job` every ~3s. Empty polls still stamp presence (~40s TTL on Agensis).
4. On a real job the hub writes the mailbox and POSTs the Grok webhook. The POST is best-effort.
5. The routine wakes, calls `hub_inbox`, does a full Grok Bot turn, calls `hub_reply`.
6. The hub retries `submit_job_result` so a network blip does not leave a claimed job hanging.

Claimed Agensis jobs are reaped on the server (~10 min idle, ~30 min hard). The hub budgets 480s and `fail_job`s past that so the channel resumes.

## Why presence is not on the bot

A Grok Bot turn can block for minutes. If that process is also the `claim_job` loop, the next mention sees "nobody attached" while the bot is working. The earlier pull-daemon split threads on the bot host. The hub is the same split, moved off the bot so more than one device can plug in and the harness credential never sits in the bot.

## Public surface

| Path | Who | Auth |
| --- | --- | --- |
| `POST /mcp` | Grok Bot | port token `gch_…` |
| `GET /health` | probes | none |
| `/admin/*` | operator | `GCH_ADMIN_TOKEN` |

Agensis `/backend/mcp` is only opened from the hub process.
