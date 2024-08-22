import replicate
from dotenv import load_dotenv

load_dotenv()

class ImageGenerator:
    def __init__(self):
        self.model = "rtuszik/fluxlyptus:4e304b52ad6745623fb29f3250d89df23ac38b42734887d9e0a4b3a31c648472"

    def generate_images(self, params):
        try:
            output = replicate.run(self.model, input=params)
            return output
        except Exception as e:
            raise ImageGenerationError(f"Error generating images: {str(e)}")

class ImageGenerationError(Exception):
    pass