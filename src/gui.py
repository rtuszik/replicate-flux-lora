import asyncio
import json
import os
import sys
import urllib.parse
from datetime import datetime
from pathlib import Path

import httpx
from loguru import logger
from nicegui import events, ui

# Configure Loguru
logger.remove()  # Remove the default handler
logger.add(
    sys.stderr, format="{time} {level} {message}", filter="my_module", level="INFO"
)
logger.add("gui.log", rotation="10 MB", format="{time} {level} {message}", level="INFO")


class Lightbox:
    def __init__(self):
        with ui.dialog().props("maximized").classes("bg-black") as self.dialog:
            ui.keyboard(self._handle_key)
            self.large_image = ui.image().props("no-spinner fit=scale-down")
        self.image_list = []

    def add_image(self, thumb_url: str, orig_url: str) -> ui.image:
        self.image_list.append(orig_url)
        with ui.button(on_click=lambda: self._open(orig_url)).props(
            "flat dense square"
        ):
            return ui.image(thumb_url)

    def _handle_key(self, event_args: events.KeyEventArguments) -> None:
        if not event_args.action.keydown:
            return
        if event_args.key.escape:
            self.dialog.close()
        image_index = self.image_list.index(self.large_image.source)
        if event_args.key.arrow_left and image_index > 0:
            self._open(self.image_list[image_index - 1])
        if event_args.key.arrow_right and image_index < len(self.image_list) - 1:
            self._open(self.image_list[image_index + 1])

    def _open(self, url: str) -> None:
        self.large_image.set_source(url)
        self.dialog.open()


class ImageGeneratorGUI:
    def __init__(self, image_generator):
        self.image_generator = image_generator
        self.settings_file = "settings.json"
        self.load_settings()
        self.recent_replicate_models = self.load_recent_replicate_models()
        self.setup_ui()
        logger.info("ImageGeneratorGUI initialized")

    def setup_ui(self):
        ui.dark_mode().enable()

        with ui.column().classes("w-full max-w-7xl mx-auto p-4 space-y-4"):
            with ui.card().classes("w-full"):
                ui.label("Image Generator").classes("text-2xl font-bold mb-4")
                with ui.row().classes("w-full justify-between"):
                    with ui.column().classes("w-1/2 pr-2"):
                        self.setup_left_panel()
                    with ui.column().classes("w-1/2 pl-2"):
                        self.setup_right_panel()
                self.setup_bottom_panel()
        logger.info("UI setup completed")

    def setup_left_panel(self):
        self.replicate_model_input = ui.input(
            "Replicate Model", value=self.settings.get("replicate_model", "")
        ).classes("w-full")
        self.replicate_model_input.on("change", self.update_replicate_model)

        self.recent_models_select = ui.select(
            options=self.recent_replicate_models,
            label="Recent Models",
            value=None,
            on_change=self.select_recent_model,
        ).classes("w-full")

        self.folder_path = self.settings.get(
            "output_folder", str(Path.home() / "Downloads")
        )
        self.folder_input = ui.input(
            label="Output Folder", value=self.folder_path
        ).classes("w-full")
        self.folder_input.on("change", self.update_folder_path)

        self.flux_model_select = (
            ui.select(
                ["dev", "schnell"],
                label="Flux Model",
                value=self.settings.get("flux_model", "dev"),
            )
            .classes("w-full")
            .bind_value(self, "flux_model")
        )

        self.aspect_ratio_select = (
            ui.select(
                [
                    "1:1",
                    "16:9",
                    "21:9",
                    "3:2",
                    "2:3",
                    "4:5",
                    "5:4",
                    "3:4",
                    "4:3",
                    "9:16",
                    "9:21",
                    "custom",
                ],
                label="Aspect Ratio",
                value=self.settings.get("aspect_ratio", "1:1"),
            )
            .classes("w-full")
            .bind_value(self, "aspect_ratio")
        )
        self.aspect_ratio_select.on("change", self.toggle_custom_dimensions)

        with ui.column().classes("w-full").bind_visibility_from(
            self.aspect_ratio_select, "value", value="custom"
        ):
            self.width_input = (
                ui.number(
                    "Width", value=self.settings.get("width", 1024), min=256, max=1440
                )
                .classes("w-full")
                .bind_value(self, "width")
            )
            self.height_input = (
                ui.number(
                    "Height", value=self.settings.get("height", 1024), min=256, max=1440
                )
                .classes("w-full")
                .bind_value(self, "height")
            )

        self.num_outputs_input = (
            ui.number(
                "Num Outputs", value=self.settings.get("num_outputs", 1), min=1, max=4
            )
            .classes("w-full")
            .bind_value(self, "num_outputs")
        )
        self.lora_scale_input = (
            ui.number(
                "LoRA Scale",
                value=self.settings.get("lora_scale", 1),
                min=-1,
                max=2,
                step=0.1,
            )
            .classes("w-full")
            .bind_value(self, "lora_scale")
        )
        self.num_inference_steps_input = (
            ui.number(
                "Num Inference Steps",
                value=self.settings.get("num_inference_steps", 28),
                min=1,
                max=50,
            )
            .classes("w-full")
            .bind_value(self, "num_inference_steps")
        )
        self.guidance_scale_input = (
            ui.number(
                "Guidance Scale",
                value=self.settings.get("guidance_scale", 3.5),
                min=0,
                max=10,
                step=0.1,
            )
            .classes("w-full")
            .bind_value(self, "guidance_scale")
        )
        self.seed_input = (
            ui.number(
                "Seed",
                value=self.settings.get("seed", -1),
                min=-2147483648,
                max=2147483647,
            )
            .classes("w-full")
            .bind_value(self, "seed")
        )
        self.output_format_select = (
            ui.select(
                ["webp", "jpg", "png"],
                label="Output Format",
                value=self.settings.get("output_format", "webp"),
            )
            .classes("w-full")
            .bind_value(self, "output_format")
        )
        self.output_quality_input = (
            ui.number(
                "Output Quality",
                value=self.settings.get("output_quality", 80),
                min=0,
                max=100,
            )
            .classes("w-full")
            .bind_value(self, "output_quality")
        )
        self.disable_safety_checker_switch = (
            ui.switch(
                "Disable Safety Checker",
                value=self.settings.get("disable_safety_checker", False),
            )
            .classes("w-full")
            .bind_value(self, "disable_safety_checker")
        )

    def update_folder_path(self, e):
        new_path = e.value
        if os.path.isdir(new_path):
            self.folder_path = new_path
            self.save_settings()
            logger.info(f"Output folder set to: {self.folder_path}")
            ui.notify(f"Output folder updated to: {self.folder_path}", type="success")
        else:
            ui.notify(
                "Invalid folder path. Please enter a valid directory.", type="error"
            )
            self.folder_input.value = self.folder_path

    def setup_right_panel(self):
        self.spinner = ui.spinner(size="lg")
        self.spinner.visible = False

        # Add gallery view
        self.gallery_container = ui.column().classes("w-full mt-4")
        self.lightbox = Lightbox()

    def setup_bottom_panel(self):
        self.prompt_input = (
            ui.textarea("Prompt", value=self.settings.get("prompt", ""))
            .classes("w-full")
            .bind_value(self, "prompt")
        )
        self.token_counter = ui.label("Tokens: 0").classes("text-sm text-gray-500")
        self.prompt_input.on("input", self.update_token_count)
        self.generate_button = ui.button(
            "Generate Images", on_click=self.start_generation
        ).classes(
            "w-full bg-blue-500 hover:bg-blue-600 text-white font-bold py-2 px-4 rounded"
        )

    def select_folder(self):
        def on_folder_selected(e):
            if e.value:
                self.folder_path = e.value
                self.folder_input.value = self.folder_path
                self.save_settings()
                logger.info(f"Output folder set to: {self.folder_path}")

        ui.open_directory_dialog(on_folder_selected)

    def update_replicate_model(self, e):
        new_model = e.value
        if new_model:
            self.image_generator.set_model(new_model)
            self.save_settings()
            self.add_recent_replicate_model(new_model)
            logger.info(f"Replicate model updated to: {new_model}")
            self.generate_button.enable()
        else:
            logger.warning("Empty Replicate model provided")
            self.generate_button.disable()

    def select_recent_model(self, e):
        if e.value:
            self.replicate_model_input.value = e.value
            self.update_replicate_model(e)
            self.recent_models_select.value = None

    def add_recent_replicate_model(self, model):
        if model not in self.recent_replicate_models:
            self.recent_replicate_models.insert(0, model)
            self.recent_replicate_models = self.recent_replicate_models[
                :5
            ]  # Keep only the last 5
            self.save_settings()
            self.recent_models_select.options = self.recent_replicate_models

    def load_recent_replicate_models(self):
        return self.settings.get("recent_replicate_models", [])

    def toggle_custom_dimensions(self, e):
        if e.value == "custom":
            self.width_input.enable()
            self.height_input.enable()
        else:
            self.width_input.disable()
            self.height_input.disable()
        self.save_settings()
        logger.info(f"Custom dimensions toggled: {e.value}")

    def update_token_count(self, e):
        token_count = len(e.value.split())
        self.token_counter.text = f"Tokens: {token_count}"
        if token_count > 77:
            ui.notify("Warning: Tokens beyond 77 will be ignored", type="warning")
        self.save_settings()

    async def start_generation(self):
        if not self.replicate_model_input.value:
            ui.notify(
                "Please set a Replicate model before generating images.", type="error"
            )
            logger.warning(
                "Attempted to generate images without setting a Replicate model"
            )
            return

        # Ensure the model is set in the ImageGenerator
        self.image_generator.set_model(self.replicate_model_input.value)

        self.save_settings()
        params = {
            "prompt": self.prompt,
            "flux_model": self.flux_model,
            "aspect_ratio": self.aspect_ratio,
            "num_outputs": self.num_outputs,
            "lora_scale": self.lora_scale,
            "num_inference_steps": self.num_inference_steps,
            "guidance_scale": self.guidance_scale,
            "output_format": self.output_format,
            "output_quality": self.output_quality,
            "disable_safety_checker": self.disable_safety_checker,
        }

        if self.aspect_ratio == "custom":
            params["width"] = self.width
            params["height"] = self.height

        if self.seed != -1:
            params["seed"] = self.seed

        self.generate_button.disable()
        self.spinner.visible = True
        ui.notify("Generating images...", type="info")
        logger.info(f"Generating images with params: {json.dumps(params, indent=2)}")

        try:
            output = await asyncio.to_thread(
                self.image_generator.generate_images, params
            )
            await self.download_and_display_images(output)
            logger.success(f"Images generated successfully: {output}")
        except Exception as e:
            error_message = f"An error occurred: {str(e)}"
            ui.notify(error_message, type="error")
            logger.exception(error_message)
        finally:
            self.generate_button.enable()
            self.spinner.visible = False

    async def download_and_display_images(self, image_urls):
        downloaded_images = []
        async with httpx.AsyncClient() as client:
            for i, url in enumerate(image_urls):
                response = await client.get(url)
                if response.status_code == 200:
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    url_part = urllib.parse.urlparse(url).path.split("/")[-2][
                        :8
                    ]  # Get first 8 chars of the unique part
                    file_name = f"generated_image_{timestamp}_{url_part}_{i+1}.png"
                    file_path = Path(self.folder_path) / file_name
                    with open(file_path, "wb") as f:
                        f.write(response.content)
                    downloaded_images.append(str(file_path))
                    logger.info(f"Image downloaded: {file_path}")
                else:
                    logger.error(f"Failed to download image from {url}")

        self.update_gallery(downloaded_images)
        ui.notify("Images generated and downloaded successfully!", type="success")

    def update_gallery(self, image_paths):
        self.gallery_container.clear()
        with self.gallery_container:
            for image_path in image_paths:
                self.lightbox.add_image(image_path, image_path).classes(
                    "w-32 h-32 object-cover m-1"
                )

    def load_settings(self):
        if os.path.exists(self.settings_file):
            with open(self.settings_file, "r") as f:
                self.settings = json.load(f)
            logger.info("Settings loaded successfully")
        else:
            self.settings = {}
            logger.info("No existing settings found, using defaults")

    def save_settings(self):
        settings_to_save = {
            "replicate_model": self.replicate_model_input.value,
            "output_folder": self.folder_path,
            "flux_model": self.flux_model,
            "aspect_ratio": self.aspect_ratio,
            "width": self.width,
            "height": self.height,
            "num_outputs": self.num_outputs,
            "lora_scale": self.lora_scale,
            "num_inference_steps": self.num_inference_steps,
            "guidance_scale": self.guidance_scale,
            "seed": self.seed,
            "output_format": self.output_format,
            "output_quality": self.output_quality,
            "disable_safety_checker": self.disable_safety_checker,
            "prompt": self.prompt,
            "recent_replicate_models": self.recent_replicate_models,
        }
        with open(self.settings_file, "w") as f:
            json.dump(settings_to_save, f)
        logger.info("Settings saved successfully")


async def create_gui(image_generator):
    return ImageGeneratorGUI(image_generator)
