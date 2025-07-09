import asyncio
import json
import os
import uuid
from datetime import datetime
from typing import Any, Dict

from loguru import logger
from nicegui import ui

from gui.dynamic_params import DynamicParameterPanel, LegacyParametersBridge
from gui.enhanced_lightbox import EnhancedLightbox
from gui.styles import Styles
from gui.universal_gallery import UniversalGallery
from gui.usermodels import UserModels
from util.gallery_database import GalleryDatabase
from util.model_schema import ModelSchemaService
from util.output_handler import OutputHandler
from util.replicate_api import Replicate_API
from util.settings import Settings


class UniversalReplicateGUI(UserModels):
    """
    Universal Replicate GUI that supports any model type with dynamic parameters,
    while maintaining backward compatibility with existing Flux LoRA workflows.
    """
    
    def __init__(self, replicate_api: Replicate_API):
        logger.info("Initializing UniversalReplicateGUI")
        
        # Core services
        self.replicate_api = replicate_api
        self.schema_service = ModelSchemaService()
        self.legacy_bridge = LegacyParametersBridge()
        
        # Initialize services with API key
        api_key = Settings.get_api_key()
        if api_key:
            self.schema_service.set_api_key(api_key)
        
        # File and database setup
        self.output_dir = self._get_output_dir()
        self.output_handler = OutputHandler(self.output_dir)
        self.gallery_db = GalleryDatabase(self._get_database_path())
        
        # UI Components
        self.dynamic_params = DynamicParameterPanel(on_parameter_change=self._on_parameter_change)
        self.universal_gallery = UniversalGallery(
            gallery_db=self.gallery_db,
            output_dir=self.output_dir,
            on_regenerate=self._on_regenerate,
            on_model_select=self._on_model_select
        )
        self.enhanced_lightbox = EnhancedLightbox(
            on_regenerate=self._on_regenerate,
            on_model_select=self._on_model_select,
            on_delete=self._on_delete_generation,
            on_update=self._on_update_generation
        )
        
        # UI State
        self.current_model = Settings.get_setting("default", "replicate_model", "", str)
        self.current_schema = None
        self.generation_in_progress = False
        self.last_generation_id = None
        
        # UI Elements
        self.main_container = None
        self.model_select = None
        self.generate_button = None
        self.progress_container = None
        self.gallery_container = None
        self.params_container = None
        
        # Initialize user models (from parent class)
        super().__init__()
        
        # Initialize model options from settings
        self._initialize_model_options()
        
        # Setup styles
        Styles.setup_custom_styles()
        
        logger.info("UniversalReplicateGUI initialized successfully")

    def _get_output_dir(self) -> str:
        """Get output directory based on environment"""
        dockerized = os.environ.get("DOCKER_CONTAINER", "False").lower() == "true"
        
        if dockerized:
            return "/app/output"
        else:
            # Always create a dedicated directory for generated files
            output_folder = "./replicate_outputs"
            os.makedirs(output_folder, exist_ok=True)
            return output_folder

    def _get_database_path(self) -> str:
        """Get database path based on environment"""
        dockerized = os.environ.get("DOCKER_CONTAINER", "False").lower() == "true"
        
        if dockerized:
            return "/app/data/gallery.db"
        else:
            return "./gallery.db"

    def _initialize_model_options(self):
        """Initialize model options from settings"""
        try:
            # Get saved models from settings
            models_json = Settings.get_setting("default", "models", '{"user_added": []}', str)
            models_data = json.loads(models_json)
            user_added = models_data.get("user_added", [])
            
            # Convert to dict format
            if isinstance(user_added, list):
                self.user_added_models = {model: model for model in user_added}
            elif isinstance(user_added, dict):
                self.user_added_models = user_added
            else:
                self.user_added_models = {}
            
            # Create model options
            self.model_options = {model: model for model in self.user_added_models.keys()}
            
            logger.info(f"Loaded {len(self.model_options)} user models")
            
        except Exception as e:
            logger.warning(f"Error loading model options: {e}")
            self.user_added_models = {}
            self.model_options = {}
            
        # Ensure current model is in options
        if self.current_model and self.current_model not in self.model_options:
            self.model_options[self.current_model] = self.current_model

    def setup_ui(self):
        """Setup the main UI"""
        logger.debug("Setting up Universal Replicate GUI")
        
        # Enable dark mode
        ui.dark_mode(True)
        
        with ui.column().classes("w-full h-screen dark:bg-[#11111b] bg-[#eff1f5] overflow-hidden") as self.main_container:
            # Header
            self._setup_header()
            
            # Main content area - using flexbox for proper viewport fitting
            with ui.row().classes("flex-1 gap-4 p-4 h-full overflow-hidden"):
                # Left panel - Model selection and parameters (fixed width)
                with ui.column().classes("w-80 flex-shrink-0 h-full overflow-hidden"):
                    # Fixed model selection at top
                    with ui.element("div").classes("flex-shrink-0"):
                        self._setup_model_selection()
                    
                    # Scrollable parameters and controls
                    with ui.column().classes("flex-1 overflow-y-auto overflow-x-hidden"):
                        self._setup_parameters_panel()
                        self._setup_generation_controls()
                
                # Right panel - Gallery (takes remaining space)
                with ui.column().classes("flex-1 h-full overflow-hidden"):
                    self._setup_gallery_panel()
            
            # Progress indicator
            self._setup_progress_indicator()
            
            # Fixed generation button at bottom
            self._setup_fixed_generation_button()
        
        # Initialize with current model if available
        if self.current_model:
            asyncio.create_task(self._load_model_schema(self.current_model))

    def _setup_header(self):
        """Setup header with title and settings"""
        with ui.row().classes("w-full items-center justify-between p-4 border-b dark:border-[#313244] border-[#dce0e8]"):
            ui.label("Universal Replicate Interface").classes("text-2xl font-bold dark:text-[#cdd6f4] text-[#4c4f69]")
            
            with ui.row().classes("gap-2"):
                ui.button(
                    icon="settings",
                    on_click=self._open_settings_popup,
                    color="blue-4",
                ).props("flat round").tooltip("Settings")
                
                ui.button(
                    icon="help",
                    on_click=self._show_help,
                    color="blue-4",
                ).props("flat round").tooltip("Help")

    def _setup_model_selection(self):
        """Setup model selection with dynamic schema loading"""
        with ui.card().classes("w-full dark:bg-[#181825] bg-[#ccd0da] modern-card"):
            ui.label("Model Selection").classes("text-lg font-bold mb-2 dark:text-[#cdd6f4] text-[#4c4f69]")
            
            with ui.row().classes("w-full gap-2 items-center"):
                # Model dropdown
                self.model_select = ui.select(
                    options=self.model_options,
                    label="Replicate Model",
                    value=self.current_model if self.current_model in self.model_options else None,
                    on_change=self._on_model_change
                ).classes("flex-1").props("filled bg-color=dark")
                
                # Add model button
                ui.button(
                    icon="add",
                    on_click=self._open_add_model_dialog,
                    color="blue-4"
                ).props("flat round").tooltip("Add Model")
                
                # Delete model button
                ui.button(
                    icon="delete",
                    on_click=self._open_delete_model_dialog,
                    color="red-4"
                ).props("flat round").tooltip("Delete Model")
            
            # Model info display
            self.model_info_container = ui.row().classes("w-full mt-2 flex-wrap gap-2")
            self._update_model_info()

    def _setup_parameters_panel(self):
        """Setup dynamic parameters panel"""
        with ui.card().classes("w-full dark:bg-[#181825] bg-[#ccd0da] modern-card"):
            ui.label("Parameters").classes("text-lg font-bold mb-2 dark:text-[#cdd6f4] text-[#4c4f69]")
            
            # Dynamic parameters container
            with ui.column().classes("w-full") as self.params_container:
                # Show dynamic parameters or legacy fallback
                if self.current_schema:
                    self.dynamic_params.set_schema(self.current_schema)
                    self.dynamic_params.get_container()
                else:
                    ui.label("Select a model to see parameters").classes("text-gray-500 text-center py-4")

    def _setup_generation_controls(self):
        """Setup generation controls (without main generate button)"""
        with ui.card().classes("w-full dark:bg-[#181825] bg-[#ccd0da] modern-card"):
            ui.label("Actions").classes("text-lg font-bold mb-2 dark:text-[#cdd6f4] text-[#4c4f69]")
            
            # Quick actions
            with ui.row().classes("w-full gap-2"):
                ui.button(
                    "Clear",
                    on_click=self._clear_parameters,
                    color="grey"
                ).props("flat").classes("flex-1")
                
                ui.button(
                    "Random",
                    on_click=self._randomize_parameters,
                    color="grey"
                ).props("flat").classes("flex-1")

    def _setup_gallery_panel(self):
        """Setup gallery panel"""
        with ui.card().classes("w-full h-full dark:bg-[#181825] bg-[#ccd0da] modern-card"):
            ui.label("Gallery").classes("text-lg font-bold mb-2 dark:text-[#cdd6f4] text-[#4c4f69]")
            
            # Gallery container - let the gallery create its own UI
            self.gallery_container = ui.column().classes("w-full h-full overflow-hidden")
            
            # Set the gallery container and initialize
            with self.gallery_container:
                self.universal_gallery.create_gallery_ui()

    def _setup_progress_indicator(self):
        """Setup progress indicator"""
        self.progress_container = ui.row().classes("w-full justify-center p-2")
        # Initially empty, will be populated during generation

    def _setup_fixed_generation_button(self):
        """Setup fixed generation button at bottom of screen"""
        with ui.element("div").classes("fixed bottom-4 right-4 z-50"):
            self.generate_button = ui.button(
                "Generate",
                on_click=self._generate_output,
                color="blue-4"
            ).classes("modern-button shadow-lg").props("size=lg fab icon=auto_awesome")
            
            # Add tooltip
            self.generate_button.tooltip("Generate with current parameters")

    async def _on_model_change(self, e):
        """Handle model selection change"""
        model_string = e.value
        if model_string:
            self.current_model = model_string
            Settings.set_setting("default", "replicate_model", model_string)
            Settings.save_settings()
            
            await self._load_model_schema(model_string)
            self._update_model_info()

    async def _load_model_schema(self, model_string: str):
        """Load schema for selected model"""
        logger.info(f"Loading schema for model: {model_string}")
        
        try:
            # Show loading state
            self.params_container.clear()
            with self.params_container:
                with ui.column().classes("w-full items-center py-8"):
                    ui.spinner("dots", size="lg").classes("mb-2")
                    ui.label("Loading model schema...").classes("text-center dark:text-[#a6adc8] text-gray-600")
            
            # Fetch schema
            schema = self.schema_service.get_model_schema(model_string)
            
            if schema:
                self.current_schema = schema
                logger.success(f"Schema loaded for {model_string}")
                
                # Update dynamic parameters in the UI context
                self.params_container.clear()
                with self.params_container:
                    self.dynamic_params.set_schema(schema)
                
                # Set model in API
                self.replicate_api.set_model(model_string)
                
            else:
                logger.error(f"Failed to load schema for {model_string}")
                self.current_schema = None
                self.params_container.clear()
                with self.params_container:
                    with ui.column().classes("w-full items-center py-8"):
                        ui.icon("error", size="lg").classes("text-red-500 mb-2")
                        ui.label("Failed to load model schema").classes("text-red-500 text-center mb-4")
                        ui.button(
                            "Retry",
                            on_click=lambda: asyncio.create_task(self._load_model_schema(model_string)),
                            color="primary"
                        ).classes("mx-auto")
        
        except Exception as e:
            logger.error(f"Error loading schema: {e}")
            self.current_schema = None
            self.params_container.clear()
            with self.params_container:
                with ui.column().classes("w-full items-center py-8"):
                    ui.icon("error", size="lg").classes("text-red-500 mb-2")
                    ui.label(f"Error: {str(e)}").classes("text-red-500 text-center")

    def _update_model_info(self):
        """Update model info display"""
        self.model_info_container.clear()
        
        if self.current_schema:
            with self.model_info_container:
                # Model category
                category = self.current_schema.model_info.get("description", "")
                if category:
                    ui.chip(self.current_schema.model_info.get("name", "")).props("color=blue")
                
                # Parameter count
                param_count = len(self.current_schema.input_parameters)
                ui.chip(f"{param_count} parameters").props("color=green")
                
                # Run count
                run_count = self.current_schema.model_info.get("run_count", 0)
                if run_count:
                    ui.chip(f"{run_count:,} runs").props("color=grey")

    def _on_parameter_change(self, param_name: str, value: Any):
        """Handle parameter changes"""
        logger.debug(f"Parameter changed: {param_name} = {value}")
        
        # Save to settings if it's a common parameter
        if param_name in ["prompt", "num_outputs", "aspect_ratio"]:
            Settings.set_setting("default", param_name, value)
            Settings.save_settings()

    async def _generate_output(self):
        """Generate output using current model and parameters"""
        if self.generation_in_progress:
            ui.notify("Generation already in progress", type="warning")
            return
        
        if not self.current_model:
            ui.notify("Please select a model first", type="warning")
            return
        
        if not self.current_schema:
            ui.notify("Model schema not loaded", type="warning")
            return
        
        try:
            self.generation_in_progress = True
            self.generate_button.props("loading")
            
            # Get parameters from dynamic panel
            params = self.dynamic_params.get_parameter_values()
            
            # Validate parameters
            is_valid, errors = self.dynamic_params.validate_parameters()
            if not is_valid:
                ui.notify(f"Invalid parameters: {'; '.join(errors)}", type="negative")
                return
            
            # Show progress
            self._show_progress("Generating...")
            
            # Generate unique ID for this generation
            self.last_generation_id = f"gen_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
            
            logger.info(f"Starting generation {self.last_generation_id} with model {self.current_model}")
            
            # Check if this is a legacy Flux model for backward compatibility
            if self.legacy_bridge.is_flux_model(self.current_model):
                # Convert to legacy format for existing API
                legacy_params = self.legacy_bridge.convert_to_legacy_params(params)
                output = await asyncio.to_thread(self.replicate_api.generate_images, legacy_params)
            else:
                # Use new universal API
                output = await asyncio.to_thread(self.replicate_api.generate_images, params)
            
            self._show_progress("Processing outputs...")
            
            # Process outputs
            processed_outputs = await asyncio.to_thread(
                self.output_handler.process_prediction_output,
                output, self.current_model, self.last_generation_id
            )
            
            if not processed_outputs:
                ui.notify("No outputs generated", type="warning")
                return
            
            self._show_progress("Generating thumbnails...")
            
            # Generate thumbnails
            thumbnail_path = None
            for processed_output in processed_outputs:
                if processed_output.type.value == "image":
                    thumbnail_path = await asyncio.to_thread(self.output_handler.generate_thumbnail, processed_output)
                    break
            
            self._show_progress("Saving to database...")
            
            # Save to database
            model_category = self.schema_service.categorize_model(self.current_model)
            success = await asyncio.to_thread(
                self.gallery_db.save_generation,
                generation_id=self.last_generation_id,
                model_string=self.current_model,
                model_category=model_category,
                input_params=params,
                outputs=processed_outputs,
                thumbnail_path=thumbnail_path
            )
            
            if success:
                ui.notify(f"Generated {len(processed_outputs)} outputs successfully!", type="positive")
                logger.success(f"Generation {self.last_generation_id} completed successfully")
                
                # Refresh gallery
                self.universal_gallery._refresh_gallery()
                
            else:
                ui.notify("Failed to save generation", type="negative")
        
        except Exception as e:
            logger.error(f"Generation failed: {e}")
            ui.notify(f"Generation failed: {str(e)}", type="negative")
        
        finally:
            self.generation_in_progress = False
            self.generate_button.props(remove="loading")
            self._hide_progress()

    def _show_progress(self, message: str):
        """Show progress indicator"""
        self.progress_container.clear()
        with self.progress_container:
            with ui.row().classes("items-center gap-2"):
                ui.spinner("dots", size="lg")
                ui.label(message).classes("text-gray-600")

    def _hide_progress(self):
        """Hide progress indicator"""
        self.progress_container.clear()

    def _clear_parameters(self):
        """Clear all parameters"""
        self.dynamic_params.clear_parameters()
        ui.notify("Parameters cleared", type="info")

    def _randomize_parameters(self):
        """Randomize parameters (placeholder)"""
        ui.notify("Randomize parameters (not implemented)", type="info")

    def _open_add_model_dialog(self):
        """Open dialog to add new model"""
        with ui.dialog() as dialog:
            with ui.card().classes("w-96"):
                ui.label("Add New Model").classes("text-lg font-bold")
                
                model_input = ui.input(
                    label="Model String",
                    placeholder="owner/model-name",
                    validation={"Model string required": lambda x: x.strip() != ""}
                ).classes("w-full")
                
                ui.label("Examples:").classes("text-sm mt-2")
                ui.label("• black-forest-labs/flux-schnell").classes("text-xs text-gray-600")
                ui.label("• stability-ai/sdxl").classes("text-xs text-gray-600")
                ui.label("• meta/llama-2-70b-chat").classes("text-xs text-gray-600")
                
                with ui.row().classes("w-full justify-end gap-2 mt-4"):
                    ui.button("Cancel", on_click=dialog.close).props("flat")
                    ui.button(
                        "Add Model",
                        on_click=lambda: self._add_model(model_input.value, dialog)
                    ).props("color=primary")
        
        dialog.open()

    async def _add_model(self, model_string: str, dialog):
        """Add new model to the list"""
        if not model_string.strip():
            ui.notify("Please enter a model string", type="warning")
            return
        
        try:
            # Test if model exists by fetching schema
            schema = self.schema_service.get_model_schema(model_string)
            
            if schema:
                # Add to user models
                self.user_added_models[model_string] = {
                    "name": schema.model_info.get("name", model_string),
                    "added_at": datetime.now().isoformat()
                }
                
                # Update model options
                self.model_options[model_string] = schema.model_info.get("name", model_string)
                self.model_select.set_options(self.model_options)
                
                # Save to settings
                Settings.set_setting("default", "models", json.dumps({"user_added": self.user_added_models}))
                Settings.save_settings()
                
                # Select the new model
                self.model_select.set_value(model_string)
                
                ui.notify(f"Added model: {model_string}", type="positive")
                dialog.close()
                
            else:
                ui.notify("Model not found or access denied. Check if the model exists and your API key has permission to access it.", type="negative")
        
        except Exception as e:
            error_msg = str(e)
            if "not found" in error_msg.lower():
                ui.notify("Model not found. Check the model name and ensure it exists.", type="negative")
            elif "permission" in error_msg.lower() or "access" in error_msg.lower():
                ui.notify("Access denied. Your API key may not have permission to access this private model.", type="negative")
            elif "authentication" in error_msg.lower():
                ui.notify("Authentication failed. Check your API key configuration.", type="negative")
            else:
                ui.notify(f"Error adding model: {error_msg}", type="negative")

    def _open_delete_model_dialog(self):
        """Open dialog to delete a model"""
        if not self.current_model:
            ui.notify("Please select a model to delete", type="warning")
            return
        
        # Check if it's a user-added model (can't delete default models)
        if self.current_model not in self.user_added_models:
            ui.notify("Cannot delete default models", type="warning")
            return
        
        with ui.dialog() as dialog:
            with ui.card().classes("w-96"):
                ui.label("Delete Model").classes("text-lg font-bold text-red-600")
                
                ui.label("Are you sure you want to delete the model:").classes("mt-2")
                ui.label(f"'{self.current_model}'").classes("font-bold text-sm")
                ui.label("This action cannot be undone.").classes("text-sm text-gray-500 mt-2")
                
                with ui.row().classes("w-full justify-end gap-2 mt-4"):
                    ui.button("Cancel", on_click=dialog.close).props("flat")
                    ui.button(
                        "Delete",
                        on_click=lambda: self._delete_model(self.current_model, dialog)
                    ).props("color=negative")
        
        dialog.open()

    def _delete_model(self, model_string: str, dialog):
        """Delete a model from the list"""
        try:
            # Remove from user added models
            if model_string in self.user_added_models:
                del self.user_added_models[model_string]
            
            # Remove from model options
            if model_string in self.model_options:
                del self.model_options[model_string]
            
            # Update the select dropdown
            self.model_select.set_options(self.model_options)
            
            # If we deleted the current model, reset to None
            if self.current_model == model_string:
                self.current_model = None
                self.model_select.set_value(None)
                self.current_schema = None
                
                # Clear parameters
                self.params_container.clear()
                with self.params_container:
                    ui.label("Select a model to see parameters").classes("text-gray-500 text-center py-4")
            
            # Save to settings
            Settings.set_setting("default", "models", json.dumps({"user_added": self.user_added_models}))
            Settings.save_settings()
            
            ui.notify(f"Deleted model: {model_string}", type="positive")
            dialog.close()
            
        except Exception as e:
            ui.notify(f"Error deleting model: {str(e)}", type="negative")

    def _on_regenerate(self, model_string: str, params: Dict[str, Any]):
        """Handle regenerate request from gallery"""
        # Set model
        self.current_model = model_string
        self.model_select.set_value(model_string)
        
        # Load schema and set parameters
        asyncio.create_task(self._load_model_and_regenerate(model_string, params))

    async def _load_model_and_regenerate(self, model_string: str, params: Dict[str, Any]):
        """Load model and regenerate with parameters"""
        await self._load_model_schema(model_string)
        
        # Set parameters
        for param_name, value in params.items():
            self.dynamic_params.set_parameter_value(param_name, value)
        
        # Trigger generation
        await self._generate_output()

    def _on_model_select(self, model_string: str, params: Dict[str, Any]):
        """Handle model selection from gallery"""
        # Set model
        self.current_model = model_string
        self.model_select.set_value(model_string)
        
        # Load schema and set parameters
        asyncio.create_task(self._load_model_and_set_params(model_string, params))

    async def _load_model_and_set_params(self, model_string: str, params: Dict[str, Any]):
        """Load model and set parameters"""
        await self._load_model_schema(model_string)
        
        # Set parameters
        for param_name, value in params.items():
            self.dynamic_params.set_parameter_value(param_name, value)
        
        ui.notify(f"Loaded model: {model_string}", type="positive")

    def _on_delete_generation(self, generation):
        """Handle delete generation request"""
        success = self.gallery_db.delete_generation(generation.id)
        if success:
            ui.notify("Generation deleted", type="positive")
            self.universal_gallery._refresh_gallery()
        else:
            ui.notify("Failed to delete generation", type="negative")

    def _on_update_generation(self, update_type: str, value: Any):
        """Handle generation update request"""
        if not self.universal_gallery.current_lightbox_item:
            return
        
        generation_id = self.universal_gallery.current_lightbox_item.id
        
        if update_type == "favorite":
            self.gallery_db.toggle_favorite(generation_id)
        
        self.universal_gallery._refresh_gallery()

    def _open_settings_popup(self):
        """Open settings popup"""
        with ui.dialog() as dialog:
            with ui.card().classes("w-96"):
                ui.label("Settings").classes("text-lg font-bold")
                
                # API Key
                api_key_input = ui.input(
                    label="Replicate API Key",
                    value=Settings.get_api_key() or "",
                    password=True,
                    password_toggle_button=True
                ).classes("w-full")
                
                # Output folder
                output_folder_input = ui.input(
                    label="Output Folder",
                    value=Settings.get_setting("default", "output_folder", "./output", str)
                ).classes("w-full")
                
                with ui.row().classes("w-full justify-end gap-2 mt-4"):
                    ui.button("Cancel", on_click=dialog.close).props("flat")
                    ui.button(
                        "Save",
                        on_click=lambda: self._save_settings(api_key_input.value, output_folder_input.value, dialog)
                    ).props("color=primary")
        
        dialog.open()

    def _save_settings(self, api_key: str, output_folder: str, dialog):
        """Save settings"""
        if api_key:
            Settings.set_setting("secrets", "REPLICATE_API_KEY", api_key)
            self.replicate_api.set_api_key(api_key)
            self.schema_service.set_api_key(api_key)
        
        Settings.set_setting("default", "output_folder", output_folder)
        Settings.save_settings()
        
        ui.notify("Settings saved", type="positive")
        dialog.close()

    def _show_help(self):
        """Show help dialog"""
        with ui.dialog() as dialog:
            with ui.card().classes("w-96"):
                ui.label("Help").classes("text-lg font-bold")
                
                ui.label("Universal Replicate Interface").classes("font-bold mt-4")
                ui.label("This interface supports any Replicate model with dynamic parameter generation.")
                
                ui.label("How to use:").classes("font-bold mt-4")
                ui.label("1. Add a model using the + button").classes("text-sm")
                ui.label("2. Select the model from the dropdown").classes("text-sm")
                ui.label("3. Configure parameters automatically generated").classes("text-sm")
                ui.label("4. Click Generate to create outputs").classes("text-sm")
                ui.label("5. View results in the persistent gallery").classes("text-sm")
                
                ui.button("Close", on_click=dialog.close).classes("w-full mt-4")
        
        dialog.open()
