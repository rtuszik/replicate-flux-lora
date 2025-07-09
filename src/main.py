import sys
from pathlib import Path

# Add src directory to Python path for absolute imports
src_path = Path(__file__).parent
sys.path.insert(0, str(src_path))

# Local imports after path modification
from loguru import logger  # noqa: E402
from nicegui import ui  # noqa: E402

from gui.universal_generator import UniversalReplicateGUI  # noqa: E402
from util.replicate_api import Replicate_API  # noqa: E402
from util.settings import Settings  # noqa: E402

logger.add(
    sys.stderr, format="{time} {level} {message}", filter="my_module", level="DEBUG"
)
logger.add(
    "app.log",
    format="{time} {level} {module}:{line} {message}",
    level="DEBUG",
    rotation="500 MB",
    compression="zip",
)


logger.info("Initializing ImageGenerator")
generator = Replicate_API()

api_key = Settings.get_api_key()
if api_key:
    generator.set_api_key(api_key)
else:
    logger.warning("No Replicate API Key found. Please set it in the settings.")

logger.info("Creating and setting up GUI")


@ui.page("/")
async def main_page():
    try:
        logger.debug("Creating Universal GUI")
        gui = UniversalReplicateGUI(generator)
        gui.setup_ui()
        logger.debug("Universal GUI created")
    except Exception as e:
        logger.exception(f"Error creating GUI: {e}")
        ui.label(f"Error loading GUI: {e}")
        raise


logger.info("Starting NiceGUI server")

# Add static file serving for images
from nicegui import app
import os
output_dir = os.path.abspath("./replicate_outputs")
if os.path.exists(output_dir):
    app.add_static_files("/outputs", output_dir)
    logger.info(f"Added static file serving for {output_dir}")

ui.run(title="Universal Replicate Interface", port=8080, favicon="🚀")
