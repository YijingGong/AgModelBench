"""
A2A server implementation for AgentBeats + your Green/White benchmark context.

Key requirements:
- Listen on $HOST and $AGENT_PORT when launched under the AgentBeats controller.  citeturn1view1
- Serve an Agent Card at /.well-known/agent-card.json (AgentBeats controller checks this). citeturn1view1
- Also serve /.well-known/agent.json (commonly used in A2A discovery). citeturn1view2
- Accept JSON-RPC requests (A2A commonly uses JSON-RPC). citeturn1view0

Notes:
- The exact A2A JSON-RPC method names can vary by client/framework. This server is tolerant:
  it accepts any method and tries to extract input text/chunk from common param shapes.
- The WHITE agent must return JSON in your user-defined schema. See schema.py.
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple
from fastapi import FastAPI, Request
from pydantic import ValidationError

from schema import ExtractionOutput, Paper, Equation, ExtractionMetadata


def _first_nonempty(*vals: Optional[str]) -> Optional[str]:
    for v in vals:
        if v is not None and str(v).strip() != "":
            return str(v)
    return None


def build_agent_card(
    *,
    name: str,
    description: str,
    base_url: str,
    version: str = "1.0.0",
    protocol_version: str = "0.2.6",
    streaming: bool = False,
) -> Dict[str, Any]:
    """
    Agent Card fields are modeled after common A2A examples. citeturn1view2
    AgentBeats specifically tests fetching /.well-known/agent-card.json. citeturn1view1
    """
    return {
        "name": name,
        "description": description,
        "url": base_url,
        "version": version,
        "protocolVersion": protocol_version,
        "capabilities": {"streaming": streaming},
        "defaultInputModes": ["text", "text/plain", "application/json"],
        "defaultOutputModes": ["application/json"],
        "skills": [
            {
                "id": "extract_dairy_math_models",
                "name": "Dairy math model extraction",
                "description": "Extract equations/models from dairy science paper text into structured JSON.",
                "examples": ["Extract the regression equations and reported metrics from this Methods section."],
                "tags": ["dairy", "equations", "latex", "benchmark"],
            }
        ],
        # Convenience pointers for clients (not always in every spec, but useful)
        "endpoints": {
            "jsonrpc": f"{base_url}/",
            "card": f"{base_url}/.well-known/agent-card.json",
            "agent": f"{base_url}/.well-known/agent.json",
            "health": f"{base_url}/health",
        },
    }


def _extract_input_from_jsonrpc(params: Any) -> Tuple[Optional[str], Dict[str, Any]]:
    """
    Try to find the paper chunk text and useful metadata from common param shapes.
    Returns (text, meta).
    """
    meta: Dict[str, Any] = {}

    if isinstance(params, dict):
        # Common shapes: {"input": {...}}, {"input_text": "..."} etc.
        if "task_id" in params:
            meta["task_id"] = params.get("task_id")
        if "schema" in params and isinstance(params["schema"], dict):
            meta["schema_name"] = params["schema"].get("name")
            meta["schema_version"] = params["schema"].get("version")

        # Paper info (optional but useful for provenance)
        paper = params.get("paper")
        if isinstance(paper, dict):
            meta["input_doi"] = paper.get("doi") or meta.get("input_doi")

        inp = params.get("input") if isinstance(params.get("input"), dict) else None
        if inp:
            meta["chunk_id"] = inp.get("chunk_id")
            meta["content_type"] = inp.get("content_type")
            text = inp.get("text")
            if isinstance(text, str) and text.strip():
                return text, meta

        # Fall back to common direct fields
        for k in ["input_text", "text", "chunk_text", "content"]:
            if isinstance(params.get(k), str) and params[k].strip():
                return params[k], meta

    # Unknown / unsupported shape
    return None, meta


def _jsonrpc_success(rpc_id: Any, result: Any) -> Dict[str, Any]:
    return {"jsonrpc": "2.0", "id": rpc_id, "result": result}


def _jsonrpc_error(rpc_id: Any, code: int, message: str, data: Any = None) -> Dict[str, Any]:
    err: Dict[str, Any] = {"code": code, "message": message}
    if data is not None:
        err["data"] = data
    return {"jsonrpc": "2.0", "id": rpc_id, "error": err}


def create_app(
    *,
    base_url: str,
    agent_name: str = "DairyMathExtractor",
    agent_description: str = "Extracts mathematical models from dairy science papers into structured JSON.",
    run_agent_fn=None,
) -> FastAPI:
    """
    run_agent_fn: callable(text: str, meta: dict) -> dict (must match ExtractionOutput shape)
                 If None, a stub is used.
    """
    app = FastAPI()
    agent_card = build_agent_card(
        name=agent_name,
        description=agent_description,
        base_url=base_url,
        streaming=False,
    )

    @app.get("/.well-known/agent-card.json")
    def agent_card_json():
        return agent_card

    @app.get("/.well-known/agent.json")
    def agent_json():
        # Many clients use this well-known path. citeturn1view2
        return agent_card

    @app.get("/health")
    def health():
        return {"ok": True}

    @app.post("/")
    async def jsonrpc_root(req: Request):
        payload = await req.json()

        # JSON-RPC batch support (optional)
        if isinstance(payload, list):
            responses = []
            for item in payload:
                resp = await _handle_single_jsonrpc(item, run_agent_fn)
                if resp is not None:
                    responses.append(resp)
            return responses

        resp = await _handle_single_jsonrpc(payload, run_agent_fn)
        return resp

    async def _handle_single_jsonrpc(body: Dict[str, Any], run_agent_fn_local):
        rpc_id = body.get("id", None)
        method = body.get("method", "")
        params = body.get("params", {})

        # Notifications (no id) can be ignored by spec; we still return nothing.
        if rpc_id is None and isinstance(body.get("id", None), type(None)):
            # Return None to indicate no response for JSON-RPC notifications.
            return None

        text, meta = _extract_input_from_jsonrpc(params)
        if not text:
            return _jsonrpc_error(rpc_id, -32602, "Missing input text in params (expected input.text or input_text).", {"method": method})

        # Call user agent
        if run_agent_fn_local is None:
            output_dict = _run_agent_stub(text, meta)
        else:
            output_dict = run_agent_fn_local(text, meta)

        # Validate output has required top-level structure and required equation fields.
        try:
            validated = ExtractionOutput.model_validate(output_dict)
        except ValidationError as e:
            return _jsonrpc_error(
                rpc_id,
                -32000,
                "White agent returned JSON that does not match required schema (paper/equations/extraction_metadata).",
                {"validation_errors": e.errors()},
            )

        # Return exactly the user-defined output JSON (not stringified)
        return _jsonrpc_success(rpc_id, validated.model_dump())

    return app


def _run_agent_stub(text: str, meta: Dict[str, Any]) -> Dict[str, Any]:
    """
    Safe stub: returns a valid structure with required fields.
    Replace by passing run_agent_fn to create_app().
    """
    return {
        "paper": {"doi": meta.get("input_doi"), "title": None, "year": None},
        "equations": [
            {
                "latex": None,
                "model_performance": None,
                "notes": "STUB: replace run_agent_fn with your extractor; latex/performance are required fields.",
            }
        ],
        "extraction_metadata": {
            "task_id": meta.get("task_id"),
            "input_doi": meta.get("input_doi"),
            "schema_name": meta.get("schema_name"),
            "schema_version": meta.get("schema_version"),
        },
    }
