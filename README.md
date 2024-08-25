# Flux Replicate GUI

A simple web interface for running Flux models using the Replicate API. Use it to generate images with custom LoRAs and fine-tuned Flux models.

## What it does

- Runs Flux models via Replicate API
- Lets you use custom LoRAs and fine-tuned models
- Allows disabling the Safety Checker
- Saves your settings
- Shows generated images in a gallery

## Setup

1. Clone the repo:
   ```
   git clone https://github.com/yourusername/flux-replicate-gui.git
   cd flux-replicate-gui
   ```

2. Create and activate a virtual environment:
   ```
   python -m venv venv
   source venv/bin/activate  # On Windows, use `venv\Scripts\activate`
   ```

3. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

4. Set your Replicate API key:
   ```
   export REPLICATE_API_TOKEN=your_api_key_here
   ```
   On Windows, use `set REPLICATE_API_TOKEN=your_api_key_here`

## Run it

1. Make sure your virtual environment is activated

2. Start the app:
   ```
   python main.py
   ```

3. Open `http://localhost:8080` in your browser

4. Choose a model, set your options, enter a prompt, and generate images
## Docker

**Docker is currently experimental.**

To run the app in a Docker container, follow these steps:

1. Make sure you have Docker installed on your system.
2. Build the Docker image:
   ```
   docker build -t flux-replicate-gui .
   ```
   Run the Docker container:
   ```
   docker run -p 8080:8080 flux-replicate-gui
   ```
   Open `http://localhost:8080` in your browser



## Need help?

Check out Replicate's guide on fine-tuning Flux:
https://replicate.com/blog/fine-tune-flux
