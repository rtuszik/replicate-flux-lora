# Flux Replicate GUI

This application provides a user-friendly web interface for running Flux1 models using the Replicate API. It's designed specifically for users who want to utilize LoRAs (Low-Rank Adaptations) of Flux created with the [ostris/flux-dev-lora-trainer](https://replicate.com/ostris/flux-dev-lora-trainer/train).

## Features

- Web-based GUI for easy interaction with Flux1 LoRAs
- Integration with Replicate API for model execution
- Support for custom LoRAs trained with flux-dev-lora-trainer
- Ability to disable the Safety Checker (API-exclusive feature)
- Customizable image generation parameters
- Image gallery for viewing generated images
- Settings persistence for a smoother user experience

## Prerequisites

- Python 3.7+
- Replicate API key

## Installation

1. Clone this repository:
   ```
   git clone https://github.com/yourusername/flux-replicate-gui.git
   cd flux-replicate-gui
   ```

2. Install the required dependencies:
   ```
   pip install -r requirements.txt
   ```

3. Set up your Replicate API key as an environment variable:
   ```
   export REPLICATE_API_TOKEN=your_api_key_here
   ```

## Usage

1. Run the application:
   ```
   python3 main.py
   ```

2. Open your web browser and navigate to `http://localhost:8080`

3. In the GUI:
   - Enter your Replicate model URL
   - Set your desired parameters (aspect ratio, number of outputs, etc.)
   - Enter your prompt
   - Click "Generate Images"

4. View your generated images in the gallery

## Key Components

- `main.py`: Entry point of the application
- `gui.py`: Defines the web interface using NiceGUI
- `image_generator.py`: Handles image generation using the Replicate API
- `utils.py`: Contains utility classes and functions

## Customization

You can modify various parameters in the GUI, including:

- Flux model selection (dev or schnell)
- Aspect ratio
- Number of outputs
- LoRA scale
- Number of inference steps
- Guidance scale
- Output format and quality
- Safety checker toggle

## Training Your Own Models

To train your own models for use with this GUI, please refer to the Replicate guide on fine-tuning Flux:

[Fine-tune Flux: Create your own image generation model](https://replicate.com/blog/fine-tune-flux)

## License

[GNU GPLv3e](LICENSE)
