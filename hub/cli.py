"""Operator CLI: pair ports, attach Agensis, serve the hub."""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys

from . import __version__, auth, ports
from .runtime import Runtime
from .server import default_public_base, serve
from .store import default_data_dir


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="gch",
        description="Grok Bot Connector Hub — plug a Grok Bot into Agensis (and later other rooms).",
    )
    parser.add_argument("--data-dir", default=os.environ.get("GCH_DATA_DIR") or str(default_data_dir()))
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_serve = sub.add_parser("serve", help="run the hub HTTP + adapters")
    p_serve.add_argument("--host", default=os.environ.get("GCH_HOST", "127.0.0.1"))
    p_serve.add_argument("--port", type=int, default=int(os.environ.get("GCH_PORT", "8787")))
    p_serve.add_argument("--public-base", default=os.environ.get("GCH_PUBLIC_BASE", ""))
    p_serve.add_argument("--admin-token", default=os.environ.get("GCH_ADMIN_TOKEN", ""))

    p_create = sub.add_parser("port-create", help="create a port and print pairing info")
    p_create.add_argument("name")
    p_create.add_argument("--adapter", default="agensis", choices=("agensis", "mock"))

    sub.add_parser("port-list", help="list ports (secrets redacted)")

    p_web = sub.add_parser("port-webhook", help="save Grok Bot webhook URL + key")
    p_web.add_argument("port_id")
    p_web.add_argument("--url", required=True)
    p_web.add_argument("--auth", required=True, help="crsr_ key or full Authorization header")

    p_ag = sub.add_parser("port-agensis", help="save Agensis Connector URL + aga_ token")
    p_ag.add_argument("port_id")
    p_ag.add_argument("--mcp-url", required=True, help="https://<host>/backend/mcp")
    p_ag.add_argument("--token", required=True, help="aga_ Connector token from the MCP tab")

    p_rev = sub.add_parser("port-revoke", help="unplug a port (rotates its Grok token)")
    p_rev.add_argument("port_id")

    args = parser.parse_args(argv)
    os.environ["GCH_DATA_DIR"] = args.data_dir
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(name)s  %(message)s")

    if args.cmd == "serve":
        return cmd_serve(args)
    if args.cmd == "port-create":
        return cmd_create(args)
    if args.cmd == "port-list":
        return cmd_list(args)
    if args.cmd == "port-webhook":
        ports.set_webhook(args.port_id, args.url, args.auth)
        print("webhook saved for", args.port_id)
        return 0
    if args.cmd == "port-agensis":
        ports.set_adapter_config(args.port_id, {"mcp_url": args.mcp_url, "token": args.token})
        print("agensis credentials saved for", args.port_id)
        print("restart `gch serve` if it is already running so the heartbeat attaches")
        return 0
    if args.cmd == "port-revoke":
        ports.revoke(args.port_id)
        print("revoked", args.port_id)
        return 0
    return 1


def cmd_create(args) -> int:
    port = ports.create(args.name, adapter=args.adapter)
    public = os.environ.get("GCH_PUBLIC_BASE") or "http://127.0.0.1:8787"
    print("Port          ", port["id"])
    print("Adapter       ", port["adapter"])
    print("Connector URL ", public.rstrip("/") + "/mcp")
    print("Port token    ", port["token"])
    print()
    print("1. Grok Bot → add custom MCP connector at that URL, Bearer = port token.")
    print("2. Do not put the Agensis aga_ token in Grok Bot.")
    print("3. Create a webhook routine from prompts/GROK_BOT_ROUTINE.md")
    print("   then:  gch port-webhook %s --url URL --auth crsr_KEY" % port["id"])
    if port["adapter"] == "agensis":
        print("4. Mint a Connector token in Agensis (AI Agents → agent → MCP tab).")
        print("   then:  gch port-agensis %s --mcp-url https://HOST/backend/mcp --token aga_TOKEN" % port["id"])
    print("5. gch serve")
    return 0


def cmd_list(args) -> int:
    rows = [ports.public_view(p) for p in ports.load_all().values()]
    print(json.dumps(rows, indent=2))
    return 0


def cmd_serve(args) -> int:
    admin = args.admin_token or os.environ.get("GCH_ADMIN_TOKEN") or ""
    if not admin:
        admin = auth.new_admin_token()
        print("GCH_ADMIN_TOKEN (generated this run):", admin, file=sys.stderr)
    public = args.public_base or default_public_base(args.host, args.port)
    runtime = Runtime()
    runtime.start_attached()
    print("grokbot-connector-hub", __version__, "data", args.data_dir)
    serve(args.host, args.port, runtime, admin, public)
    return 0


if __name__ == "__main__":
    sys.exit(main())
