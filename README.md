# hf-gradio

A CLI for sending predictions to Gradio apps hosted on Hugging Face Spaces (and beyond). Works standalone as `hf-gradio` and is also available as `gradio info` / `gradio predict` when Gradio is installed.

## Installation

```bash
pip install hf-gradio
```

## Commands

### `info` — Discover endpoints and parameters

```bash
hf-gradio info <space_id_or_url>
```

Returns a JSON description of all endpoints, their parameters (with types, defaults, and whether they're required), and return values.

```bash
hf-gradio info gradio/calculator
```

```json
{
  "/predict": {
    "parameters": [
      {"name": "num1", "required": true, "default": null, "type": {"type": "number"}},
      {"name": "operation", "required": true, "default": null, "type": {"enum": ["add", "subtract", "multiply", "divide"], "type": "string"}},
      {"name": "num2", "required": true, "default": null, "type": {"type": "number"}}
    ],
    "returns": [{"name": "output", "type": {"type": "number"}}],
    "description": ""
  }
}
```

File-type parameters are simplified to `"type": "filepath"` with clear instructions on how to format the payload:

```json
{
  "type": "filepath",
  "description": "Must include {\"path\": \"<local path or url>\", \"meta\": {\"_type\": \"gradio.FileData\"}}. The meta key signals that the file will be uploaded to the remote server."
}
```

### `predict` — Send predictions

```bash
hf-gradio predict <space_id_or_url> <endpoint> <json_payload>
```

Returns a JSON object with named output keys.

```bash
# Simple numeric prediction
hf-gradio predict gradio/calculator /predict '{"num1": 5, "operation": "multiply", "num2": 3}'
# {"output": 15}

# Image generation
hf-gradio predict black-forest-labs/FLUX.2-dev /infer '{"prompt": "A majestic dragon"}'
# {"Result": "/tmp/gradio/.../image.webp", "Seed": 1117868604}

# File upload (must include the meta key)
hf-gradio predict gradio/image_mod /predict '{"image": {"path": "/path/to/image.png", "meta": {"_type": "gradio.FileData"}}}'
# {"output": "/tmp/gradio/.../output.png"}
```

### Private Spaces

Both commands accept `--token` for accessing private Spaces:

```bash
hf-gradio info my-org/private-space --token hf_xxxxx
```

By default, the locally saved HF token is used if one exists.

## Designed for AI coding agents

The `info` command returns agent-friendly JSON schemas. The `meta` key requirement for file uploads is clearly documented in the schema itself. This makes it straightforward for agents to discover an API and construct valid payloads.

```bash
# Step 1: Discover the API
hf-gradio info mrfakename/Z-Image-Turbo

# Step 2: Send a prediction
hf-gradio predict mrfakename/Z-Image-Turbo /generate_image '{"prompt": "A cute cat sitting on a windowsill"}'
```
