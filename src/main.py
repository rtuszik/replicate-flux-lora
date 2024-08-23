import sys

from gui import create_gui
from image_generator import ImageGenerator
from loguru import logger
from nicegui import ui

# Configure Loguru
logger.remove()  # Remove the default handler
logger.add(
    sys.stderr, format="{time} {level} {message}", filter="my_module", level="INFO"
)
logger.add(
    "main.log", rotation="10 MB", format="{time} {level} {message}", level="INFO"
)

# Create the ImageGenerator instance
logger.info("Initializing ImageGenerator")
generator = ImageGenerator()

# Create and setup the GUI
logger.info("Creating and setting up GUI")


@ui.page("/")
async def main_page():
    await create_gui(generator)
    logger.info("NiceGUI server is running")


# Run the NiceGUI server
logger.info("Starting NiceGUI server")
ui.run(port=8080)
