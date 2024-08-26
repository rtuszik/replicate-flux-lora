![Super-Linter](https://github.com/rtuszik/replicate-flux-lora/actions/workflows/super-linter.yml/badge.svg)
![GitHub Actions Workflow Status](https://img.shields.io/github/actions/workflow/status/rtuszik/replicate-flux-lora/docker-build-push.yml)


# Flux Replicate GUI
A simple web interface for running Flux models using the Replicate API. Use it to generate images with custom LoRAs and fine-tuned Flux models.

## What it does
- Runs Flux models via Replicate API
- Lets you use custom LoRAs and fine-tuned models
- Allows disabling the Safety Checker
- Saves your settings
- Shows generated images in a gallery

## Recommended Setup: Docker
Docker is the recommended way to run this application. It ensures consistent environment across different systems.

### Prerequisites
- Docker and Docker Compose installed on your system
- Replicate API key

### Docker Compose Setup
1. Create a `docker-compose.yml` file with the following content:
```yaml
  services:
    replicate-flux-lora:
      image: ghcr.io/rtuszik/replicate-flux-lora:latest
      container_name: replicate-flux-lora
      env_file: .env
      ports:
        - "8080:8080"
      volumes:
        - ${HOST_OUTPUT_DIR}:/app/output
      restart: unless-stopped
```

2. Create a `.env` file in the same directory with the following content:
   ```
   REPLICATE_API_TOKEN=your_api_key_here
   HOST_OUTPUT_DIR=/path/to/your/output/directory
   ```
   Replace `your_api_key_here` with your actual Replicate API key and `/path/to/your/output/directory` with the directory on your host machine where you want to save generated images.

### Running with Docker
1. Start the application:
   ```
   docker-compose up -d
   ```

2. Open `http://localhost:8080` in your browser

3. Choose a model, set your options, enter a prompt, and generate images

## Alternative Setup: Local Python Environment
If you prefer to run the application without Docker, you can use a local Python environment.

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

5. Run the application:
   ```
   python main.py
   ```

6. Open `http://localhost:8080` in your browser

## Need help?
Check out Replicate's guide on fine-tuning Flux:
https://replicate.com/blog/fine-tune-flux