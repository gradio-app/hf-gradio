from __future__ import annotations

import typer
from typing import Annotated, Any
from gradio_client import Client
from gradio_client.utils import traverse
import json

app = typer.Typer()


def _resolve_refs(schema: Any, defs: dict[str, Any] | None = None) -> Any:
    """Recursively resolve $ref references and remove $defs."""
    if not isinstance(schema, dict):
        if isinstance(schema, list):
            return [_resolve_refs(item, defs) for item in schema]
        return schema

    if defs is None:
        defs = schema.get("$defs", {})

    if "$ref" in schema:
        ref_path = schema["$ref"]
        ref_name = ref_path.split("/")[-1]
        if ref_name in defs:
            return _resolve_refs(defs[ref_name], defs)
        return schema

    resolved = {}
    for key, value in schema.items():
        if key == "$defs":
            continue
        resolved[key] = _resolve_refs(value, defs)
    return resolved


def simplify_json_schema(schema: Any, is_input: bool = True):
    schema = _resolve_refs(schema)
    simplifier = _make_file_simplifier(is_input)
    return traverse(
        schema,
        simplifier,
        lambda x: (
            isinstance(x, dict)
            and "meta" in x.get("properties", {})
            and "path" in x.get("properties", {})
        ),
    )


def _make_file_simplifier(is_input: bool):
    def _simplify(schema: Any) -> Any:
        props = schema.get("properties", {})
        if "meta" in props and "path" in props:
            if is_input:
                return {
                    "type": "filepath",
                    "description": (
                        'Must include {"path": "<local path or url>", "meta": {"_type": "gradio.FileData"}}. '
                        "The meta key signals that the file will be uploaded to the remote server."
                    ),
                }
            else:
                return {
                    "type": "filepath",
                    "description": "The returned file path on disk.",
                }
        return schema

    return _simplify


def _condense_info(info: dict[str, Any]):
    condensed_info = {}
    for endpoint, data_format in info["named_endpoints"].items():
        endpoint_info = {
            "parameters": [],
            "returns": [],
            "description": data_format.get("description", ""),
        }
        for param in data_format["parameters"]:
            endpoint_info["parameters"].append(
                {
                    "name": param["parameter_name"],
                    "required": not param["parameter_has_default"],
                    "default": param["parameter_default"],
                    "type": simplify_json_schema(param["type"], is_input=True),
                }
            )
        for output in data_format["returns"]:
            endpoint_info["returns"].append(
                {
                    "name": output["label"],
                    "type": simplify_json_schema(output["type"], is_input=False),
                }
            )
        condensed_info[endpoint] = endpoint_info
    return condensed_info


@app.command()
def info(
    space_id_or_url: Annotated[
        str,
        typer.Argument(
            help="The space id, e.g. gradio/calculator or URL of the Gradio application"
        ),
    ],
    token: Annotated[
        str | None,
        typer.Option(
            help="optional Hugging Face token to use to access private Spaces. By default, the locally saved token is used if there is one.",
        ),
    ] = None,
):
    """Fetches the expected JSON payload for all of the app's endpoints."""
    client = Client(src=space_id_or_url, token=token, verbose=False)
    original_info = client.view_api(return_format="dict", print_info=False)
    condensed_info = _condense_info(original_info)
    print(json.dumps(condensed_info, indent=2))


@app.command()
def predict(
    space_id_or_url: Annotated[
        str,
        typer.Argument(
            help="The space id, e.g. gradio/calculator or URL of the Gradio application"
        ),
    ],
    endpoint: Annotated[str, typer.Argument(help="The endpoint to hit")],
    payload: Annotated[str, typer.Argument(help="The payload to send to the space")],
    token: Annotated[
        str | None,
        typer.Option(
            help="optional Hugging Face token to use to access private Spaces. By default, the locally saved token is used if there is one.",
        ),
    ] = None,
):
    """Sends a prediction request to a Gradio app endpoint."""
    client = Client(
        src=space_id_or_url, token=token, verbose=False, download_files=True
    )
    payload = json.loads(payload)
    result = client.predict(**payload, api_name=endpoint)

    original_info = client.view_api(return_format="dict", print_info=False)
    condensed_info = _condense_info(original_info)
    return_names = [r["name"] for r in condensed_info[endpoint]["returns"]]

    if not isinstance(result, tuple):
        result = (result,)
    output = dict(zip(return_names, result))
    print(json.dumps(output, indent=2))
