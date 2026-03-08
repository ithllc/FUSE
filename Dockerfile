# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Install system dependencies for OpenCV and other tools
RUN apt-get update && apt-get install -y \
    libgl1-mesa-glx \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file into the container
COPY requirements.txt .

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Expose the port Cloud Run expects (default is 8080)
EXPOSE 8080

# Command to run the application
# Using a web server wrapper or just running the main.py
# Note: FUSE currently runs a continuous loop. Cloud Run expects a web server.
CMD ["python", "main.py"]
