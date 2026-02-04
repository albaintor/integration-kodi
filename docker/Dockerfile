FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
COPY src/*.whl ./src/
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY src/ ./src/
COPY driver.json .
COPY kodi.png .

# Create non-root user for security
RUN useradd -m -u 1000 kodi && chown -R kodi:kodi /app
USER kodi

# Expose the integration port (default 9090)
EXPOSE 9090

# Run the driver
CMD ["python", "src/driver.py"]