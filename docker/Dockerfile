FROM python:3.11-slim-bullseye

WORKDIR /app

# Copy requirements and install dependencies
COPY ./requirements.txt requirements.txt
RUN pip3 install --no-cache-dir --upgrade -r requirements.txt

# Create config directory
RUN mkdir /config

# Copy all source files
ADD . .

# Environment variables
ENV UC_DISABLE_MDNS_PUBLISH="false"
ENV UC_MDNS_LOCAL_HOSTNAME=""
ENV UC_INTEGRATION_INTERFACE="0.0.0.0"
ENV UC_INTEGRATION_HTTP_PORT="9090"
ENV UC_CONFIG_HOME="/config"

# Container metadata
LABEL org.opencontainers.image.source https://github.com/unfoldedcircle/integration-kodi

# Run the driver
CMD ["python3", "-u", "src/driver.py"]