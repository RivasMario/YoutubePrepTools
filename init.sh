#!/bin/bash
echo "Starting YoutubePrepTools Container..."

# Ensure a /data directory exists so users can mount their videos easily
mkdir -p /data

# Start the Streamlit application
exec streamlit run /app/app.py \
    --server.port=8501 \
    --server.address=0.0.0.0 \
    --server.enableCORS=false \
    --server.maxUploadSize=4000 \
    --browser.gatherUsageStats=false