import sys
from pathlib import Path

# Add src directory to Python path for absolute imports
src_path = Path(__file__).parent
sys.path.insert(0, str(src_path))

# Local imports after path modification
from loguru import logger  # noqa: E402
from nicegui import ui  # noqa: E402

from gui.imagegenerator import ImageGeneratorGUI  # noqa: E402
from util.replicate_api import Replicate_API  # noqa: E402
from util.settings import Settings  # noqa: E402

logger.add(
    sys.stderr, format="{time} {level} {message}", filter="my_module", level="INFO"
)
logger.add(
    "app.log",
    format="{time} {level} {module}:{line} {message}",
    level="INFO",
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
    logger.debug("Creating GUI")
    gui = ImageGeneratorGUI(generator)
    gui.setup_ui()
    logger.debug("GUI created")


logger.info("Starting NiceGUI server")

ui.run(title="Replicate Flux LoRA", port=8080, favicon="🚀")
