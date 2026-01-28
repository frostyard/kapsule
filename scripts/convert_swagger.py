#!/usr/bin/env python3
"""Convert Swagger 2.0 (OpenAPI 2.0) to OpenAPI 3.0 format."""

import yaml
import json
import sys
from pathlib import Path


def convert_swagger2_to_openapi3(swagger: dict) -> dict:
    """Convert a Swagger 2.0 spec to OpenAPI 3.0 format."""
    
    openapi3 = {
        "openapi": "3.0.3",
        "info": swagger.get("info", {"title": "API", "version": "1.0.0"}),
    }
    
    # Convert host/basePath/schemes to servers
    host = swagger.get("host", "localhost")
    base_path = swagger.get("basePath", "/")
    schemes = swagger.get("schemes", ["https"])
    
    openapi3["servers"] = [
        {"url": f"{scheme}://{host}{base_path}"} 
        for scheme in schemes
    ]
    
    # Convert definitions to components/schemas
    if "definitions" in swagger:
        openapi3["components"] = {
            "schemas": convert_definitions(swagger["definitions"])
        }
    
    # Convert securityDefinitions to components/securitySchemes
    if "securityDefinitions" in swagger:
        if "components" not in openapi3:
            openapi3["components"] = {}
        openapi3["components"]["securitySchemes"] = convert_security_definitions(
            swagger["securityDefinitions"]
        )
    
    # Convert paths
    if "paths" in swagger:
        openapi3["paths"] = convert_paths(swagger["paths"])
    
    # Copy over security, tags, externalDocs
    for key in ["security", "tags", "externalDocs"]:
        if key in swagger:
            openapi3[key] = swagger[key]
    
    return openapi3


def convert_definitions(definitions: dict) -> dict:
    """Convert Swagger 2.0 definitions to OpenAPI 3.0 schemas."""
    schemas = {}
    for name, schema in definitions.items():
        schemas[name] = convert_schema(schema)
    return schemas


def convert_schema(schema: dict) -> dict:
    """Convert a Swagger 2.0 schema to OpenAPI 3.0 format."""
    if not isinstance(schema, dict):
        return schema
    
    result = {}
    
    for key, value in schema.items():
        # Skip vendor extensions we don't need
        if key.startswith("x-go-"):
            continue
            
        if key == "$ref":
            # Update $ref paths from #/definitions/ to #/components/schemas/
            if value.startswith("#/definitions/"):
                result["$ref"] = value.replace("#/definitions/", "#/components/schemas/")
            else:
                result["$ref"] = value
        elif key == "items":
            result["items"] = convert_schema(value)
        elif key == "properties":
            result["properties"] = {
                k: convert_schema(v) for k, v in value.items()
            }
        elif key == "additionalProperties":
            if isinstance(value, dict):
                result["additionalProperties"] = convert_schema(value)
            else:
                result["additionalProperties"] = value
        elif key == "allOf":
            result["allOf"] = [convert_schema(s) for s in value]
        elif key == "anyOf":
            result["anyOf"] = [convert_schema(s) for s in value]
        elif key == "oneOf":
            result["oneOf"] = [convert_schema(s) for s in value]
        else:
            result[key] = value
    
    return result


def convert_security_definitions(sec_defs: dict) -> dict:
    """Convert Swagger 2.0 securityDefinitions to OpenAPI 3.0 securitySchemes."""
    schemes = {}
    for name, definition in sec_defs.items():
        scheme = dict(definition)
        # Convert type names if needed
        if scheme.get("type") == "basic":
            scheme["type"] = "http"
            scheme["scheme"] = "basic"
        schemes[name] = scheme
    return schemes


def convert_paths(paths: dict) -> dict:
    """Convert Swagger 2.0 paths to OpenAPI 3.0 format."""
    result = {}
    
    for path, path_item in paths.items():
        result[path] = convert_path_item(path_item)
    
    return result


def convert_path_item(path_item: dict) -> dict:
    """Convert a Swagger 2.0 path item to OpenAPI 3.0 format."""
    result = {}
    
    for key, value in path_item.items():
        if key in ["get", "put", "post", "delete", "options", "head", "patch"]:
            result[key] = convert_operation(value)
        elif key == "parameters":
            result["parameters"] = [convert_parameter(p) for p in value]
        else:
            result[key] = value
    
    return result


def convert_operation(operation: dict) -> dict:
    """Convert a Swagger 2.0 operation to OpenAPI 3.0 format."""
    result = {}
    
    body_param = None
    form_params = []
    other_params = []
    
    for key, value in operation.items():
        if key == "parameters":
            for param in value:
                if param.get("in") == "body":
                    body_param = param
                elif param.get("in") == "formData":
                    form_params.append(param)
                else:
                    other_params.append(convert_parameter(param))
        elif key == "responses":
            result["responses"] = convert_responses(value)
        elif key == "produces":
            # Handled in responses
            pass
        elif key == "consumes":
            # Handled in requestBody
            pass
        else:
            result[key] = value
    
    if other_params:
        result["parameters"] = other_params
    
    # Convert body parameter to requestBody
    if body_param:
        consumes = operation.get("consumes", ["application/json"])
        result["requestBody"] = {
            "content": {
                content_type: {
                    "schema": convert_schema(body_param.get("schema", {}))
                }
                for content_type in consumes
            }
        }
        if body_param.get("required"):
            result["requestBody"]["required"] = True
        if body_param.get("description"):
            result["requestBody"]["description"] = body_param["description"]
    
    # Convert form parameters to requestBody
    if form_params:
        consumes = operation.get("consumes", ["application/x-www-form-urlencoded"])
        properties = {}
        required = []
        for param in form_params:
            prop = {"type": param.get("type", "string")}
            if "description" in param:
                prop["description"] = param["description"]
            if "format" in param:
                prop["format"] = param["format"]
            properties[param["name"]] = prop
            if param.get("required"):
                required.append(param["name"])
        
        schema = {"type": "object", "properties": properties}
        if required:
            schema["required"] = required
        
        result["requestBody"] = {
            "content": {
                content_type: {"schema": schema}
                for content_type in consumes
            }
        }
    
    return result


def convert_parameter(param: dict) -> dict:
    """Convert a Swagger 2.0 parameter to OpenAPI 3.0 format."""
    result = {
        "name": param["name"],
        "in": param["in"],
    }
    
    if "description" in param:
        result["description"] = param["description"]
    if "required" in param:
        result["required"] = param["required"]
    
    # In OpenAPI 3.0, schema is used instead of type/format directly
    if param["in"] != "body":
        schema = {}
        for key in ["type", "format", "items", "enum", "default", "minimum", "maximum"]:
            if key in param:
                if key == "items":
                    schema[key] = convert_schema(param[key])
                else:
                    schema[key] = param[key]
        if schema:
            result["schema"] = schema
    
    return result


def convert_responses(responses: dict) -> dict:
    """Convert Swagger 2.0 responses to OpenAPI 3.0 format."""
    result = {}
    
    for status, response in responses.items():
        converted = {}
        
        if "description" in response:
            converted["description"] = response["description"]
        else:
            converted["description"] = "Response"
        
        if "schema" in response:
            # Default to application/json for response content
            converted["content"] = {
                "application/json": {
                    "schema": convert_schema(response["schema"])
                }
            }
        
        if "headers" in response:
            converted["headers"] = response["headers"]
        
        result[str(status)] = converted
    
    return result


def main():
    if len(sys.argv) < 2:
        print("Usage: convert_swagger.py <input.yaml> [output.yaml]")
        sys.exit(1)
    
    input_path = Path(sys.argv[1])
    output_path = Path(sys.argv[2]) if len(sys.argv) > 2 else input_path.with_suffix(".v3.yaml")
    
    print(f"Reading {input_path}...")
    with open(input_path) as f:
        swagger = yaml.safe_load(f)
    
    print(f"Converting Swagger {swagger.get('swagger', '2.0')} to OpenAPI 3.0...")
    openapi3 = convert_swagger2_to_openapi3(swagger)
    
    print(f"Writing {output_path}...")
    with open(output_path, "w") as f:
        yaml.dump(openapi3, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
    
    print("Done!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
