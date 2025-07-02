.PHONY: build up down logs restart clean

# Build the Docker image
build:
    docker-compose build

# Start the service
up:
    docker-compose up -d

# Stop the service  
down:
    docker-compose down

# Show logs
logs:
    docker-compose logs -f

# Restart the service
restart:
    docker-compose restart

# Clean up everything
clean:
    docker-compose down -v
    docker image prune -f

# Build and start
start: build up

# Development mode with live logs
dev:
    docker-compose up --build