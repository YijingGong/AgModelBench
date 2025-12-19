"""
Entry point for running the WHITE A2A server under AgentBeats or standalone.

AgentBeats controller expectations:
- Provide a run.sh that starts your agent.
- Agent listens on $HOST and $AGENT_PORT; controller sets these env vars. citeturn1view1
- Controller (or testers) should be able to fetch /.well-known/agent-card.json. citeturn1view1

This entrypoint also supports:
- --host, --port, --card-url (public base URL override for Agent Card.url)
"""
from __future__ import annotations

import argparse
import os

import uvicorn
from a2a_server import create_app

# ---- TODO: plug in your real agent function here ----
def run_agent_placeholder(text: str, meta: dict):
    """
    Replace this with your real extractor, e.g.:
        from my_extractor import run_agent
        return run_agent(text, meta)
    Must return a dict with top-level keys:
      - paper
      - equations (each equation must include 'latex' and 'model_performance')
      - extraction_metadata
    """
    # Returning None here would fail schema validation; keep placeholder valid.
    return None  # <-- replace


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default=os.environ.get("HOST", "0.0.0.0"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("AGENT_PORT", "8000")))
    parser.add_argument("--card-url", default=os.environ.get("CARD_URL", None),
                        help="Public base URL for the agent (e.g., https://<proxy>/agent).")
    parser.add_argument("--use-placeholder-agent", action="store_true",
                        help="Use the built-in stub agent (always returns valid schema).")
    args = parser.parse_args()

    base_url = args.card_url or f"http://{args.host}:{args.port}"

    if args.use_placeholder_agent:
        app = create_app(base_url=base_url, run_agent_fn=None)
    else:
        # If you keep run_agent_placeholder returning None, server will return schema error.
        # Replace with your real agent function.
        app = create_app(base_url=base_url, run_agent_fn=run_agent_placeholder)

    uvicorn.run(app, host=args.host, port=args.port)

if __name__ == "__main__":
    main()
