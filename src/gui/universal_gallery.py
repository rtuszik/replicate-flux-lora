import os
from pathlib import Path
from typing import Callable, List, Optional

from loguru import logger
from nicegui import ui

from util.gallery_database import GalleryDatabase, GenerationRecord


class UniversalGallery:
    def __init__(self, 
                 gallery_db: GalleryDatabase,
                 output_dir: str,
                 on_regenerate: Optional[Callable] = None,
                 on_model_select: Optional[Callable] = None):
        self.gallery_db = gallery_db
        self.output_dir = Path(output_dir).resolve()  # Convert to absolute path
        self.on_regenerate = on_regenerate
        self.on_model_select = on_model_select
        
        # UI state
        self.current_filter = "all"
        self.current_sort = "created_at"
        self.sort_order = "DESC"
        self.search_query = ""
        self.page_size = 20
        self.current_page = 0
        self.favorites_only = False
        self.total_items = 0
        self.total_pages = 0
        
        # UI elements
        self.gallery_container = None
        self.stats_container = None
        self.filter_container = None
        self.search_input = None
        self.lightbox_dialog = None
        self.current_lightbox_item = None
        
        # Auto-refresh
        self.auto_refresh_enabled = False
        self.refresh_interval = 5  # seconds
        
        logger.info("UniversalGallery initialized")

    def create_gallery_ui(self) -> ui.element:
        """Create the main gallery UI"""
        
        with ui.column().classes("w-full h-full flex flex-col overflow-hidden") as main_container:
            # Header with stats and controls - fixed at top
            with ui.element("div").classes("flex-shrink-0 p-4 border-b dark:border-[#45475a] border-[#acb0be]"):
                self._create_header()
            
            # Filter and search controls - fixed at top
            with ui.element("div").classes("flex-shrink-0 p-4 border-b dark:border-[#45475a] border-[#acb0be]"):
                self._create_filter_controls()
            
            # Gallery grid - scrollable main content
            self._create_gallery_grid()
            
            # Pagination controls - fixed at bottom
            with ui.element("div").classes("flex-shrink-0 p-4 border-t dark:border-[#45475a] border-[#acb0be]"):
                self._create_pagination_controls()
        
        # Start auto-refresh
        self._start_auto_refresh()
        
        return main_container

    def _create_header(self):
        """Create header with stats and controls"""
        with ui.row().classes("w-full justify-between items-center"):
            # Stats
            self.stats_container = ui.row().classes("gap-4")
            self._update_stats()
            
            # Controls
            with ui.row().classes("gap-2"):
                ui.button("🔄", on_click=self._refresh_gallery).props("flat round").tooltip("Refresh")
                ui.button("📊", on_click=self._show_stats_dialog).props("flat round").tooltip("Statistics")

    def _create_filter_controls(self):
        """Create filter and search controls"""
        with ui.row().classes("w-full gap-4 items-center"):
            # Search
            self.search_input = ui.input(
                placeholder="Search prompts, models...",
                on_change=self._on_search_change
            ).classes("flex-1").props("clearable")
            
            # Category filter
            ui.select(
                options={
                    "all": "All Types",
                    "image-generation": "Images",
                    "video-generation": "Videos", 
                    "audio-generation": "Audio",
                    "text-generation": "Text",
                    "image-processing": "Image Processing",
                    "video-processing": "Video Processing",
                    "audio-processing": "Audio Processing",
                    "unknown": "Other"
                },
                value=self.current_filter,
                on_change=self._on_filter_change
            ).classes("w-48")
            
            # Sort options
            ui.select(
                options={
                    "created_at": "Recent First",
                    "model_string": "Model Name"
                },
                value=self.current_sort,
                on_change=self._on_sort_change
            ).classes("w-40")
            
            # Favorites toggle
            ui.switch(
                "⭐ Favorites only",
                value=self.favorites_only,
                on_change=self._on_favorites_change
            ).classes("whitespace-nowrap")

    def _create_gallery_grid(self):
        """Create the gallery grid container"""
        with ui.element("div").classes("flex-1 overflow-y-auto"):
            self.gallery_container = ui.element("div").classes("grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-4 p-4")
            self._load_gallery_items()

    def _create_pagination_controls(self):
        """Create pagination controls"""
        with ui.row().classes("w-full justify-center items-center gap-4"):
            self.prev_button = ui.button("← Previous", on_click=self._previous_page).props("flat")
            self.page_label = ui.label("Page 1")
            self.next_button = ui.button("Next →", on_click=self._next_page).props("flat")
            
        # Update pagination state
        self._update_pagination_controls()

    def _load_gallery_items(self):
        """Load and display gallery items"""
        if not self.gallery_container:
            return
            
        # Clear existing content
        self.gallery_container.clear()
        
        # Get total count first
        self._update_total_count()
        
        # Get generations from database
        generations = self._get_filtered_generations()
        
        if not generations:
            with self.gallery_container:
                with ui.element("div").classes("col-span-full flex items-center justify-center py-8"):
                    ui.label("No generations found").classes("text-gray-500 text-center")
            self._update_pagination_controls()
            return
        
        # Display each generation
        for generation in generations:
            self._create_generation_card(generation)
            
        # Update pagination controls
        self._update_pagination_controls()

    def _get_filtered_generations(self) -> List[GenerationRecord]:
        """Get filtered generations from database"""
        filter_category = None if self.current_filter == "all" else self.current_filter
        
        if self.search_query:
            return self.gallery_db.search_generations(
                self.search_query,
                limit=self.page_size
            )
        else:
            return self.gallery_db.get_generations(
                limit=self.page_size,
                offset=self.current_page * self.page_size,
                filter_category=filter_category,
                favorites_only=self.favorites_only,
                sort_by=self.current_sort,
                sort_order=self.sort_order
            )

    def _create_generation_card(self, generation: GenerationRecord):
        """Create a simple card for a generation"""
        with self.gallery_container:
            with ui.card().classes("relative cursor-pointer hover:shadow-lg transition-shadow dark:bg-[#181825] bg-[#ccd0da] aspect-square min-h-[200px] min-w-[200px]").on("click", lambda g=generation: self._show_lightbox(g)):
                # Image preview with minimum size container
                with ui.element("div").classes("w-full h-full min-h-[200px] relative"):
                    image_path = self._get_image_path(generation)
                    logger.debug(f"Gallery card for generation {generation.id}: image_path={image_path}")
                    
                    if image_path:
                        logger.debug(f"Using image path for ui.image(): {image_path}")
                        # Try direct file path first (NiceGUI v1.2.20+ can handle local files)
                        if os.path.exists(image_path.replace('/outputs/', 'replicate_outputs/')):
                            direct_path = image_path.replace('/outputs/', 'replicate_outputs/')
                            logger.debug(f"Using direct file path: {direct_path}")
                            ui.image(direct_path).classes("w-full h-full object-cover rounded")
                        else:
                            logger.debug(f"Using URL path: {image_path}")
                            ui.image(image_path).classes("w-full h-full object-cover rounded")
                    else:
                        logger.debug(f"Using placeholder for generation {generation.id}")
                        placeholder = self._create_placeholder(generation)
                        with ui.element("div").classes("w-full h-full dark:bg-[#313244] bg-gray-200 flex items-center justify-center rounded"):
                            ui.label(placeholder).classes("text-4xl")
                
                # Simple overlay with just a favorite button
                with ui.element("div").classes("absolute top-2 right-2"):
                    fav_icon = "⭐" if generation.favorite else "☆"
                    ui.button(fav_icon, on_click=lambda g=generation: self._toggle_favorite(g)).props("flat dense").classes("bg-black bg-opacity-50 text-white")

    def _get_image_path(self, generation: GenerationRecord) -> Optional[str]:
        """Get the first image path for a generation - returns media URL for NiceGUI"""
        logger.debug(f"Getting image path for generation {generation.id}")
        
        if generation.outputs:
            logger.debug(f"Found {len(generation.outputs)} outputs for generation {generation.id}")
            for i, output in enumerate(generation.outputs):
                logger.debug(f"Output {i}: type={output.get('type')}, file_path={output.get('file_path')}")
                
                if output.get("type") == "image" and output.get("file_path"):
                    file_path = output["file_path"]
                    logger.debug(f"Processing image file_path from DB: {file_path}")
                    
                    if os.path.isabs(file_path):
                        abs_path = file_path
                        logger.debug(f"Using absolute path: {abs_path}")
                    else:
                        abs_path = os.path.join(os.getcwd(), file_path)
                        logger.debug(f"Converted to absolute path: {abs_path}")
                    
                    logger.debug(f"Checking if file exists: {os.path.exists(abs_path)}")
                    if os.path.exists(abs_path):
                        if file_path.startswith("replicate_outputs/"):
                            media_url = f"/outputs/{file_path.replace('replicate_outputs/', '')}"
                        else:
                            rel_path = os.path.relpath(abs_path, str(self.output_dir))
                            media_url = f"/outputs/{rel_path}"
                        
                        logger.debug(f"File exists, returning media URL: {media_url}")
                        return media_url
                    else:
                        logger.debug(f"File does not exist: {abs_path}")
        else:
            logger.debug(f"No outputs found for generation {generation.id}")
        
        logger.debug(f"No image path found for generation {generation.id}")
        return None

    def _convert_to_url(self, file_path: str, output_type: str = "image") -> str:
        """Convert file path to appropriate URL for NiceGUI serving"""
        logger.debug(f"Converting to URL: {file_path}, type: {output_type}")
        
        if os.path.isabs(file_path):
            abs_path = file_path
        else:
            abs_path = os.path.join(os.getcwd(), file_path)
        
        logger.debug(f"Absolute path: {abs_path}")
        logger.debug(f"File exists: {os.path.exists(abs_path)}")
        
        if os.path.exists(abs_path):
            if file_path.startswith("replicate_outputs/"):
                rel_path = file_path.replace('replicate_outputs/', '')
            else:
                rel_path = os.path.relpath(abs_path, str(self.output_dir))
            
            # Use static files for images, media files for videos/audio
            if output_type in ["video", "audio"]:
                url = f"/media/{rel_path}"
            else:
                url = f"/outputs/{rel_path}"
            
            logger.debug(f"Generated URL: {url}")
            return url
        
        logger.debug(f"File does not exist, returning original path: {file_path}")
        return file_path

    def _create_placeholder(self, generation: GenerationRecord) -> str:
        """Create placeholder icon based on generation type"""
        category = generation.model_category
        
        placeholders = {
            "image-generation": "🖼️",
            "video-generation": "🎬",
            "audio-generation": "🎵",
            "text-generation": "📝",
            "image-processing": "🎨",
            "video-processing": "🎞️",
            "audio-processing": "🎧",
        }
        
        return placeholders.get(category, "📄")

    def _get_prompt_preview(self, generation: GenerationRecord) -> Optional[str]:
        """Get prompt preview from generation parameters"""
        if not generation.input_params:
            return None
        
        # Look for common prompt parameter names
        prompt_keys = ["prompt", "text", "input", "query", "instruction"]
        
        for key in prompt_keys:
            if key in generation.input_params:
                prompt = generation.input_params[key]
                if isinstance(prompt, str) and prompt.strip():
                    return prompt[:100] + "..." if len(prompt) > 100 else prompt
        
        return None

    def _show_lightbox(self, generation: GenerationRecord):
        """Show lightbox with generation details"""
        self.current_lightbox_item = generation
        
        if self.lightbox_dialog:
            self.lightbox_dialog.close()
        
        with ui.dialog().classes("w-full max-w-6xl") as dialog:
            self.lightbox_dialog = dialog
            
            with ui.card().classes("w-full h-full"):
                # Header
                with ui.row().classes("w-full justify-between items-center p-4"):
                    ui.label(generation.model_string).classes("text-xl font-bold")
                    ui.button("✕", on_click=dialog.close).props("flat round")
                
                # Content
                with ui.row().classes("w-full gap-4 p-4"):
                    # Left: Outputs
                    with ui.column().classes("flex-1"):
                        self._create_lightbox_outputs(generation)
                    
                    # Right: Details
                    with ui.column().classes("w-80"):
                        self._create_lightbox_details(generation)
        
        dialog.open()

    def _create_lightbox_outputs(self, generation: GenerationRecord):
        """Create outputs display for lightbox"""
        if not generation.outputs:
            ui.label("No outputs found").classes("text-gray-500")
            return
        
        for i, output in enumerate(generation.outputs):
            output_type = output.get("type", "unknown")
            file_path = output.get("file_path")
            
            if not file_path or not os.path.exists(file_path):
                continue
            
            with ui.card().classes("w-full mb-4"):
                ui.label(f"Output {i+1} - {output_type.title()}").classes("font-bold")
                
                if output_type == "image":
                    ui.image(self._convert_to_url(file_path, "image")).classes("w-full max-h-96 object-contain")
                elif output_type == "video":
                    ui.video(self._convert_to_url(file_path, "video")).classes("w-full max-h-96")
                elif output_type == "audio":
                    ui.audio(self._convert_to_url(file_path, "audio")).classes("w-full")
                elif output_type == "text":
                    # Read and display text content
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                        ui.textarea(value=content, readonly=True).classes("w-full h-32")
                    except Exception as e:
                        ui.label(f"Error reading text: {e}").classes("text-red-500")
                elif output_type == "json":
                    # Read and display JSON content
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                        ui.code(content, language="json").classes("w-full")
                    except Exception as e:
                        ui.label(f"Error reading JSON: {e}").classes("text-red-500")
                else:
                    ui.label(f"File: {Path(file_path).name}").classes("text-gray-600")
                    ui.button("Download", on_click=lambda fp=file_path: self._download_file(fp)).props("flat")

    def _create_lightbox_details(self, generation: GenerationRecord):
        """Create details panel for lightbox"""
        # Basic info
        with ui.card().classes("w-full mb-4"):
            ui.label("Generation Details").classes("font-bold mb-2")
            
            ui.label(f"Model: {generation.model_string}").classes("text-sm")
            ui.label(f"Category: {generation.model_category}").classes("text-sm")
            ui.label(f"Created: {generation.created_at.strftime('%Y-%m-%d %H:%M:%S')}").classes("text-sm")
            ui.label(f"Outputs: {len(generation.outputs)}").classes("text-sm")
        
        # Parameters
        with ui.card().classes("w-full mb-4"):
            ui.label("Parameters").classes("font-bold mb-2")
            
            if generation.input_params:
                for key, value in generation.input_params.items():
                    if isinstance(value, str) and len(value) > 50:
                        ui.label(f"{key}:").classes("text-sm font-medium")
                        ui.textarea(value=value, readonly=True).classes("w-full h-20 text-xs")
                    else:
                        ui.label(f"{key}: {value}").classes("text-sm")
            else:
                ui.label("No parameters").classes("text-sm text-gray-500")
        
        # Actions
        with ui.card().classes("w-full mb-4"):
            ui.label("Actions").classes("font-bold mb-2")
            
            # Favorite
            fav_text = "Remove from Favorites" if generation.favorite else "Add to Favorites"
            ui.button(fav_text, on_click=lambda: self._toggle_favorite(generation)).classes("w-full mb-2")
            
            
            # Regenerate
            if self.on_regenerate:
                ui.button(
                    "Regenerate",
                    on_click=lambda: self._regenerate_item(generation)
                ).classes("w-full mt-2").props("color=primary")
            
            # Use Model
            if self.on_model_select:
                ui.button(
                    "Use This Model",
                    on_click=lambda: self._use_model(generation)
                ).classes("w-full mt-2").props("color=secondary")
            
            # Delete
            ui.button(
                "Delete",
                on_click=lambda: self._delete_item(generation)
            ).classes("w-full mt-2").props("color=negative")

    def _toggle_favorite(self, generation: GenerationRecord):
        """Toggle favorite status"""
        self.gallery_db.toggle_favorite(generation.id)
        self._refresh_gallery()


    def _regenerate_item(self, generation: GenerationRecord):
        """Regenerate item using same parameters"""
        if self.on_regenerate:
            self.on_regenerate(generation.model_string, generation.input_params)
        
        if self.lightbox_dialog:
            self.lightbox_dialog.close()

    def _use_model(self, generation: GenerationRecord):
        """Use this model in the main interface"""
        if self.on_model_select:
            self.on_model_select(generation.model_string, generation.input_params)
        
        if self.lightbox_dialog:
            self.lightbox_dialog.close()

    def _delete_item(self, generation: GenerationRecord):
        """Delete generation with confirmation"""
        with ui.dialog() as confirm_dialog:
            with ui.card():
                ui.label("Delete Generation").classes("text-lg font-bold")
                ui.label("Are you sure you want to delete this generation? This action cannot be undone.")
                
                with ui.row().classes("w-full justify-end gap-2 mt-4"):
                    ui.button("Cancel", on_click=confirm_dialog.close).props("flat")
                    ui.button(
                        "Delete",
                        on_click=lambda: self._confirm_delete(generation, confirm_dialog)
                    ).props("color=negative")
        
        confirm_dialog.open()

    def _confirm_delete(self, generation: GenerationRecord, dialog):
        """Confirm deletion"""
        success = self.gallery_db.delete_generation(generation.id)
        
        if success:
            ui.notify("Generation deleted successfully", type="positive")
            self._refresh_gallery()
        else:
            ui.notify("Error deleting generation", type="negative")
        
        dialog.close()
        if self.lightbox_dialog:
            self.lightbox_dialog.close()

    def _download_file(self, file_path: str):
        """Download file"""
        if os.path.exists(file_path):
            # For NiceGUI, we need to serve the file
            # This is a simplified approach - in production you'd want proper file serving
            ui.notify(f"File path: {file_path}", type="info")
        else:
            ui.notify("File not found", type="negative")

    def _show_actions_menu(self, generation: GenerationRecord):
        """Show actions menu for generation"""
        # This would show a dropdown menu with actions
        # For now, just show the lightbox
        self._show_lightbox(generation)

    def _show_cleanup_dialog(self):
        """Show cleanup dialog"""
        with ui.dialog() as cleanup_dialog:
            with ui.card():
                ui.label("Cleanup Database").classes("text-lg font-bold")
                ui.label("This will remove database entries for missing files and delete orphaned files.")
                
                with ui.row().classes("w-full justify-end gap-2 mt-4"):
                    ui.button("Cancel", on_click=cleanup_dialog.close).props("flat")
                    ui.button(
                        "Cleanup",
                        on_click=lambda: self._perform_cleanup(cleanup_dialog)
                    ).props("color=primary")
        
        cleanup_dialog.open()

    def _perform_cleanup(self, dialog):
        """Perform database cleanup"""
        stats = self.gallery_db.sync_with_filesystem(str(self.output_dir))
        
        ui.notify(f"Cleanup complete: {stats['removed_records']} records, {stats['removed_files']} files removed", type="positive")
        
        self._refresh_gallery()
        dialog.close()

    def _show_stats_dialog(self):
        """Show statistics dialog"""
        with ui.dialog() as stats_dialog:
            with ui.card().classes("w-96"):
                ui.label("Gallery Statistics").classes("text-lg font-bold")
                
                # Database stats
                db_stats = self.gallery_db.get_database_stats()
                ui.label(f"Total Generations: {db_stats.get('total_generations', 0)}")
                ui.label(f"Total Outputs: {db_stats.get('total_outputs', 0)}")
                ui.label(f"Favorites: {db_stats.get('favorites', 0)}")
                ui.label(f"Database Size: {db_stats.get('db_size_bytes', 0) / 1024:.1f} KB")
                
                # Model usage
                ui.label("Top Models:").classes("font-bold mt-4")
                model_stats = self.gallery_db.get_model_usage_stats()
                for model, count in list(model_stats.items())[:5]:
                    ui.label(f"  {model}: {count} uses")
                
                # Category stats
                ui.label("By Category:").classes("font-bold mt-4")
                category_stats = self.gallery_db.get_category_stats()
                for category, count in category_stats.items():
                    ui.label(f"  {category}: {count} generations")
                
                ui.button("Close", on_click=stats_dialog.close).classes("w-full mt-4")
        
        stats_dialog.open()

    def _update_stats(self):
        """Update stats display"""
        if not self.stats_container:
            return
        
        self.stats_container.clear()
        
        db_stats = self.gallery_db.get_database_stats()
        total = db_stats.get('total_generations', 0)
        favorites = db_stats.get('favorites', 0)
        
        with self.stats_container:
            ui.label(f"📊 {total} generations").classes("text-sm")
            ui.label(f"⭐ {favorites} favorites").classes("text-sm")

    def _on_search_change(self, e):
        """Handle search input change"""
        self.search_query = e.value
        self.current_page = 0
        self._load_gallery_items()

    def _on_filter_change(self, e):
        """Handle filter change"""
        self.current_filter = e.value
        self.current_page = 0
        self._load_gallery_items()

    def _on_sort_change(self, e):
        """Handle sort change"""
        self.current_sort = e.value
        self.current_page = 0
        self._load_gallery_items()

    def _on_favorites_change(self, e):
        """Handle favorites toggle"""
        self.favorites_only = e.value
        self.current_page = 0
        self._load_gallery_items()

    def _update_total_count(self):
        """Update total count and pages"""
        filter_category = None if self.current_filter == "all" else self.current_filter
        
        if self.search_query:
            # For search, we need to count all results
            all_results = self.gallery_db.search_generations(
                self.search_query,
                limit=10000  # Large limit to get all results
            )
            self.total_items = len(all_results)
        else:
            # Get count from database
            self.total_items = self.gallery_db.get_generation_count(
                filter_category=filter_category,
                favorites_only=self.favorites_only
            )
        
        self.total_pages = max(1, (self.total_items + self.page_size - 1) // self.page_size)
        
        # Ensure current page is valid
        if self.current_page >= self.total_pages:
            self.current_page = max(0, self.total_pages - 1)
    
    def _update_pagination_controls(self):
        """Update pagination control states"""
        if hasattr(self, 'prev_button'):
            self.prev_button.set_enabled(self.current_page > 0)
        
        if hasattr(self, 'next_button'):
            self.next_button.set_enabled(self.current_page < self.total_pages - 1)
            
        if hasattr(self, 'page_label'):
            self.page_label.set_text(f"Page {self.current_page + 1} of {self.total_pages}")

    def _previous_page(self):
        """Go to previous page"""
        if self.current_page > 0:
            self.current_page -= 1
            self._load_gallery_items()

    def _next_page(self):
        """Go to next page"""
        if self.current_page < self.total_pages - 1:
            self.current_page += 1
            self._load_gallery_items()

    def _refresh_gallery(self):
        """Refresh gallery display"""
        self.current_page = 0  # Reset to first page
        self._load_gallery_items()
        self._update_stats()

    def _start_auto_refresh(self):
        """Start auto-refresh timer"""
        if self.auto_refresh_enabled:
            ui.timer(self.refresh_interval, self._refresh_gallery, once=False)

    def add_generation(self, generation: GenerationRecord):
        """Add a new generation to the gallery"""
        # This would be called when a new generation is completed
        self._refresh_gallery()

    def set_auto_refresh(self, enabled: bool):
        """Enable/disable auto-refresh"""
        self.auto_refresh_enabled = enabled
