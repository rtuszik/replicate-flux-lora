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
   git clone https://github.com/rtuszik/replicate-flux-lora.git
   cd replicate-flux-lora
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

4. Set up your environment variables:
   - Copy the example.env file to create your own .env file:
     ```
     cp example.env .env
     ```
   - Edit the .env file and replace 'your_api_key_here' with your actual Replicate API key:
     ```
     REPLICATE_API_TOKEN=your_api_key_here
     ```

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

### Docker Compose
```yaml
services:
  replicate-flux-lora:
    image: ghcr.io/rtuszik/replicate-flux-lora:latest
    container_name: replicate-flux-lora
    environment:
      - REPLICATE_API_TOKEN=${REPLICATE_API_TOKEN}
    ports:
      - "8080:8080"
    volumes:
      - ${HOST_OUTPUT_DIR}:/app/output
    restart: unless-stopped
```
Replace `${REPLICATE_API_TOKEN}` with your actual Replicate API key.
Replace `${HOST_OUTPUT_DIR}` with the directory on your host machine where you want to save generated images.

## Need help?
Check out Replicate's guide on fine-tuning Flux:
https://replicate.com/blog/fine-tune-flux