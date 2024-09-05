import asyncio
import json
import os
import sys
import urllib.parse
import zipfile
from datetime import datetime
from pathlib import Path

import httpx
import toml
from config import get_api_key, settings
from dynaconf import loaders
from loguru import logger
from nicegui import ui

logger.remove()
logger.add(
    sys.stderr, format="{time} {level} {message}", filter="my_module", level="INFO"
)
logger.add("gui.log", rotation="10 MB", format="{time} {level} {message}", level="INFO")

DOCKERIZED = os.environ.get("DOCKER_CONTAINER", False)

SETTINGS_LOCAL_FILE = "settings.local.toml"


class Lightbox:
    def __init__(self):
        with ui.dialog().props("maximized").classes("bg-black") as self.dialog:
            self.dialog.on_key = self._handle_key
            self.large_image = ui.image().props("no-spinner fit=scale-down")
        self.image_list = []

    def add_image(
        self,
        thumb_url: str,
        orig_url: str,
        thumb_classes: str = "w-32 h-32 object-cover",
    ) -> ui.button:
        self.image_list.append(orig_url)
        button = ui.button(on_click=lambda: self._open(orig_url)).props(
            "flat dense square"
        )
        with button:
            ui.image(thumb_url).classes(thumb_classes)
        return button

    def _handle_key(self, e) -> None:
        if not e.action.keydown:
            return
        if e.key.escape:
            self.dialog.close()
        image_index = self.image_list.index(self.large_image.source)
        if e.key.arrow_left and image_index > 0:
            self._open(self.image_list[image_index - 1])
        if e.key.arrow_right and image_index < len(self.image_list) - 1:
            self._open(self.image_list[image_index + 1])

    def _open(self, url: str) -> None:
        self.large_image.set_source(url)
        self.dialog.open()


class ImageGeneratorGUI:
    def __init__(self, image_generator):
        self.image_generator = image_generator
        self.settings = settings
        self.user_added_models = {}
        self.api_key = get_api_key() or os.environ.get("REPLICATE_API_KEY", "")
        self.last_generated_images = []
        self.setup_custom_styles()
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

        for attr in self._attributes:
            setattr(self, attr, None)

        self.load_settings()

        if not self.output_folder:
            self.output_folder = (
                str(Path.home() / "Downloads") if not DOCKERIZED else "/app/output"
            )

        logger.info("ImageGeneratorGUI initialized")

    def setup_custom_styles(self):
        ui.add_head_html("""
            <link href="https://fonts.googleapis.com/css2?family=Roboto+Mono:ital,wght@0,100..700;1,100..700&display=swap" rel="stylesheet">
            <style>
                body, .q-field__native, .q-btn__content, .q-item__label {
                    font-family: 'Roboto Mono', sans-serif !important;
                }
                .modern-card {
                    border-radius: 15px;
                    box-shadow: 10px 10px 5px rgba(0, 0, 0, 0.1);
                    transition: all 0.3s ease;
                }
                .modern-card:hover {
                    transform: translateY(-2px);
                    box-shadow: 10px 10px 5px rgba(0, 0, 0, 0.15);
                }
                .modern-button {
                    border-radius: 8px;
                    text-transform: uppercase;
                    font-weight: 600;
                    letter-spacing: 0.5px;
                }
                @keyframes pulse {
                    0%, 100% {
                        opacity: 1;
                    }
                    50% {
                        opacity: .5;
                    }
                }
                }
            </style>
        """)

    def setup_ui(self):
        ui.dark_mode()
        self.check_api_key()

        with ui.grid().classes(
            "w-full h-screen md:h-full grid-cols-1 md:grid-cols-2 gap-2 md:gap-5 p-4 md:p-6 dark:bg-[#1f2328] bg-[#ffffff] md:auto-rows-min"
        ):
            with ui.card().classes(
                "col-span-full modern-card dark:bg-[#25292e] bg-[#818b981f] flex-nowrap h-min"
            ):
                self.setup_top_panel()

            with ui.card().classes(
                "col-span-full modern-card dark:bg-[#25292e] bg-[#818b981f]"
            ):
                self.setup_prompt_panel()

            with ui.card().classes(
                "row-span-2 overflow-auto modern-card dark:bg-[#25292e] bg-[#818b981f]"
            ):
                self.setup_left_panel()

            with ui.card().classes(
                "row-span-2 overflow-auto modern-card dark:bg-[#25292e] bg-[#818b981f]"
            ):
                self.setup_right_panel()

        logger.info("UI setup completed")

    def setup_top_panel(self):
        with ui.row().classes("w-full items-center"):
            ui.label("Lumberjack - Replicate API Interface").classes(
                "text-2xl/loose font-bold"
            )
            dark_mode = ui.dark_mode(True)
            ui.switch().bind_value(dark_mode).classes().props(
                "dense checked-icon=dark_mode unchecked-icon=light_mode color=blue-7"
            )
            ui.button(
                icon="settings_suggest",
                on_click=self.open_settings_popup,
                color="#0969da",
            ).classes("absolute-right mr-6 mt-3 mb-3")

    def setup_left_panel(self):
        with ui.row().classes("w-full flex-row flex-nowrap"):
            self.replicate_model_select = (
                ui.select(
                    options=self.model_options,
                    label="Replicate Model",
                    value=self.replicate_model,
                    on_change=lambda e: asyncio.create_task(
                        self.update_replicate_model(e.value)
                    ),
                )
                .classes("width-5/6 overflow-auto custom-select")
                .tooltip("Select or manage Replicate models")
                .props("filled")
            )
            ui.button(icon="token", color="#0969da").classes("ml-2 mt-1.2").on(
                "click", self.open_user_model_popup
            ).props("size=1.3rem")

        self.flux_model_select = (
            ui.select(
                ["dev", "schnell"],
                label="Flux Model",
                value=self.settings.get("flux_model", "dev"),
            )
            .classes("w-full text-gray-200")
            .tooltip(
                "Which model to run inferences with. The dev model needs around 28 steps but the schnell model only needs around 4 steps."
            )
            .bind_value(self, "flux_model")
            .props("filled")
        )

        with ui.row().classes("w-full flex-nowrap md:flex-wrap"):
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
                .classes("w-1/2 md:w-full text-gray-200")
                .bind_value(self, "aspect_ratio")
                .tooltip(
                    "Width of the generated image. Optional, only used when aspect_ratio=custom. Must be a multiple of 16 (if it's not, it will be rounded to nearest multiple of 16)"
                )
                .props("filled")
            )
            self.aspect_ratio_select.on("change", self.toggle_custom_dimensions)

            with ui.column().classes("w-full").bind_visibility_from(
                self.aspect_ratio_select, "value", value="custom"
            ):
                self.width_input = (
                    ui.number(
                        "Width",
                        value=self.settings.get("width", 1024),
                        min=256,
                        max=1440,
                    )
                    .classes("w-full")
                    .bind_value(self, "width")
                    .tooltip(
                        "Width of the generated image. Optional, only used when aspect_ratio=custom. Must be a multiple of 16 (if it's not, it will be rounded to nearest multiple of 16)"
                    )
                )
                self.height_input = (
                    ui.number(
                        "Height",
                        value=self.settings.get("height", 1024),
                        min=256,
                        max=1440,
                    )
                    .classes("w-full")
                    .bind_value(self, "height")
                    .tooltip(
                        "Height of the generated image. Optional, only used when aspect_ratio=custom. Must be a multiple of 16 (if it's not, it will be rounded to nearest multiple of 16)"
                    )
                )

            self.num_outputs_input = (
                ui.number(
                    "Num Outputs",
                    value=self.settings.get("num_outputs", 1),
                    min=1,
                    max=4,
                )
                .classes("w-1/2 md:w-full")
                .bind_value(self, "num_outputs")
                .tooltip("Number of images to output.")
                .props("filled")
            )

        with ui.row().classes("w-full flex-nowrap md:flex-wrap"):
            self.lora_scale_input = (
                ui.number(
                    "LoRA Scale",
                    value=self.settings.get("lora_scale", 1),
                    min=-1,
                    max=2,
                    step=0.1,
                )
                .classes("w-1/2 md:w-full")
                .tooltip(
                    "Determines how strongly the LoRA should be applied. Sane results between 0 and 1."
                )
                .props("filled")
                .bind_value(self, "lora_scale")
            )
            self.num_inference_steps_input = (
                ui.number(
                    "Num Inference Steps",
                    value=self.settings.get("num_inference_steps", 28),
                    min=1,
                    max=50,
                )
                .classes("w-1/2 md:w-full")
                .tooltip("Number of Inference Steps")
                .bind_value(self, "num_inference_steps")
                .props("filled")
            )

        with ui.row().classes("w-full flex-nowrap md:flex-wrap"):
            self.guidance_scale_input = (
                ui.number(
                    "Guidance Scale",
                    value=self.settings.get("guidance_scale", 3.5),
                    min=0,
                    max=10,
                    step=0.1,
                    precision=2,
                )
                .classes("w-1/2 md:w-full")
                .tooltip("Guidance Scale for the diffusion process")
                .bind_value(self, "guidance_scale")
                .props("filled")
            )
            self.seed_input = (
                ui.number(
                    "Seed",
                    value=self.settings.get("seed", -1),
                    min=-2147483648,
                    max=2147483647,
                )
                .classes("w-1/2 md:w-full")
                .bind_value(self, "seed")
                .props("filled")
            )

        with ui.row().classes("w-full flex-nowrap"):
            self.output_format_select = (
                ui.select(
                    ["webp", "jpg", "png"],
                    label="Output Format",
                    value=self.settings.get("output_format", "webp"),
                )
                .classes("w-full")
                .tooltip("Format of the output images")
                .bind_value(self, "output_format")
                .props("filled")
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
                .props("filled")
            )

        with ui.row().classes("w-full flex-nowrap"):
            self.disable_safety_checker_switch = (
                ui.switch(
                    "Disable Safety Checker",
                    value=self.settings.get("disable_safety_checker", True),
                )
                .classes("w-1/2")
                .tooltip("Disable safety checker for generated images.")
                .bind_value(self, "disable_safety_checker")
                .props("filled color=blue-8")
            )
            self.reset_button = ui.button(
                "Reset Parameters", on_click=self.reset_to_default, color="#cf222e"
            ).classes("w-1/2 text-white font-bold py-2 px-4 rounded")

    def setup_right_panel(self):
        with ui.row().classes("w-full flex-nowrap"):
            ui.label("Output").classes("text-center ml-4 mt-3 w-full").style(
                "font-size: 230%; font-weight: bold; text-align: left;"
            )
            ui.button(
                "Download Images", on_click=self.download_zip, color="#0969da"
            ).classes("modern-button text-white font-bold py-2 px-4 rounded")
        ui.separator()
        with ui.row().classes("w-full flex-nowrap"):
            self.gallery_container = ui.column().classes(
                "w-full mt-4 grid grid-cols-2 gap-4"
            )
            self.lightbox = Lightbox()

    def setup_prompt_panel(self):
        with ui.row().classes("w-full flex-row flex-nowrap"):
            self.prompt_input = (
                ui.textarea("Prompt", value=self.settings.get("prompt", ""))
                .classes("w-full text-gray-200 shadow-lg")
                .bind_value(self, "prompt")
                .props("clearable filled autofocus")
            )
            self.generate_button = (
                ui.button(icon="bolt", on_click=self.start_generation, color="#0969da")
                .classes("ml-2 font-bold rounded modern-button h-full")
                .props("size=1.5rem")
                .style("animation: pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite;")
            )
        self.progress = (
            ui.linear_progress(show_value=False, size="20px")
            .classes("w-full")
            .props("indeterminate")
        )
        self.progress.visible = False

    async def open_settings_popup(self):
        with ui.dialog() as dialog, ui.card().classes(
            "w-2/3 modern-card dark:bg-[#25292e] bg-[#818b981f]"
        ):
            ui.label("Settings").classes("text-2xl font-bold")
            api_key_input = ui.input(
                label="API Key",
                placeholder="Enter Replicate API Key...",
                password=True,
                value=self.api_key,
            ).classes("w-full mb-4")

            async def save_settings():
                new_api_key = api_key_input.value
                if new_api_key != self.api_key:
                    self.api_key = new_api_key
                    await self.save_api_key()
                dialog.close()
                ui.notify("Settings saved successfully", type="positive")

            if not DOCKERIZED:
                self.folder_input = ui.input(
                    label="Output Folder", value=self.output_folder
                ).classes("w-full mb-4")
                self.folder_input.on("change", self.update_folder_path)
                ui.button(
                    "Save Settings", on_click=save_settings, color="#818b981f"
                ).classes("mt-4")
        dialog.open()

    async def save_api_key(self):
        settings.set("REPLICATE_API_KEY", self.api_key)

        secrets_dict = {"default": {"REPLICATE_API_KEY": self.api_key}}

        loaders.write(".secrets.toml", secrets_dict)

        os.environ["REPLICATE_API_KEY"] = self.api_key

        self.image_generator.set_api_key(self.api_key)

    @ui.refreshable
    def model_list(self):
        for model in self.user_added_models:
            with ui.row().classes("w-full justify-between items-center"):
                ui.label(model)
                ui.button(
                    icon="delete",
                    on_click=lambda m=model: self.confirm_delete_model(m),
                    color="#818b981f",
                ).props("flat round color=red")

    async def open_user_model_popup(self):
        async def add_model():
            await self.add_user_model(new_model_input.value)

        with ui.dialog() as dialog, ui.card():
            ui.label("Manage Replicate Models").classes("text-xl font-bold mb-4")
            new_model_input = ui.input(label="Add New Model").classes("w-full mb-4")
            ui.button("Add Model", on_click=add_model, color="#818b981f")

            ui.label("Current Models:").classes("mt-4 mb-2")
            self.model_list()

            ui.button("Close", on_click=dialog.close, color="#818b981f").classes("mt-4")
        dialog.open()

    async def add_user_model(self, new_model):
        if new_model and new_model not in self.user_added_models:
            self.user_added_models[new_model] = new_model
            self.model_options = list(self.user_added_models.keys())
            self.replicate_model_select.options = self.model_options
            self.replicate_model_select.value = new_model
            await self.update_replicate_model(new_model)
            await self.save_settings()
            ui.notify(f"Model '{new_model}' added successfully", type="positive")
            self.model_list.refresh()
        else:
            ui.notify("Invalid model name or model already exists", type="negative")

    async def confirm_delete_model(self, model):
        async def delete_model():
            await self.delete_user_model(model, confirm_dialog)

        with ui.dialog() as confirm_dialog, ui.card():
            ui.label(f"Are you sure you want to delete the model '{model}'?").classes(
                "mb-4"
            )
            with ui.row():
                ui.button("Yes", on_click=delete_model, color="1f883d").classes("mr-2")
                ui.button("No", on_click=confirm_dialog.close, color="cf222e")
        confirm_dialog.open()

    async def delete_user_model(self, model, confirm_dialog):
        if model in self.user_added_models:
            del self.user_added_models[model]
            self.model_options = list(self.user_added_models.keys())
            self.replicate_model_select.options = self.model_options
            if self.replicate_model_select.value == model:
                self.replicate_model_select.value = None
                await self.update_replicate_model(None)
            await self.save_settings()
            ui.notify(f"Model '{model}' deleted successfully", type="positive")
            confirm_dialog.close()
            self.model_list.refresh()
        else:
            ui.notify("Cannot delete this model", type="negative")

    async def update_replicate_model(self, new_model):
        if new_model:
            await asyncio.to_thread(self.image_generator.set_model, new_model)
            self.replicate_model = new_model
            await self.save_settings()
            logger.info(f"Replicate model updated to: {new_model}")
            self.generate_button.enable()
        else:
            logger.warning("No Replicate model selected")
            self.generate_button.disable()

    async def update_folder_path(self, e):
        new_path = e.value
        if os.path.isdir(new_path):
            self.output_folder = new_path
            await self.save_settings()
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
        await self.save_settings()
        logger.info(f"Custom dimensions toggled: {e.value}")

    def check_api_key(self):
        if not self.api_key:
            ui.notify(
                "No Replicate API Key found. Please set it in the settings before generating images.",
                type="warning",
                close_button="OK",
                timeout=10000,  # 10 seconds
                position="top",
            )

    async def reset_to_default(self):
        with open("settings.toml", "r") as f:
            default_settings = toml.load(f)["default"]

        for attr in self._attributes:
            if attr in default_settings and attr not in ["models", "replicate_model"]:
                value = default_settings[attr]
                setattr(self, attr, value)
                if hasattr(self, f"{attr}_input"):
                    getattr(self, f"{attr}_input").value = value
                elif hasattr(self, f"{attr}_select"):
                    getattr(self, f"{attr}_select").value = value
                elif hasattr(self, f"{attr}_switch"):
                    getattr(self, f"{attr}_switch").value = value

        await self.save_settings()
        ui.notify("Parameters reset to default values", type="info")
        logger.info("Parameters reset to default values")

    async def start_generation(self):
        if not self.api_key:
            ui.notify(
                "Please set your Replicate API Key in the settings.", type="negative"
            )
            return
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

        await self.save_settings()
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
        self.progress.visible = True
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
            self.progress.visible = False

    def create_zip_file(self):
        if not self.last_generated_images:
            ui.notify("No images to download", type="warning")
            return None

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        zip_filename = f"generated_images_{timestamp}.zip"
        zip_path = Path(self.output_folder) / zip_filename

        with zipfile.ZipFile(zip_path, "w") as zipf:
            for image_path in self.last_generated_images:
                zipf.write(image_path, Path(image_path).name)

        return str(zip_path)

    def download_zip(self):
        zip_path = self.create_zip_file()
        if zip_path:
            ui.download(zip_path)
            ui.notify("Downloading zip file of generated images", type="positive")

    async def update_gallery(self, image_paths):
        self.gallery_container.clear()
        self.last_generated_images = image_paths
        with self.gallery_container:
            with ui.row().classes("w-full"):
                with ui.grid(columns=2).classes("md:grid-cols-3 w-full gap-2"):
                    for image_path in image_paths:
                        self.lightbox.add_image(
                            image_path, image_path, "w-full h-full object-cover"
                        )

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

        await self.update_gallery(downloaded_images)
        ui.notify("Images generated and downloaded successfully!", type="positive")

    def load_settings(self):
        with open("settings.toml", "r") as f:
            default_settings = toml.load(f)["default"]

        local_settings = {}
        if os.path.exists(SETTINGS_LOCAL_FILE):
            with open(SETTINGS_LOCAL_FILE, "r") as f:
                local_settings = toml.load(f).get("default", {})

        for attr in self._attributes:
            setattr(self, attr, local_settings.get(attr, default_settings.get(attr)))

        models = local_settings.get("models", default_settings.get("models", {}))
        self.user_added_models = {
            model: model for model in models.get("user_added", [])
        }

        self.model_options = list(self.user_added_models.keys())
        self.replicate_model = local_settings.get("replicate_model", "")

    async def save_settings(self):
        settings_dict = {}
        for attr in self._attributes:
            settings_dict[attr] = getattr(self, attr)

        settings_dict["models"] = {"user_added": list(self.user_added_models.keys())}
        settings_dict["replicate_model"] = self.replicate_model_select.value

        with open(SETTINGS_LOCAL_FILE, "w") as f:
            toml.dump({"default": settings_dict}, f)

        logger.info("Settings saved successfully")


async def create_gui(image_generator):
    gui = ImageGeneratorGUI(image_generator)
    gui.setup_ui()
    return gui
