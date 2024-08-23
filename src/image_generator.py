import replicate
from dotenv import load_dotenv

load_dotenv()


class ImageGenerator:
    def __init__(self):
        self.model = "rtuszik/fluxlyptus:b23b9b488de7af95eba09786ef3156d345d979024712f54b3e5a32d61f14e568"

    def generate_images(self, params):
        try:
            output = replicate.run(self.model, input=params)
            return output
        except Exception as e:
            raise ImageGenerationError(f"Error generating images: {str(e)}")


class ImageGenerationError(Exception):
    pass
