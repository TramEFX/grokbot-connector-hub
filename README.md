# Grok Bot Connector Hub

A **virtual USB hub** for [Grok Bot](https://x.ai/news/introducing-grok-bot): plug a bot into a multi-agent room without exposing that room’s MCP door to the internet.

**Grok Bot is the device. The hub is the plugboard. [Agensis](https://github.com/jasonkneen/agensis) is the first host controller.**

```
Grok Bot                         Hub                         Agensis
────────                         ───                         ───────
custom MCP connector ──tools──►  port + mailbox   ──adapter──► Connector
webhook routine      ◄─doorbell─ presence loop               claim_job
                                 per-port tokens             submit / fail
```

`TramEFX/grokbot-harness-bridge` is the earlier **custom cable** (pull-daemon on the bot host). This repo replaces that topology. That repo stays as-is.

## Why a hub

Grok Bot is an MCP **client** plus a sleepy **webhook routine**. MCP cannot push a tool call into the bot. Multi-agent rooms such as Agensis stamp **presence** on a short TTL when a Connector polls `claim_job`.

If the bot itself polls Agensis:

- a long turn looks offline
- the Agensis `aga_` token and the whole `/backend/mcp` surface end up behind a public tunnel
- the next room means another one-off daemon

The hub owns presence and the harness credential. The bot only sees four tools on **its** port.

## First adapter: Agensis

Agensis agents are members, not sidebars. Run modes are **Direct** (hosted), **Relay** (WebSocket host), and **Connector** (MCP client acts as the agent). This hub seats Grok Bot as a **Connector**.

It speaks only the published Connector tools (`whoami`, `claim_job`, `submit_job_result`, `fail_job`) documented in [`server/MCP.md`](https://github.com/jasonkneen/agensis/blob/main/server/MCP.md). This repository is **not** a fork of Agensis (AGPL-3.0). The hub is MIT.

A Relay adapter (push over the Agensis agent WebSocket instead of polling) is the next adapter to add — same mailbox, same Grok tools.

## Quick start

Python 3.10+, standard library only.

```bash
git clone https://github.com/TramEFX/grokbot-connector-hub.git
cd grokbot-connector-hub
export GCH_DATA_DIR=./data
python3 -m hub port-create studio-bot --adapter agensis
```

That prints a **connector URL** and a **port token** (`gch_…`).

1. In Grok Bot, add a custom MCP connector at `http://127.0.0.1:8787/mcp` (or your Tailscale / named HTTPS URL). Bearer = the port token. Never paste the Agensis `aga_` token into Grok Bot.
2. Create a webhook routine from [`prompts/GROK_BOT_ROUTINE.md`](prompts/GROK_BOT_ROUTINE.md). Save URL + `crsr_` key:

   ```bash
   python3 -m hub port-webhook p_studio-bot --url https://api2.cursor.sh/automations/webhook/… --auth crsr_…
   ```

3. In Agensis: **AI Agents → your agent → MCP tab**. Mint a **Connector** token (not the Relay `agensis connect` command — that rotates the token and switches the agent to Relay).

   ```bash
   python3 -m hub port-agensis p_studio-bot \
     --mcp-url https://YOUR_AGENSIS_HOST/backend/mcp \
     --token aga_…
   ```

4. Serve. Keep Agensis reachable from *this* machine only (localhost, Tailscale, private VPC). Publish **only** the hub `/mcp` if Grok needs a public URL.

   ```bash
   python3 -m hub serve --host 127.0.0.1 --port 8787
   ```

5. @mention the agent in an Agensis channel. The hub claims the job, doorbells the routine, the bot calls `hub_inbox` / `hub_reply`, the hub submits back to Agensis.

Smoke without Agensis:

```bash
python3 -m hub port-create demo --adapter mock
python3 -m hub serve
# another shell:
curl -s -X POST http://127.0.0.1:8787/admin/ports/p_demo/demo-job \
  -H "Authorization: Bearer $GCH_ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"prompt":"Say hi from the hub."}'
```

`gch serve` prints a generated admin token on stderr if `GCH_ADMIN_TOKEN` is unset.

## Port tools (what Grok Bot sees)

| Tool | Role |
| --- | --- |
| `hub_whoami` | Port id, adapter, presence, open job count |
| `hub_inbox` | Open turns, oldest first. Prompt is already composed. |
| `hub_reply` | Deliver the turn to the harness |
| `hub_fail` | Clean failure so the room resumes |

The webhook body is a doorbell only. If the POST is lost, the inbox file / `hub_inbox` still has the job.

## Security model

- One token per port (`gch_…`). Revoke = unplug.
- Agensis `aga_…` never leaves the hub data dir.
- Grok Bot webhook `crsr_…` never leaves the hub data dir.
- Default bind is `127.0.0.1`. Put a named tunnel or Tailscale in front of `/mcp` only — not in front of Agensis.
- Job ids are sanitized before they touch the filesystem.
- Data dir mode `700`, port file mode `600`.

See [`docs/SECURITY.md`](docs/SECURITY.md).

## Layout

```
hub/                runtime, MCP door, CLI, adapters
hub/adapters/agensis.py   first adapter
hub/adapters/mock.py      tests + demo
prompts/            paste-into-Grok-Bot routine
docs/               architecture, Agensis notes, security
tests/              stdlib unittest
```

```bash
PYTHONPATH=. python3 -m unittest discover -s tests -v
```

## Status

v0.1 — usable Connector path for one Grok Bot ↔ one Agensis agent. Planned: Agensis Relay adapter, pairing codes with expiry, OAuth on `/mcp` for the Grok connector UI.

## License

MIT. Agensis is a separate project under AGPL-3.0; see [`NOTICE`](NOTICE).
