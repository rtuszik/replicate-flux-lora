# Image Generator GUI

## Overview
The Image Generator GUI is a Python application that provides a user-friendly interface for generating images using the [LucaTaco Flux-Dev LoRA explorer](https://replicate.com/lucataco/flux-dev-lora/readme) via Replicate. This tool allows users to input prompts, adjust various parameters, and generate high-quality images with ease.

## Features
- Intuitive graphical user interface
- Real-time token counting with warnings for exceeding token limits
- Customizable image generation parameters:
  - Aspect ratio
  - Number of outputs
  - Inference steps
  - Guidance scale
  - Seed
  - Output format and quality
- Support for custom LoRA models
- Image preview with full-size viewing capability
- Option to automatically save generated images
- Persistent settings between sessions
- Toggle between grid and list view for generated images
- Ability to interrupt ongoing image generation

## Installation

1. Clone this repository:
   ```
   git clone https://github.com/rtuszik/flux-dev-lora-python.git
   cd flux-dev-lora-python
   ```

2. Install the required dependencies:
   ```
   pip install -r requirements.txt
   ```

3. Set up your Replicate API key:
   - Create a `.env` file in the project root
   - Add your Replicate API key: `REPLICATE_API_TOKEN=your_api_key_here`

## Usage

1. Run the application:
   ```
   python3 FluxLoraGUI.py
   ```

2. Enter your prompt in the text box.
3. Adjust the generation parameters as desired.
4. Click "Generate Images" to create your images.
5. Click on the generated thumbnails to view them in full size.
6. Use the "Toggle View" button to switch between grid and list views of the gallery.
7. The "Interrupt Generation" button allows you to stop the image generation process if needed.

## About the Replicate Model

This application uses the Flux-Dev LoRA model implemented via Huggingface Diffusers. Key points about the model:

- Supports various LoRAs, including Dreambooth and Style LoRAs.
- Allows use of custom LoRAs by providing a Huggingface path or URL.

## Contributing

Contributions to improve the Image Generator GUI are welcome. Please feel free to submit pull requests or open issues for bugs and feature requests.

## Troubleshooting

If you encounter any issues:
1. Ensure your Replicate API key is correctly set in the `.env` file.
2. Check that all dependencies are installed correctly.
3. Verify that you have a stable internet connection.

For persistent problems, please open an issue on the GitHub repository.

---

For more information on training LoRAs or using the Flux model, please refer to the [official Flux LoRA trainer model](https://replicate.com/lucataco/flux-dev-lora).