import asyncio
import json
import os
import sys
import urllib.parse
from datetime import datetime
from pathlib import Path

import httpx
import toml
from config import settings
from loguru import logger
from nicegui import events, ui

logger.remove()
logger.add(
    sys.stderr, format="{time} {level} {message}", filter="my_module", level="INFO"
)
logger.add("gui.log", rotation="10 MB", format="{time} {level} {message}", level="INFO")

DOCKERIZED = os.environ.get("DOCKER_CONTAINER", False)


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
        self.settings = settings
        self.user_added_models = {}

        self._attributes = [
            "prompt",
            "flux_model",
            "aspect_ratio",
            "num_outputs",
            "lora_scale",
            "num_inference_steps",
            "guidance_scale",
            "output_format",
            "output_quality",
            "disable_safety_checker",
            "width",
            "height",
            "seed",
            "output_folder",
            "replicate_model",
        ]

        # Initialize attributes
        for attr in self._attributes:
            setattr(self, attr, None)

        self.load_settings()

        if not self.output_folder:
            self.output_folder = (
                str(Path.home() / "Downloads") if not DOCKERIZED else "/app/output"
            )

        self.setup_ui()
        logger.info("ImageGeneratorGUI initialized")

    def setup_ui(self):
        ui.dark_mode().enable()

        with ui.grid(columns=2).classes("w-screen h-full gap-4 px-8"):
            with ui.card().classes("col-span-2"):
                ui.label("Flux LoRA API").classes("text-2xl font-bold mb-4")

            with ui.card().classes("h-[70vh] overflow-auto"):
                self.setup_left_panel()

            with ui.card().classes("h-[70vh] overflow-auto"):
                self.setup_right_panel()

            with ui.card().classes("col-span-2"):
                self.setup_bottom_panel()

        logger.info("UI setup completed")

    def setup_left_panel(self):
        with ui.row().classes("w-full"):
            self.replicate_model_select = (
                ui.select(
                    options=self.model_options,
                    label="Replicate Model",
                    value=self.replicate_model,
                    on_change=self.update_replicate_model,
                )
                .classes("w-5/6")
                .tooltip("Select or manage Replicate models")
            )
            ui.button(icon="add").classes("w-1/6").on(
                "click", self.open_user_model_popup
            )

        self.folder_input = ui.input(
            label="Output Folder", value=self.output_folder
        ).classes("w-full")
        self.folder_input.on("change", self.update_folder_path)

        self.flux_model_select = (
            ui.select(
                ["dev", "schnell"],
                label="Flux Model",
                value=self.settings.get("flux_model", "dev"),
            )
            .classes("w-full")
            .tooltip(
                "Which model to run inferences with. The dev model needs around 28 steps but the schnell model only needs around 4 steps."
            )
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
            .tooltip(
                "Width of the generated image. Optional, only used when aspect_ratio=custom. Must be a multiple of 16 (if it's not, it will be rounded to nearest multiple of 16)"
            )
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
                .tooltip(
                    "Width of the generated image. Optional, only used when aspect_ratio=custom. Must be a multiple of 16 (if it's not, it will be rounded to nearest multiple of 16)"
                )
            )
            self.height_input = (
                ui.number(
                    "Height", value=self.settings.get("height", 1024), min=256, max=1440
                )
                .classes("w-full")
                .bind_value(self, "height")
                .tooltip(
                    "Height of the generated image. Optional, only used when aspect_ratio=custom. Must be a multiple of 16 (if it's not, it will be rounded to nearest multiple of 16)"
                )
            )

        self.num_outputs_input = (
            ui.number(
                "Num Outputs", value=self.settings.get("num_outputs", 1), min=1, max=4
            )
            .classes("w-full")
            .bind_value(self, "num_outputs")
            .tooltip("Number of images to output.")
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
            .tooltip(
                "Determines how strongly the LoRA should be applied. Sane results between 0 and 1."
            )
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
            .tooltip("Number of Inference Steps")
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
            .tooltip("Guidance Scale for the diffusion process")
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
            .tooltip("Format of the output images")
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
            .tooltip(
                "Quality when saving the output images, from 0 to 100. 100 is best quality, 0 is lowest quality. Not relevant for .png outputs"
            )
            .bind_value(self, "output_quality")
        )
        self.disable_safety_checker_switch = (
            ui.switch(
                "Disable Safety Checker",
                value=self.settings.get("disable_safety_checker", True),
            )
            .classes("w-full")
            .tooltip("Disable safety checker for generated images.")
            .bind_value(self, "disable_safety_checker")
        )
        self.reset_button = ui.button(
            "Reset to Default", on_click=self.reset_to_default
        ).classes(
            "w-1/2 bg-gray-500 hover:bg-gray-600 text-white font-bold py-2 px-4 rounded"
        )

    def setup_right_panel(self):
        self.spinner = ui.spinner(type="infinity", size="150px")
        self.spinner.visible = False

        self.gallery_container = ui.column().classes("w-full mt-4")
        self.lightbox = Lightbox()

    def setup_bottom_panel(self):
        self.prompt_input = (
            ui.textarea("Prompt", value=self.settings.get("prompt", ""))
            .classes("w-full")
            .bind_value(self, "prompt")
            .props("clearable")
        )
        self.generate_button = ui.button(
            "Generate Images", on_click=self.start_generation
        ).classes(
            "w-full bg-blue-500 hover:bg-blue-600 text-white font-bold py-2 px-4 rounded"
        )

    async def open_user_model_popup(self):
        with ui.dialog() as dialog, ui.card():
            ui.label("Manage Replicate Models").classes("text-xl font-bold mb-4")
            new_model_input = ui.input(label="Add New Model").classes("w-full mb-4")
            ui.button(
                "Add Model",
                on_click=lambda: self.add_user_model(new_model_input.value, dialog),
            )

            ui.label("Current Models:").classes("mt-4 mb-2")
            with ui.column().classes("w-full"):
                for model in self.user_added_models:
                    with ui.row().classes("w-full justify-between items-center"):
                        ui.label(model)
                        ui.button(
                            icon="delete",
                            on_click=lambda m=model: self.confirm_delete_model(
                                m, dialog
                            ),
                        ).props("flat round color=red")

            ui.button("Close", on_click=dialog.close).classes("mt-4")
        dialog.open()

    async def add_user_model(self, new_model, dialog):
        if new_model and new_model not in self.user_added_models:
            self.user_added_models[new_model] = new_model
            self.model_options = list(self.user_added_models.keys())
            self.replicate_model_select.options = self.model_options
            self.replicate_model_select.value = new_model
            await self.update_replicate_model(
                events.ValueChangeEventArguments(
                    sender=self.replicate_model_select,
                    value=new_model,
                    client=ui.client,
                )
            )
            await asyncio.to_thread(self.save_settings)
            ui.notify(f"Model '{new_model}' added successfully", type="positive")
            dialog.close()
        else:
            ui.notify("Invalid model name or model already exists", type="negative")

    async def confirm_delete_model(self, model, parent_dialog):
        with ui.dialog() as confirm_dialog, ui.card():
            ui.label(f"Are you sure you want to delete the model '{model}'?").classes(
                "mb-4"
            )
            with ui.row():
                ui.button(
                    "Yes",
                    on_click=lambda: self.delete_user_model(
                        model, parent_dialog, confirm_dialog
                    ),
                ).classes("mr-2")
                ui.button("No", on_click=confirm_dialog.close)
        confirm_dialog.open()

    async def delete_user_model(self, model, parent_dialog, confirm_dialog):
        if model in self.user_added_models:
            del self.user_added_models[model]
            self.model_options = list(self.user_added_models.keys())
            self.replicate_model_select.options = self.model_options
            if self.replicate_model_select.value == model:
                self.replicate_model_select.value = None
                await self.update_replicate_model(
                    events.ValueChangeEventArguments(
                        sender=self.replicate_model_select, value=None, client=ui.client
                    )
                )
            await asyncio.to_thread(self.save_settings)
            ui.notify(f"Model '{model}' deleted successfully", type="positive")
            confirm_dialog.close()
            parent_dialog.close()
        else:
            ui.notify("Cannot delete this model", type="negative")

    async def update_replicate_model(self, e):
        new_model = e.value
        if new_model:
            await asyncio.to_thread(self.image_generator.set_model, new_model)
            self.replicate_model = new_model
            await asyncio.to_thread(self.save_settings)
            logger.info(f"Replicate model updated to: {new_model}")
            self.generate_button.enable()
        else:
            logger.warning("No Replicate model selected")
            self.generate_button.disable()

    async def update_folder_path(self, e):
        new_path = e.value
        if os.path.isdir(new_path):
            self.output_folder = new_path
            await asyncio.to_thread(self.save_settings)
            logger.info(f"Output folder set to: {self.output_folder}")
            ui.notify(
                f"Output folder updated to: {self.output_folder}", type="positive"
            )
        else:
            ui.notify(
                "Invalid folder path. Please enter a valid directory.", type="negative"
            )
            self.folder_input.value = self.output_folder

    async def toggle_custom_dimensions(self, e):
        if e.value == "custom":
            self.width_input.enable()
            self.height_input.enable()
        else:
            self.width_input.disable()
            self.height_input.disable()
        await asyncio.to_thread(self.save_settings)
        logger.info(f"Custom dimensions toggled: {e.value}")

    async def reset_to_default(self):
        with open("settings.toml", "r") as f:
            default_settings = toml.load(f)["default"]

        for attr in self._attributes:
            if attr in default_settings:
                value = default_settings[attr]
                setattr(self, attr, value)
                if hasattr(self, f"{attr}_input"):
                    getattr(self, f"{attr}_input").value = value
                elif hasattr(self, f"{attr}_select"):
                    getattr(self, f"{attr}_select").value = value
                elif hasattr(self, f"{attr}_switch"):
                    getattr(self, f"{attr}_switch").value = value

        self.user_added_models = {}
        await asyncio.to_thread(self.save_settings)
        ui.notify("Settings reset to default values", type="info")
        logger.info("Settings reset to default values")

    async def start_generation(self):
        if not self.replicate_model_select.value:
            ui.notify(
                "Please select a Replicate model before generating images.",
                type="negative",
            )
            logger.warning(
                "Attempted to generate images without selecting a Replicate model"
            )
            return

        await asyncio.to_thread(
            self.image_generator.set_model, self.replicate_model_select.value
        )

        await asyncio.to_thread(self.save_settings)
        params = {
            "prompt": self.prompt_input.value,
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
            ui.notify(error_message, type="negative")
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
                    url_part = urllib.parse.urlparse(url).path.split("/")[-2][:8]
                    file_name = f"generated_image_{timestamp}_{url_part}_{i+1}.png"
                    file_path = Path(self.output_folder) / file_name
                    with open(file_path, "wb") as f:
                        f.write(response.content)
                    downloaded_images.append(str(file_path))
                    logger.info(f"Image downloaded: {file_path}")
                else:
                    logger.error(f"Failed to download image from {url}")

        self.update_gallery(downloaded_images)
        ui.notify("Images generated and downloaded successfully!", type="positive")

    def update_gallery(self, image_paths):
        self.gallery_container.clear()
        with self.gallery_container:
            for image_path in image_paths:
                self.lightbox.add_image(image_path, image_path).classes(
                    "w-32 h-32 object-cover m-1"
                )

    def load_settings(self):
        with open("settings.toml", "r") as f:
            default_settings = toml.load(f)["default"]

        local_settings = {}
        if os.path.exists("settings.local.toml"):
            with open("settings.local.toml", "r") as f:
                local_settings = toml.load(f).get("default", {})

        for attr in self._attributes:
            setattr(self, attr, local_settings.get(attr, default_settings.get(attr)))

        models = local_settings.get("models", default_settings.get("models", {}))
        self.user_added_models = {
            model: model for model in models.get("user_added", [])
        }

        self.model_options = list(self.user_added_models.keys())
        self.replicate_model = local_settings.get("replicate_model", "")

    def save_settings(self):
        settings_dict = {}
        for attr in self._attributes:
            settings_dict[attr] = getattr(self, attr)

        settings_dict["models"] = {"user_added": list(self.user_added_models.keys())}
        settings_dict["replicate_model"] = self.replicate_model_select.value

        with open("settings.local.toml", "w") as f:
            toml.dump({"default": settings_dict}, f)

        logger.info("Settings saved successfully")


async def create_gui(image_generator):
    return ImageGeneratorGUI(image_generator)
