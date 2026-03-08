# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Install system dependencies for Mermaid CLI (Puppeteer/Chromium)
RUN apt-get update && apt-get install -y \
    libglib2.0-0 \
    curl \
    gnupg \
    libnss3 \
    libatk-bridge2.0-0 \
    libgtk-3-0 \
    libasound2t64 \
    libxss1 \
    libgbm-dev \
    libx11-xcb1 \
    libxcomposite1 \
    libxdamage1 \
    libxrandr2 \
    libpango-1.0-0 \
    libcairo2 \
    libcups2 \
    libdrm2 \
    libatspi2.0-0 \
    fonts-liberation \
    chromium \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && npm install -g @mermaid-js/mermaid-cli --unsafe-perm \
    && rm -rf /var/lib/apt/lists/*

# Configure Puppeteer to use system Chromium
ENV PUPPETEER_EXECUTABLE_PATH=/usr/bin/chromium
ENV PUPPETEER_SKIP_CHROMIUM_DOWNLOAD=true

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file into the container
COPY requirements.txt .

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Create puppeteer config for mermaid-cli
RUN echo '{"args": ["--no-sandbox", "--disable-setuid-sandbox"]}' > /app/puppeteer-config.json

# Expose the port Cloud Run expects (default is 8080)
EXPOSE 8080

# Command to run the application using uvicorn directly
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
