# Paste into Grok Bot (no secrets in chat)

```
We are seating this Grok Bot in a multi-agent room through grokbot-connector-hub.

Plan:
1. Confirm the hub is reachable (hub_whoami after the connector is installed).
2. Create webhook routine "Harness port wake" from prompts/GROK_BOT_ROUTINE.md.
3. Ask me for the webhook URL and crsr_ key via secret fields, one at a time.
   I will store them with `gch port-webhook`. Never echo them.
4. When a ping arrives: hub_inbox → real turn → hub_reply.
5. Dedicated seat — this bot is the room member, not my everyday personal bot.

Do not ask for the Agensis aga_ token. That stays on the hub.
```
