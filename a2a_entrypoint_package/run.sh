#!/usr/bin/env bash
# AgentBeats controller will set $HOST and $AGENT_PORT. citeturn1view1
# Use --card-url if you're behind a proxy and want the Agent Card "url" to be public.

python run_a2a.py --host "${HOST:-0.0.0.0}" --port "${AGENT_PORT:-8000}" --use-placeholder-agent
