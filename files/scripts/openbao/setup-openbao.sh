#!/bin/bash

# Get current user's UID and GID
CURRENT_UID=$(id -u)
CURRENT_GID=$(id -g)

# Create directories for persistent storage and configuration
mkdir -p openbao/data
mkdir -p openbao/logs
mkdir -p openbao/config
mkdir -p openbao/etc

# Create docker-compose.yml file with additional mounts for /etc/passwd and /etc/group
cat > docker-compose.yml << 'EOF'
services:
  openbao:
    image: ghcr.io/openbao/openbao:latest
    container_name: openbao
    ports:
      - "8200:8200"
    volumes:
      - ./openbao/data:/vault/file
      - ./openbao/logs:/vault/logs
      - ./openbao/config:/vault/config
      - ./openbao/etc/passwd:/etc/passwd:ro
      - ./openbao/etc/group:/etc/group:ro
    environment:
      - VAULT_ADDR=http://127.0.0.1:8200
    cap_add:
      - IPC_LOCK
    command: server -config=/vault/config/local.json
    healthcheck:
      test: ["CMD-SHELL", "vault status >/dev/null 2>&1 || exit 0"]
      interval: 10s
      timeout: 5s
      retries: 12
    restart: unless-stopped
EOF

# Create OpenBao configuration file
cat > openbao/config/local.json << 'EOF'
{
  "storage": {
    "file": {
      "path": "/vault/file"
    }
  },
  "listener": {
    "tcp": {
      "address": "0.0.0.0:8200",
      "tls_disable": true
    }
  },
  "api_addr": "http://127.0.0.1:8200",
  "default_lease_ttl": "168h",
  "max_lease_ttl": "720h",
  "ui": true
}
EOF

# Create custom /etc/passwd and /etc/group files for the openbao user
cat > openbao/etc/passwd << EOF
openbao:x:${CURRENT_UID}:${CURRENT_GID}:openbao user:/vault:/bin/bash
EOF

cat > openbao/etc/group << EOF
openbao:x:${CURRENT_GID}:
EOF

# Set proper permissions for storage and configuration
#chown -R ${CURRENT_UID}:${CURRENT_GID} openbao/data openbao/logs openbao/config openbao/etc
chmod -R 755 openbao/data openbao/logs openbao/config
chmod 644 openbao/config/local.json openbao/etc/passwd openbao/etc/group

# Start the container
echo "Starting OpenBao container..."
docker-compose up -d

# Wait for OpenBao to be ready
echo "Waiting for OpenBao to be ready..."
MAX_WAIT=120
WAIT_INTERVAL=5
ELAPSED=0

while [ $ELAPSED -lt $MAX_WAIT ]; do
    CONTAINER_STATUS=$(docker inspect -f '{{.State.Status}}' openbao 2>/dev/null)
    if [ "$CONTAINER_STATUS" = "running" ]; then
        HEALTH_STATUS=$(docker inspect -f '{{.State.Health.Status}}' openbao 2>/dev/null)
        echo "OpenBao container status: $CONTAINER_STATUS, health status: $HEALTH_STATUS. Checking if server is responsive..."
        # Check if vault status produces output, indicating the server is running
        STATUS_OUTPUT=$(docker exec openbao vault status 2>&1)
        if echo "$STATUS_OUTPUT" | grep -q "Sealed"; then
            echo "OpenBao server is responsive (sealed state detected)!"
            break
        else
            echo "Vault status output: $STATUS_OUTPUT"
        fi
    else
        echo "OpenBao container status: $CONTAINER_STATUS. Waiting ${WAIT_INTERVAL}s..."
    fi
    sleep $WAIT_INTERVAL
    ELAPSED=$((ELAPSED + WAIT_INTERVAL))
done

# Check if container is running
if [ "$(docker inspect -f '{{.State.Running}}' openbao 2>/dev/null)" = "true" ]; then
    echo "OpenBao container is running. Attempting initialization..."

    # Check if OpenBao is already initialized
    STATUS=$(docker exec openbao vault status 2>&1)
    if echo "$STATUS" | grep -q "Initialized.*true"; then
        echo "OpenBao is already initialized. Skipping initialization."
        # Extract unseal key and root token from existing init.txt if available
        if [ -s init.txt ]; then
            UNSEAL_KEY=$(grep 'Unseal Key 1' init.txt | awk '{print $NF}')
            ROOT_TOKEN=$(grep 'Initial Root Token' init.txt | awk '{print $NF}')
        else
            echo "Warning: init.txt not found or empty. Manual unsealing may be required."
            docker logs openbao
            exit 1
        fi
    else
        echo "Initializing OpenBao..."
        # Initialize OpenBao with retries
        MAX_RETRIES=3
        RETRY_COUNT=0
        until [ $RETRY_COUNT -ge $MAX_RETRIES ]; do
            docker exec openbao vault operator init -key-shares=1 -key-threshold=1 > init.txt 2>&1
            if [ $? -eq 0 ] && [ -s init.txt ] && grep -q 'Unseal Key 1' init.txt; then
                break
            fi
            RETRY_COUNT=$((RETRY_COUNT + 1))
            echo "Initialization attempt $RETRY_COUNT failed. Retrying in 5s..."
            sleep 5
        done

        # Check if init.txt is non-empty and valid
        if [ -s init.txt ] && grep -q 'Unseal Key 1' init.txt; then
            # Extract unseal key and root token
            UNSEAL_KEY=$(grep 'Unseal Key 1' init.txt | awk '{print $NF}')
            ROOT_TOKEN=$(grep 'Initial Root Token' init.txt | awk '{print $NF}')

            if [ -z "$UNSEAL_KEY" ] || [ -z "$ROOT_TOKEN" ]; then
                echo "Error: Failed to extract unseal key or root token from init.txt."
                echo "Contents of init.txt:"
                cat init.txt
                echo "Container logs:"
                docker logs openbao
                exit 1
            fi
        else
            echo "Error: OpenBao initialization failed after $MAX_RETRIES attempts."
            echo "Contents of init.txt:"
            cat init.txt
            echo "Container logs:"
            docker logs openbao
            exit 1
        fi
    fi

    # Unseal OpenBao
    echo "Unsealing OpenBao..."
    docker exec openbao vault operator unseal $UNSEAL_KEY

    # Check if OpenBao is unsealed
    if docker exec openbao vault status | grep -q "Sealed.*false"; then
        echo "OpenBao is unsealed!"
        # Login with root token
        docker exec openbao vault login $ROOT_TOKEN

        echo "OpenBao is initialized and unsealed!"
        echo "Root Token: $ROOT_TOKEN"
        echo "Access OpenBao at: http://localhost:8200"
        echo "Initialization details saved in init.txt"
    else
        echo "Error: Failed to unseal OpenBao."
        echo "Container logs:"
        docker logs openbao
        exit 1
    fi
else
    echo "Error: OpenBao container failed to start after ${MAX_WAIT}s."
    echo "Container logs:"
    docker logs openbao
    exit 1
fi
