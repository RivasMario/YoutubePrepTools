FROM python:3.11-slim

# Install system dependencies (ffmpeg is required for video processing)
RUN apt-get update && apt-get install -y \
    ffmpeg \
    git \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Set up the working directory
WORKDIR /app

# Install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application scripts
COPY . /app

# Ensure init script is executable
RUN chmod +x /app/init.sh

# Expose Streamlit port
EXPOSE 8501

# Start the application using the init process
ENTRYPOINT ["/app/init.sh"]