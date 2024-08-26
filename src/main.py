import sys

from loguru import logger
from nicegui import ui

from gui import create_gui
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


logger.info("Creating and setting up GUI")


@ui.page("/")
async def main_page():
    await create_gui(generator)
    logger.info("NiceGUI server is running")


logger.info("Starting NiceGUI server")

ui.run(title="Replicate Flux LoRA", port=8080)
