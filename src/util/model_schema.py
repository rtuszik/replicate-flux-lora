import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Union
from enum import Enum

import replicate
from loguru import logger

from .settings import Settings


class ParameterType(Enum):
    STRING = "string"
    NUMBER = "number"
    INTEGER = "integer"
    BOOLEAN = "boolean"
    ARRAY = "array"
    OBJECT = "object"
    FILE = "file"  # Special case for file inputs


@dataclass
class ParameterDefinition:
    name: str
    type: ParameterType
    title: str
    description: str
    required: bool = False
    default: Any = None
    minimum: Optional[float] = None
    maximum: Optional[float] = None
    enum: Optional[List[Any]] = None
    format: Optional[str] = None  # e.g., "uri", "binary"
    x_order: Optional[int] = None  # Replicate's custom ordering


@dataclass
class OutputDefinition:
    type: str
    description: Optional[str] = None
    items: Optional[Dict] = None  # For array outputs
    properties: Optional[Dict] = None  # For object outputs


@dataclass
class ModelSchema:
    model_string: str
    input_parameters: List[ParameterDefinition]
    output_definition: OutputDefinition
    model_info: Dict[str, Any]


class ModelSchemaService:
    def __init__(self):
        self.client = None
        self._schema_cache: Dict[str, ModelSchema] = {}
        self._setup_client()

    def _setup_client(self):
        """Initialize Replicate client with API key"""
        api_key = Settings.get_api_key()
        if api_key:
            self.client = replicate.Client(api_token=api_key)
            logger.info("ModelSchemaService initialized with API key")
        else:
            logger.warning("No API key found for ModelSchemaService")

    def set_api_key(self, api_key: str):
        """Update API key and reinitialize client"""
        self.client = replicate.Client(api_token=api_key)
        logger.info("ModelSchemaService API key updated")

    def get_model_schema(self, model_string: str) -> Optional[ModelSchema]:
        """
        Fetch model schema from Replicate API.
        Returns cached schema if available.
        """
        if model_string in self._schema_cache:
            logger.debug(f"Using cached schema for {model_string}")
            return self._schema_cache[model_string]

        if not self.client:
            logger.error("No Replicate client available")
            return None

        try:
            logger.info(f"Fetching schema for model: {model_string}")
            
            # Parse model string to get owner/name (handle version hashes)
            if "/" not in model_string:
                logger.error(f"Invalid model string format: {model_string}")
                return None
            
            # Handle versioned models like owner/model:version_hash
            if ":" in model_string:
                model_part, version_hash = model_string.split(":", 1)
                owner, name = model_part.split("/", 1)
                logger.debug(f"Parsing versioned model: {owner}/{name} with version {version_hash}")
            else:
                owner, name = model_string.split("/", 1)
            
            # Get model info - use the original model_string for versioned models
            try:
                model = self.client.models.get(f"{owner}/{name}")
            except Exception as e:
                logger.error(f"Failed to get model {owner}/{name}: {str(e)}")
                # For private models, the error might be more specific
                if "not found" in str(e).lower():
                    logger.error(f"Model not found. This might be a private model that requires authentication.")
                elif "permission" in str(e).lower() or "access" in str(e).lower():
                    logger.error(f"Access denied. Check if your API key has permission to access this private model.")
                raise
            
            # Get the appropriate version
            if ":" in model_string:
                # For versioned models, try to get the specific version
                _, version_hash = model_string.split(":", 1)
                try:
                    version = self.client.models.versions.get(f"{owner}/{name}", version_hash)
                    logger.debug(f"Got specific version {version_hash} for model {owner}/{name}")
                except Exception as e:
                    logger.warning(f"Could not get specific version {version_hash}, falling back to latest: {str(e)}")
                    version = model.latest_version
            else:
                version = model.latest_version
            
            if not version:
                logger.error(f"No version found for model: {model_string}")
                return None
                
            # Get the OpenAPI schema from the version
            openapi_schema = version.openapi_schema
            
            if not openapi_schema:
                logger.error(f"No OpenAPI schema found for model: {model_string}")
                return None

            # Parse the schema
            schema = self._parse_openapi_schema(model_string, openapi_schema, model, version)
            
            # Cache the schema
            self._schema_cache[model_string] = schema
            logger.success(f"Successfully fetched and cached schema for {model_string}")
            
            return schema
            
        except Exception as e:
            logger.error(f"Error fetching schema for {model_string}: {str(e)}")
            return None

    def _parse_openapi_schema(self, model_string: str, openapi_schema: Dict, model_info: Any, version_info: Any = None) -> ModelSchema:
        """Parse OpenAPI schema into our internal format"""
        
        # Extract input schema
        input_schema = openapi_schema.get("components", {}).get("schemas", {}).get("Input", {})
        input_parameters = self._parse_input_parameters(input_schema)
        
        # Extract output schema
        output_schema = openapi_schema.get("components", {}).get("schemas", {}).get("Output", {})
        output_definition = self._parse_output_definition(output_schema)
        
        # Create model info dict
        # Use version_info if provided, otherwise use model_info.latest_version
        current_version = version_info if version_info else model_info.latest_version
        
        model_info_dict = {
            "name": model_info.name,
            "owner": model_info.owner,
            "description": model_info.description,
            "url": model_info.url,
            "run_count": model_info.run_count,
            "cover_image_url": model_info.cover_image_url,
            "latest_version_id": model_info.latest_version.id if model_info.latest_version else None,
            "current_version_id": current_version.id if current_version else None,
        }
        
        return ModelSchema(
            model_string=model_string,
            input_parameters=input_parameters,
            output_definition=output_definition,
            model_info=model_info_dict
        )

    def _parse_input_parameters(self, input_schema: Dict) -> List[ParameterDefinition]:
        """Parse input parameters from OpenAPI schema"""
        parameters = []
        
        properties = input_schema.get("properties", {})
        required_fields = input_schema.get("required", [])
        
        for param_name, param_def in properties.items():
            param_type = self._get_parameter_type(param_def)
            
            parameters.append(ParameterDefinition(
                name=param_name,
                type=param_type,
                title=param_def.get("title", param_name),
                description=param_def.get("description", ""),
                required=param_name in required_fields,
                default=param_def.get("default"),
                minimum=param_def.get("minimum"),
                maximum=param_def.get("maximum"),
                enum=param_def.get("enum"),
                format=param_def.get("format"),
                x_order=param_def.get("x-order", 999)  # Default high order for unspecified
            ))
        
        # Sort by x-order
        parameters.sort(key=lambda p: p.x_order or 999)
        
        return parameters

    def _get_parameter_type(self, param_def: Dict) -> ParameterType:
        """Determine parameter type from OpenAPI definition"""
        param_type = param_def.get("type", "string")
        param_format = param_def.get("format")
        
        # Handle file inputs (usually format: "uri" or "binary")
        if param_format in ["uri", "binary"] or "file" in param_def.get("description", "").lower():
            return ParameterType.FILE
        
        # Map OpenAPI types to our enum
        type_mapping = {
            "string": ParameterType.STRING,
            "number": ParameterType.NUMBER,
            "integer": ParameterType.INTEGER,
            "boolean": ParameterType.BOOLEAN,
            "array": ParameterType.ARRAY,
            "object": ParameterType.OBJECT,
        }
        
        return type_mapping.get(param_type, ParameterType.STRING)

    def _parse_output_definition(self, output_schema: Dict) -> OutputDefinition:
        """Parse output definition from OpenAPI schema"""
        return OutputDefinition(
            type=output_schema.get("type", "unknown"),
            description=output_schema.get("description"),
            items=output_schema.get("items"),
            properties=output_schema.get("properties")
        )

    def validate_input_parameters(self, model_string: str, input_params: Dict[str, Any]) -> tuple[bool, List[str]]:
        """
        Validate input parameters against model schema.
        Returns (is_valid, list_of_errors)
        """
        schema = self.get_model_schema(model_string)
        if not schema:
            return False, ["Could not fetch model schema"]
        
        errors = []
        
        # Check for unknown parameters
        valid_param_names = {p.name for p in schema.input_parameters}
        for param_name in input_params:
            if param_name not in valid_param_names:
                errors.append(f"Unknown parameter '{param_name}'")
        
        # Check required parameters
        required_params = [p.name for p in schema.input_parameters if p.required]
        for required_param in required_params:
            if required_param not in input_params:
                errors.append(f"Required parameter '{required_param}' is missing")
        
        # Check parameter types and constraints
        for param in schema.input_parameters:
            if param.name not in input_params:
                continue
                
            value = input_params[param.name]
            
            # Type validation
            if param.type == ParameterType.INTEGER and not isinstance(value, int):
                errors.append(f"Parameter '{param.name}' must be an integer")
            elif param.type == ParameterType.NUMBER and not isinstance(value, (int, float)):
                errors.append(f"Parameter '{param.name}' must be a number")
            elif param.type == ParameterType.BOOLEAN and not isinstance(value, bool):
                errors.append(f"Parameter '{param.name}' must be a boolean")
            
            # Range validation
            if param.type in [ParameterType.INTEGER, ParameterType.NUMBER]:
                if param.minimum is not None and value < param.minimum:
                    errors.append(f"Parameter '{param.name}' must be >= {param.minimum}")
                if param.maximum is not None and value > param.maximum:
                    errors.append(f"Parameter '{param.name}' must be <= {param.maximum}")
            
            # Enum validation
            if param.enum and value not in param.enum:
                errors.append(f"Parameter '{param.name}' must be one of: {param.enum}")
        
        return len(errors) == 0, errors

    def categorize_model(self, model_string: str) -> str:
        """
        Categorize model based on its schema and metadata.
        Returns category like 'image-generation', 'text-generation', etc.
        """
        schema = self.get_model_schema(model_string)
        if not schema:
            return "unknown"
        
        # Check output type first
        output_type = schema.output_definition.type
        
        # Look for common patterns in input parameters
        param_names = [p.name.lower() for p in schema.input_parameters]
        
        if output_type == "array":
            # Check if array items are likely images
            items = schema.output_definition.items or {}
            if items.get("format") == "uri" or "image" in str(items):
                return "image-generation"
        
        # Check for common parameter patterns
        if "prompt" in param_names:
            if any(p in param_names for p in ["image", "width", "height", "aspect_ratio"]):
                return "image-generation"
            elif any(p in param_names for p in ["video", "fps", "duration"]):
                return "video-generation"
            elif any(p in param_names for p in ["audio", "duration", "sample_rate"]):
                return "audio-generation"
            else:
                return "text-generation"
        
        if "image" in param_names:
            return "image-processing"
        
        if "video" in param_names:
            return "video-processing"
        
        if "audio" in param_names:
            return "audio-processing"
        
        # Check model name/description for hints
        model_name = schema.model_info.get("name", "").lower()
        model_desc = schema.model_info.get("description", "").lower()
        
        if any(word in model_name + " " + model_desc for word in ["image", "picture", "photo", "visual"]):
            return "image-processing"
        elif any(word in model_name + " " + model_desc for word in ["video", "movie", "film"]):
            return "video-processing"
        elif any(word in model_name + " " + model_desc for word in ["audio", "sound", "music", "voice"]):
            return "audio-processing"
        elif any(word in model_name + " " + model_desc for word in ["text", "language", "chat", "instruct"]):
            return "text-generation"
        
        return "unknown"

    def clear_cache(self):
        """Clear the schema cache"""
        self._schema_cache.clear()
        logger.info("Schema cache cleared")

    def get_cached_models(self) -> List[str]:
        """Get list of models with cached schemas"""
        return list(self._schema_cache.keys())