FROM python:3.11-slim

# Environment variables to optimize Python behavior
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV DOCKER_CONTAINER=True

# Set the working directory
WORKDIR /app

# Copy the requirements file and install dependencies
COPY requirements.txt .
RUN python -m pip install -r requirements.txt

# Copy the application source code to the working directory
COPY src/ .
COPY settings.toml .

# Expose the desired port
EXPOSE 8080

# Define the command to run your application
CMD ["python", "main.py"]