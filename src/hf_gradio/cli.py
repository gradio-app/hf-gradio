from __future__ import annotations

import typer
from typing import Annotated, Any
from gradio_client import Client, handle_file
from gradio_client.utils import traverse
import copy
import json

app = typer.Typer()

regex_pattern = r"(?i)\bdict\(.*?\bpath:.*?\burl:.*?\)(?=\s*\||\]|$)"

class APIInfoParseError(ValueError):
    pass


def _get_type(schema: dict):
    if "const" in schema:
        return "const"
    if "enum" in schema:
        return "enum"
    elif "type" in schema:
        return schema["type"]
    elif schema.get("$ref"):
        return "$ref"
    elif schema.get("oneOf"):
        return "oneOf"
    elif schema.get("anyOf"):
        return "anyOf"
    elif schema.get("allOf"):
        return "allOf"
    elif "type" not in schema:
        return {}
    else:
        raise APIInfoParseError(f"Cannot parse type for {schema}")


def simplify_json_schema(schema: Any):
    return traverse(schema, _simplify_json_schema, lambda x: isinstance(x, dict) and "properties" in x)


def _simplify_json_schema(schema: Any) -> Any:
    """Convert the json schema into a python type hint"""

    props = schema.get("properties", {})
    print("SCHEMA", schema, "props", props)
    if "meta" in props and "path" in props:
        new_schema = copy.deepcopy(schema)
        for prop in props:
            if prop not in ["meta", "path"]:
                del new_schema["properties"][prop]
        new_schema["properties"]["path"]["description"] = "Path to a local file or publicly available url"
        return new_schema
    else:
        return schema
    


# def _condense_info(info: dict[str, Any]):
#     condensed_info = {}
#     for endpoint, data_format in info["named_endpoints"].items():
#         endpoint_info = {"parameters": [], "returns": [], "description": data_format.get("description", "")}
#         for param in data_format["parameters"]:
#             python_type = re.sub(regex_pattern, , param["python_type"]["type"])
#             endpoint_info["parameters"].append(
#                 {
#                     "name": param["parameter_name"],
#                     "required": not param["parameter_has_default"],
#                     "default": param["parameter_default"],
#                     "type": python_type,
#                 }
#             )
#         for output in data_format["returns"]:
#             python_type = re.sub(regex_pattern, "filepath", output["python_type"]["type"])
#             endpoint_info["returns"].append(
#                 {"name": output["label"], "type": python_type}
#             )
#         condensed_info[endpoint] = endpoint_info
#     return condensed_info

def _condense_info(info: dict[str, Any]):
    condensed_info = {}
    for endpoint, data_format in info["named_endpoints"].items():
        endpoint_info = {"parameters": [], "returns": [], "description": data_format.get("description", "")}
        for param in data_format["parameters"]:
            #python_type = re.sub(regex_pattern, , param["python_type"]["type"])
            endpoint_info["parameters"].append(
                {
                    "name": param["parameter_name"],
                    "required": not param["parameter_has_default"],
                    "default": param["parameter_default"],
                    "type": simplify_json_schema(param["type"]),
                }
            )
        for output in data_format["returns"]:
            endpoint_info["returns"].append(
                {"name": output["label"], "type": simplify_json_schema(output["type"])}
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
def predict(space_id_or_url: Annotated[
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
    ] = None):
    client = Client(src=space_id_or_url, token=token, verbose=False)
    info_ = _condense_info(client.view_api(return_format="dict", print_info=False)).get(endpoint, {})
    payload = json.loads(payload)
    for param in info_['parameters']:
        if param["type"] == "filepath":
            payload[param["name"]] = handle_file(payload[param["name"]])
    result = client.predict(**payload, api_name=endpoint)
    print(result)