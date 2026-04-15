FROM python:3.10-slim

# 1. Install system dependencies for OpenCV and CLIP
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    git \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# 2. Set the working directory
WORKDIR /app

# 3. Handle requirements first for better caching
# IMPORTANT: Ensure your requirements.txt has numpy<2.0.0
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 4. Copy the entire project
COPY . .

# 5. FIX PERMISSIONS & CREATE FOLDERS
# This ensures the app can write to the JSON databases and save uploaded logos
RUN mkdir -p /app/frontend/data /app/uploads && \
    chmod -R 777 /app && \
    touch /app/users_db.json /app/logos_db.json && \
    chmod 666 /app/users_db.json /app/logos_db.json

# 6. Expose the Streamlit port
EXPOSE 7860

# 7. Start the application
CMD ["streamlit", "run", "app.py", "--server.port=7860", "--server.address=0.0.0.0"]