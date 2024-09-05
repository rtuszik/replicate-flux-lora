import sys

from config import get_api_key
from gui import create_gui
from loguru import logger
from nicegui import ui
from replicate_api import ImageGenerator

logger.remove()
logger.add(
    sys.stderr, format="{time} {level} {message}", filter="my_module", level="INFO"
)
logger.add(
    "main.log", rotation="10 MB", format="{time} {level} {message}", level="INFO"
)


logger.info("Initializing ImageGenerator")
generator = ImageGenerator()


api_key = get_api_key()
if api_key:
    generator.set_api_key(api_key)
else:
    logger.warning("No Replicate API Key found. Please set it in the settings.")

logger.info("Creating and setting up GUI")


@ui.page("/")
async def main_page():
    await create_gui(generator)
    logger.info("NiceGUI server is running")


logger.info("Starting NiceGUI server")

ui.run(title="Replicate Flux LoRA", port=8080, favicon="🚀")





