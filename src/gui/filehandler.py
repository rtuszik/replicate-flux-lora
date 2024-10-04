from nicegui import ui
from datetime import datetime
import zipfile
from loguru import logger
from pathlib import Path

from gui.imagegenerator import ImageGeneratorGUI


class FileHandler:
    def create_zip_file():
        logger.debug("Creating zip file of generated images")
        if not ImageGeneratorGUI.last_generated_images:
            ui.notify("No images to download", type="warning")
            logger.warning("No images to zip")
            return None

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        zip_filename = f"generated_images_{timestamp}.zip"
        zip_path = Path(ImageGeneratorGUI.output_folder) / zip_filename

        with zipfile.ZipFile(zip_path, "w") as zipf:
            for image_path in ImageGeneratorGUI.last_generated_images:
                zipf.write(image_path, Path(image_path).name)
        logger.info(f"Zip file created: {zip_path}")
        return str(zip_path)

    def download_zip():
        logger.debug("Downloading zip file")
        zip_path = create_zip_file()
        if zip_path:
            ui.download(zip_path)
            ui.notify("Downloading zip file of generated images", type="positive")
