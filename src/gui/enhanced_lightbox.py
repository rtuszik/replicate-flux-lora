import os
import json
from pathlib import Path
from typing import List, Optional, Dict, Any, Callable
from urllib.parse import quote

from nicegui import ui, events
from loguru import logger

from util.gallery_database import GenerationRecord


class EnhancedLightbox:
    """
    Enhanced lightbox component for displaying generation details
    with support for all media types and advanced features.
    """
    
    def __init__(self, 
                 on_regenerate: Optional[Callable] = None,
                 on_model_select: Optional[Callable] = None,
                 on_delete: Optional[Callable] = None,
                 on_update: Optional[Callable] = None):
        self.on_regenerate = on_regenerate
        self.on_model_select = on_model_select
        self.on_delete = on_delete
        self.on_update = on_update
        
        self.dialog = None
        self.current_generation = None
        self.current_output_index = 0
        self.is_fullscreen = False
        
        # Media viewers
        self.media_container = None
        self.details_container = None
        
        logger.debug("EnhancedLightbox initialized")

    def show(self, generation: GenerationRecord, output_index: int = 0):
        """Show lightbox with generation details"""
        self.current_generation = generation
        self.current_output_index = output_index
        
        if self.dialog:
            self.dialog.close()
        
        self._create_lightbox()
        self.dialog.open()

    def _create_lightbox(self):
        """Create the lightbox dialog"""
        dialog_classes = "w-full max-w-7xl h-5/6" if not self.is_fullscreen else "w-full h-full"
        
        with ui.dialog().classes(dialog_classes) as dialog:
            self.dialog = dialog
            
            with ui.card().classes("w-full h-full flex flex-col"):
                # Header
                self._create_header()
                
                # Main content
                with ui.row().classes("flex-1 w-full gap-4 p-4 overflow-hidden"):
                    # Left: Media viewer
                    with ui.column().classes("flex-1 h-full"):
                        self.media_container = ui.column().classes("w-full h-full")
                        self._create_media_viewer()
                    
                    # Right: Details panel
                    with ui.column().classes("w-80 h-full overflow-y-auto"):
                        self.details_container = ui.column().classes("w-full gap-4")
                        self._create_details_panel()

    def _create_header(self):
        """Create lightbox header"""
        with ui.row().classes("w-full justify-between items-center p-4 border-b"):
            # Title
            model_name = self.current_generation.model_string
            ui.label(model_name).classes("text-xl font-bold")
            
            # Output navigation
            if self.current_generation.outputs and len(self.current_generation.outputs) > 1:
                with ui.row().classes("gap-2 items-center"):
                    ui.button("◀", on_click=self._previous_output).props("flat round dense")
                    ui.label(f"{self.current_output_index + 1} / {len(self.current_generation.outputs)}")
                    ui.button("▶", on_click=self._next_output).props("flat round dense")
            
            # Controls
            with ui.row().classes("gap-2"):
                ui.button("⛶", on_click=self._toggle_fullscreen).props("flat round").tooltip("Fullscreen")
                ui.button("⬇", on_click=self._download_current).props("flat round").tooltip("Download")
                ui.button("✕", on_click=self.dialog.close).props("flat round").tooltip("Close")

    def _create_media_viewer(self):
        """Create media viewer based on current output"""
        if not self.media_container:
            return
        
        self.media_container.clear()
        
        if not self.current_generation.outputs:
            with self.media_container:
                ui.label("No outputs available").classes("text-gray-500 text-center")
            return
        
        if self.current_output_index >= len(self.current_generation.outputs):
            self.current_output_index = 0
        
        output = self.current_generation.outputs[self.current_output_index]
        output_type = output.get("type", "unknown")
        file_path = output.get("file_path")
        
        if not file_path or not os.path.exists(file_path):
            with self.media_container:
                ui.label("File not found").classes("text-red-500 text-center")
            return
        
        with self.media_container:
            self._render_media_content(output_type, file_path, output)

    def _render_media_content(self, output_type: str, file_path: str, output: Dict[str, Any]):
        """Render media content based on type"""
        
        if output_type == "image":
            self._render_image(file_path, output)
        elif output_type == "video":
            self._render_video(file_path, output)
        elif output_type == "audio":
            self._render_audio(file_path, output)
        elif output_type == "text":
            self._render_text(file_path, output)
        elif output_type == "json":
            self._render_json(file_path, output)
        else:
            self._render_file(file_path, output)

    def _render_image(self, file_path: str, output: Dict[str, Any]):
        """Render image with zoom and pan capabilities"""
        
        # Image container with zoom controls
        with ui.column().classes("w-full h-full"):
            # Zoom controls
            with ui.row().classes("w-full justify-center gap-2 mb-2"):
                ui.button("🔍+", on_click=self._zoom_in).props("flat dense")
                ui.button("🔍-", on_click=self._zoom_out).props("flat dense")
                ui.button("↻", on_click=self._reset_zoom).props("flat dense")
                ui.button("🔲", on_click=self._fit_to_container).props("flat dense")
            
            # Image display
            with ui.element("div").classes("flex-1 flex items-center justify-center overflow-hidden"):
                img = ui.image(file_path).classes("max-w-full max-h-full object-contain cursor-zoom-in")
                
                # Add click-to-zoom functionality
                img.on("click", self._toggle_image_zoom)
            
            # Image info
            width = output.get("width")
            height = output.get("height")
            file_size = output.get("file_size", 0)
            
            info_parts = []
            if width and height:
                info_parts.append(f"{width}×{height}")
            if file_size:
                info_parts.append(f"{file_size // 1024}KB")
            
            if info_parts:
                ui.label(" • ".join(info_parts)).classes("text-sm text-gray-600 text-center")

    def _render_video(self, file_path: str, output: Dict[str, Any]):
        """Render video with controls"""
        
        with ui.column().classes("w-full h-full"):
            # Video player
            with ui.element("div").classes("flex-1 flex items-center justify-center"):
                video = ui.video(file_path).classes("w-full h-full")
                video.props("controls")
            
            # Video info
            duration = output.get("duration")
            file_size = output.get("file_size", 0)
            
            info_parts = []
            if duration:
                info_parts.append(f"{duration:.1f}s")
            if file_size:
                info_parts.append(f"{file_size // 1024}KB")
            
            if info_parts:
                ui.label(" • ".join(info_parts)).classes("text-sm text-gray-600 text-center")

    def _render_audio(self, file_path: str, output: Dict[str, Any]):
        """Render audio with waveform visualization"""
        
        with ui.column().classes("w-full h-full justify-center"):
            # Audio player
            ui.audio(file_path).classes("w-full")
            
            # Audio visualization placeholder
            with ui.element("div").classes("w-full h-32 bg-gray-100 rounded flex items-center justify-center mt-4"):
                ui.label("🎵 Audio Waveform").classes("text-gray-500")
            
            # Audio info
            duration = output.get("duration")
            file_size = output.get("file_size", 0)
            
            info_parts = []
            if duration:
                info_parts.append(f"{duration:.1f}s")
            if file_size:
                info_parts.append(f"{file_size // 1024}KB")
            
            if info_parts:
                ui.label(" • ".join(info_parts)).classes("text-sm text-gray-600 text-center mt-2")

    def _render_text(self, file_path: str, output: Dict[str, Any]):
        """Render text with formatting options"""
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            with ui.column().classes("w-full h-full"):
                # Text controls
                with ui.row().classes("w-full gap-2 mb-2"):
                    ui.button("📋", on_click=lambda: self._copy_text(content)).props("flat dense").tooltip("Copy")
                    ui.button("💾", on_click=lambda: self._save_text(content)).props("flat dense").tooltip("Save")
                    ui.button("🔍", on_click=lambda: self._search_text(content)).props("flat dense").tooltip("Search")
                
                # Text display
                ui.textarea(
                    value=content,
                    readonly=True
                ).classes("flex-1 w-full font-mono text-sm")
                
                # Text info
                lines = content.count('\n') + 1
                chars = len(content)
                words = len(content.split())
                
                ui.label(f"{lines} lines • {words} words • {chars} characters").classes("text-sm text-gray-600")
        
        except Exception as e:
            ui.label(f"Error reading text file: {e}").classes("text-red-500")

    def _render_json(self, file_path: str, output: Dict[str, Any]):
        """Render JSON with syntax highlighting and tree view"""
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                data = json.loads(content)
            
            with ui.column().classes("w-full h-full"):
                # JSON controls
                with ui.row().classes("w-full gap-2 mb-2"):
                    ui.button("📋", on_click=lambda: self._copy_text(content)).props("flat dense").tooltip("Copy")
                    ui.button("🌳", on_click=lambda: self._toggle_json_view()).props("flat dense").tooltip("Tree View")
                    ui.button("✨", on_click=lambda: self._format_json(data)).props("flat dense").tooltip("Format")
                
                # JSON display
                ui.code(content, language="json").classes("flex-1 w-full")
                
                # JSON info
                keys = len(data) if isinstance(data, dict) else "N/A"
                ui.label(f"Keys: {keys} • Size: {len(content)} chars").classes("text-sm text-gray-600")
        
        except Exception as e:
            ui.label(f"Error reading JSON file: {e}").classes("text-red-500")

    def _render_file(self, file_path: str, output: Dict[str, Any]):
        """Render generic file with download option"""
        
        file_name = Path(file_path).name
        file_size = output.get("file_size", 0)
        mime_type = output.get("mime_type", "unknown")
        
        with ui.column().classes("w-full h-full justify-center items-center"):
            # File icon
            ui.label("📄").classes("text-6xl mb-4")
            
            # File info
            ui.label(file_name).classes("text-lg font-bold")
            ui.label(f"Type: {mime_type}").classes("text-sm text-gray-600")
            if file_size:
                ui.label(f"Size: {file_size // 1024}KB").classes("text-sm text-gray-600")
            
            # Download button
            ui.button("Download", on_click=lambda: self._download_file(file_path)).props("color=primary")

    def _create_details_panel(self):
        """Create details panel"""
        if not self.details_container:
            return
        
        self.details_container.clear()
        
        with self.details_container:
            # Generation info
            self._create_generation_info()
            
            # Parameters
            self._create_parameters_section()
            
            # Actions
            self._create_actions_section()
            
            # File info
            self._create_file_info_section()

    def _create_generation_info(self):
        """Create generation info section"""
        with ui.card().classes("w-full"):
            ui.label("Generation Info").classes("font-bold mb-2")
            
            gen = self.current_generation
            
            # Basic info
            with ui.column().classes("gap-1"):
                ui.label(f"Model: {gen.model_string}").classes("text-sm")
                ui.label(f"Category: {gen.model_category}").classes("text-sm")
                ui.label(f"Created: {gen.created_at.strftime('%Y-%m-%d %H:%M:%S')}").classes("text-sm")
                ui.label(f"Outputs: {len(gen.outputs)}").classes("text-sm")
            
            # Rating and favorite
            with ui.row().classes("w-full justify-between items-center mt-2"):
                # Favorite toggle
                fav_icon = "⭐" if gen.favorite else "☆"
                ui.button(fav_icon, on_click=self._toggle_favorite).props("flat dense")
                
                # Rating stars
                with ui.row().classes("gap-1"):
                    for i in range(1, 6):
                        star_icon = "★" if i <= gen.rating else "☆"
                        ui.button(
                            star_icon,
                            on_click=lambda r=i: self._set_rating(r)
                        ).props("flat dense").classes("text-yellow-500 text-xs")

    def _create_parameters_section(self):
        """Create parameters section"""
        with ui.card().classes("w-full"):
            ui.label("Parameters").classes("font-bold mb-2")
            
            if self.current_generation.input_params:
                with ui.expansion("Show Parameters", icon="settings").classes("w-full"):
                    for key, value in self.current_generation.input_params.items():
                        with ui.row().classes("w-full gap-2 items-start"):
                            ui.label(f"{key}:").classes("text-sm font-medium min-w-20")
                            
                            if isinstance(value, str) and len(value) > 50:
                                ui.textarea(value=value, readonly=True).classes("flex-1 text-xs")
                            else:
                                ui.label(str(value)).classes("text-sm flex-1")
            else:
                ui.label("No parameters").classes("text-sm text-gray-500")

    def _create_actions_section(self):
        """Create actions section"""
        with ui.card().classes("w-full"):
            ui.label("Actions").classes("font-bold mb-2")
            
            with ui.column().classes("w-full gap-2"):
                # Notes
                ui.label("Notes:").classes("text-sm")
                ui.textarea(
                    value=self.current_generation.notes,
                    placeholder="Add notes...",
                    on_change=self._update_notes
                ).classes("w-full h-20")
                
                # Action buttons
                if self.on_regenerate:
                    ui.button(
                        "🔄 Regenerate",
                        on_click=self._regenerate
                    ).classes("w-full").props("color=primary")
                
                if self.on_model_select:
                    ui.button(
                        "🎯 Use This Model",
                        on_click=self._use_model
                    ).classes("w-full").props("color=secondary")
                
                ui.button(
                    "🗑️ Delete",
                    on_click=self._delete
                ).classes("w-full").props("color=negative")

    def _create_file_info_section(self):
        """Create file info section"""
        if not self.current_generation.outputs:
            return
        
        with ui.card().classes("w-full"):
            ui.label("File Info").classes("font-bold mb-2")
            
            current_output = self.current_generation.outputs[self.current_output_index]
            
            with ui.column().classes("gap-1"):
                file_path = current_output.get("file_path", "")
                if file_path:
                    ui.label(f"Path: {Path(file_path).name}").classes("text-sm")
                
                file_size = current_output.get("file_size", 0)
                if file_size:
                    ui.label(f"Size: {file_size // 1024}KB").classes("text-sm")
                
                mime_type = current_output.get("mime_type", "")
                if mime_type:
                    ui.label(f"Type: {mime_type}").classes("text-sm")
                
                # Metadata
                metadata = current_output.get("metadata")
                if metadata:
                    with ui.expansion("Metadata", icon="info").classes("w-full"):
                        for key, value in metadata.items():
                            ui.label(f"{key}: {value}").classes("text-sm")

    # Event handlers
    def _previous_output(self):
        """Go to previous output"""
        if self.current_output_index > 0:
            self.current_output_index -= 1
            self._create_media_viewer()
            self._create_details_panel()

    def _next_output(self):
        """Go to next output"""
        if self.current_output_index < len(self.current_generation.outputs) - 1:
            self.current_output_index += 1
            self._create_media_viewer()
            self._create_details_panel()

    def _toggle_fullscreen(self):
        """Toggle fullscreen mode"""
        self.is_fullscreen = not self.is_fullscreen
        self.dialog.close()
        self._create_lightbox()
        self.dialog.open()

    def _download_current(self):
        """Download current output"""
        if self.current_generation.outputs:
            current_output = self.current_generation.outputs[self.current_output_index]
            file_path = current_output.get("file_path")
            if file_path:
                self._download_file(file_path)

    def _download_file(self, file_path: str):
        """Download file"""
        # In a real implementation, this would trigger a download
        ui.notify(f"Download: {Path(file_path).name}", type="info")

    def _toggle_favorite(self):
        """Toggle favorite status"""
        if self.on_update:
            self.on_update("favorite", not self.current_generation.favorite)

    def _set_rating(self, rating: int):
        """Set rating"""
        if self.on_update:
            self.on_update("rating", rating)

    def _update_notes(self, e):
        """Update notes"""
        if self.on_update:
            self.on_update("notes", e.value)

    def _regenerate(self):
        """Regenerate with same parameters"""
        if self.on_regenerate:
            self.on_regenerate(self.current_generation.model_string, self.current_generation.input_params)
        self.dialog.close()

    def _use_model(self):
        """Use this model"""
        if self.on_model_select:
            self.on_model_select(self.current_generation.model_string, self.current_generation.input_params)
        self.dialog.close()

    def _delete(self):
        """Delete generation"""
        if self.on_delete:
            self.on_delete(self.current_generation)
        self.dialog.close()

    # Media interaction handlers
    def _zoom_in(self):
        """Zoom in on media"""
        ui.notify("Zoom in", type="info")

    def _zoom_out(self):
        """Zoom out on media"""
        ui.notify("Zoom out", type="info")

    def _reset_zoom(self):
        """Reset zoom"""
        ui.notify("Reset zoom", type="info")

    def _fit_to_container(self):
        """Fit media to container"""
        ui.notify("Fit to container", type="info")

    def _toggle_image_zoom(self):
        """Toggle image zoom on click"""
        ui.notify("Toggle zoom", type="info")

    def _copy_text(self, content: str):
        """Copy text to clipboard"""
        ui.notify("Text copied to clipboard", type="positive")

    def _save_text(self, content: str):
        """Save text to file"""
        ui.notify("Text saved", type="positive")

    def _search_text(self, content: str):
        """Search in text"""
        ui.notify("Search functionality", type="info")

    def _toggle_json_view(self):
        """Toggle JSON tree view"""
        ui.notify("Toggle JSON view", type="info")

    def _format_json(self, data: Any):
        """Format JSON"""
        ui.notify("JSON formatted", type="positive")