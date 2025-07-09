from typing import Dict, List, Any, Optional
from nicegui import ui
from loguru import logger

from util.model_schema import ModelSchema, ParameterDefinition, ParameterType
from util.settings import Settings


class DynamicParameterPanel:
    def __init__(self, on_parameter_change=None):
        self.schema: Optional[ModelSchema] = None
        self.parameter_values: Dict[str, Any] = {}
        self.ui_elements: Dict[str, ui.element] = {}
        self.on_parameter_change = on_parameter_change
        self.container = None

    def set_schema(self, schema: ModelSchema):
        """Set the model schema and regenerate UI"""
        self.schema = schema
        self.parameter_values = {}
        self.ui_elements = {}
        # Clear existing container
        if self.container:
            self.container.clear()
        self._generate_ui()

    def _generate_ui(self):
        """Generate UI controls based on current schema"""
        if not self.schema:
            return

        # Don't create a new container here - it should be created in the parent context
        # Just generate the UI content
        
        # Group parameters by type for better organization
        required_params = [p for p in self.schema.input_parameters if p.required]
        optional_params = [p for p in self.schema.input_parameters if not p.required]
        
        if required_params:
            ui.label("Required Parameters").classes("text-md font-semibold text-red-600 mb-2")
            for param in required_params:
                self._create_parameter_control(param)
        
        if optional_params:
            ui.separator().classes("my-2")
            ui.label("Optional Parameters").classes("text-md font-semibold dark:text-[#a6adc8] text-gray-600 mb-2")
            for param in optional_params:
                self._create_parameter_control(param)

    def _create_parameter_control(self, param: ParameterDefinition):
        """Create appropriate UI control for a parameter"""
        
        with ui.column().classes("w-full gap-1 mb-2"):
            # Parameter label with description
            label_text = param.title or param.name
            if param.required:
                label_text += " *"
            
            ui.label(label_text).classes("font-medium text-sm dark:text-[#cdd6f4] text-[#4c4f69]")
            
            if param.description:
                ui.label(param.description).classes("text-xs dark:text-[#a6adc8] text-gray-600")
            
            # Create control based on parameter type
            if param.type == ParameterType.BOOLEAN:
                control = self._create_boolean_control(param)
            elif param.type == ParameterType.INTEGER:
                control = self._create_integer_control(param)
            elif param.type == ParameterType.NUMBER:
                control = self._create_number_control(param)
            elif param.type == ParameterType.STRING and param.enum:
                control = self._create_enum_control(param)
            elif param.type == ParameterType.STRING:
                control = self._create_string_control(param)
            elif param.type == ParameterType.FILE:
                control = self._create_file_control(param)
            elif param.type == ParameterType.ARRAY:
                control = self._create_array_control(param)
            else:
                control = self._create_string_control(param)  # Fallback
            
            self.ui_elements[param.name] = control
            
            # Set default value
            if param.default is not None:
                self.parameter_values[param.name] = param.default
                if hasattr(control, 'set_value'):
                    control.set_value(param.default)
                elif hasattr(control, 'value'):
                    control.value = param.default

    def _create_boolean_control(self, param: ParameterDefinition) -> ui.element:
        """Create a switch for boolean parameters"""
        def on_change(e):
            value = e.value if hasattr(e, 'value') else e
            self.parameter_values[param.name] = value
            if self.on_parameter_change:
                self.on_parameter_change(param.name, value)
        
        return ui.switch(
            value=param.default or False,
            on_change=on_change
        ).classes("w-full")

    def _create_integer_control(self, param: ParameterDefinition) -> ui.element:
        """Create a number input for integer parameters"""
        def on_change(e):
            value = e.value if hasattr(e, 'value') else e
            try:
                int_value = int(value) if value is not None else None
                self.parameter_values[param.name] = int_value
                if self.on_parameter_change:
                    self.on_parameter_change(param.name, int_value)
            except (ValueError, TypeError):
                pass
        
        return ui.number(
            value=param.default,
            min=param.minimum,
            max=param.maximum,
            step=1,
            on_change=on_change
        ).classes("w-full").props("filled bg-color=dark")

    def _create_number_control(self, param: ParameterDefinition) -> ui.element:
        """Create a number input for float parameters"""
        def on_change(e):
            value = e.value if hasattr(e, 'value') else e
            try:
                float_value = float(value) if value is not None else None
                self.parameter_values[param.name] = float_value
                if self.on_parameter_change:
                    self.on_parameter_change(param.name, float_value)
            except (ValueError, TypeError):
                pass
        
        return ui.number(
            value=param.default,
            min=param.minimum,
            max=param.maximum,
            step=0.1,
            on_change=on_change
        ).classes("w-full").props("filled bg-color=dark")

    def _create_string_control(self, param: ParameterDefinition) -> ui.element:
        """Create a text input for string parameters"""
        def on_change(e):
            value = e.value if hasattr(e, 'value') else e
            self.parameter_values[param.name] = value
            if self.on_parameter_change:
                self.on_parameter_change(param.name, value)
        
        # Use textarea for longer descriptions or if 'prompt' is in the name
        if len(param.description or "") > 100 or 'prompt' in param.name.lower():
            return ui.textarea(
                value=param.default or "",
                placeholder=param.description[:50] + "..." if param.description and len(param.description) > 50 else param.description,
                on_change=on_change
            ).classes("w-full").props("clearable filled bg-color=dark autofocus color=blue-4")
        else:
            return ui.input(
                value=param.default or "",
                placeholder=param.description[:50] + "..." if param.description and len(param.description) > 50 else param.description,
                on_change=on_change
            ).classes("w-full").props("clearable filled bg-color=dark")

    def _create_enum_control(self, param: ParameterDefinition) -> ui.element:
        """Create a select dropdown for enum parameters"""
        def on_change(e):
            value = e.value if hasattr(e, 'value') else e
            self.parameter_values[param.name] = value
            if self.on_parameter_change:
                self.on_parameter_change(param.name, value)
        
        options = param.enum or []
        return ui.select(
            options=options,
            value=param.default,
            on_change=on_change
        ).classes("w-full").props("filled bg-color=dark")

    def _create_file_control(self, param: ParameterDefinition) -> ui.element:
        """Create a file upload control for file parameters"""
        def on_upload(e):
            if e.content:
                # For now, we'll store the file content as a data URL
                # In a full implementation, you'd save to disk and use file path
                import base64
                data_url = f"data:{e.type};base64,{base64.b64encode(e.content).decode()}"
                self.parameter_values[param.name] = data_url
                if self.on_parameter_change:
                    self.on_parameter_change(param.name, data_url)
        
        with ui.column().classes("w-full gap-1"):
            # File upload
            upload = ui.upload(
                on_upload=on_upload,
                max_file_size=100 * 1024 * 1024,  # 100MB limit
                auto_upload=True
            ).classes("w-full")
            
            # URL input as alternative
            ui.label("Or paste a URL:").classes("text-xs text-gray-600 mt-2")
            
            def on_url_change(e):
                value = e.value if hasattr(e, 'value') else e
                if value and value.strip():
                    self.parameter_values[param.name] = value.strip()
                    if self.on_parameter_change:
                        self.on_parameter_change(param.name, value.strip())
            
            url_input = ui.input(
                placeholder="https://example.com/image.jpg",
                on_change=on_url_change
            ).classes("w-full")
            
            return upload  # Return the upload component as primary

    def _create_array_control(self, param: ParameterDefinition) -> ui.element:
        """Create a multi-value input for array parameters"""
        def on_change(e):
            value = e.value if hasattr(e, 'value') else e
            # Simple comma-separated values for now
            if value:
                array_value = [item.strip() for item in value.split(',') if item.strip()]
                self.parameter_values[param.name] = array_value
                if self.on_parameter_change:
                    self.on_parameter_change(param.name, array_value)
            else:
                self.parameter_values[param.name] = []
                if self.on_parameter_change:
                    self.on_parameter_change(param.name, [])
        
        return ui.input(
            placeholder="Enter values separated by commas",
            on_change=on_change
        ).classes("w-full")

    def get_parameter_values(self) -> Dict[str, Any]:
        """Get current parameter values"""
        return self.parameter_values.copy()

    def set_parameter_value(self, name: str, value: Any):
        """Set a parameter value programmatically"""
        if name in self.ui_elements:
            self.parameter_values[name] = value
            control = self.ui_elements[name]
            
            if hasattr(control, 'set_value'):
                control.set_value(value)
            elif hasattr(control, 'value'):
                control.value = value

    def clear_parameters(self):
        """Clear all parameter values"""
        self.parameter_values.clear()
        for control in self.ui_elements.values():
            if hasattr(control, 'set_value'):
                control.set_value(None)
            elif hasattr(control, 'value'):
                control.value = None

    def validate_parameters(self) -> tuple[bool, List[str]]:
        """Validate current parameter values against schema"""
        if not self.schema:
            return True, []
        
        from util.model_schema import ModelSchemaService
        schema_service = ModelSchemaService()
        return schema_service.validate_input_parameters(
            self.schema.model_string, 
            self.parameter_values
        )

    def get_container(self) -> ui.element:
        """Get the container element for this panel"""
        return self.container


class LegacyParametersBridge:
    """
    Bridge class to maintain compatibility with existing Flux LoRA parameters
    while supporting the new dynamic system.
    """
    
    # Legacy parameter mapping for existing Flux LoRA functionality
    LEGACY_FLUX_PARAMS = {
        "flux_model": "model",
        "aspect_ratio": "aspect_ratio", 
        "num_outputs": "num_outputs",
        "lora_scale": "lora_scale",
        "num_inference_steps": "num_inference_steps",
        "guidance_scale": "guidance_scale",
        "output_format": "output_format",
        "output_quality": "output_quality",
        "disable_safety_checker": "disable_safety_checker",
        "width": "width",
        "height": "height",
        "seed": "seed",
        "prompt": "prompt"
    }
    
    def __init__(self):
        pass
    
    def is_flux_model(self, model_string: str) -> bool:
        """Check if model is a Flux LoRA model"""
        return "flux" in model_string.lower() or "lora" in model_string.lower()
    
    def convert_legacy_params(self, legacy_params: Dict[str, Any]) -> Dict[str, Any]:
        """Convert legacy parameter names to dynamic parameter names"""
        converted = {}
        for legacy_name, value in legacy_params.items():
            if legacy_name in self.LEGACY_FLUX_PARAMS:
                converted[self.LEGACY_FLUX_PARAMS[legacy_name]] = value
            else:
                converted[legacy_name] = value
        return converted
    
    def convert_to_legacy_params(self, dynamic_params: Dict[str, Any]) -> Dict[str, Any]:
        """Convert dynamic parameter names back to legacy names"""
        legacy = {}
        reverse_mapping = {v: k for k, v in self.LEGACY_FLUX_PARAMS.items()}
        
        for param_name, value in dynamic_params.items():
            if param_name in reverse_mapping:
                legacy[reverse_mapping[param_name]] = value
            else:
                legacy[param_name] = value
        return legacy