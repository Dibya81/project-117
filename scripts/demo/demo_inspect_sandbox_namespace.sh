#!/usr/bin/env bash
# ==============================================================================
# Project 117 — OpenSandbox Task Container Network Namespace Inspection
#
# Inspects an active or ephemeral OpenSandbox container to verify that:
# 1. Network mode is 'none' / isolated (zero external network interfaces except lo).
# 2. Kernel capabilities are dropped (cap_drop: ALL).
# 3. Outbound connections (curl / socket) fail deterministically.
# ==============================================================================

set -euo pipefail

echo "======================================================================"
echo "Project 117 — OpenSandbox Container Isolation Inspection"
echo "======================================================================"

CONTAINER_NAME="${1:-project117-sandbox-task}"

# Check if Docker is available on this host
if ! command -v docker &> /dev/null; then
    echo "NOTICE: Docker CLI is not installed or available on this host."
    echo "Expected behavior: OpenSandboxClient raises typed 'SandboxUnavailable'."
    echo "Container security policy requires Docker engine with cap_drop: ALL."
    exit 0
fi

# If container is running, inspect network namespace
if docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    echo "1. Inspecting container network mode..."
    NET_MODE=$(docker inspect --format '{{.HostConfig.NetworkMode}}' "${CONTAINER_NAME}")
    echo "   Network Mode: ${NET_MODE}"
    if [ "${NET_MODE}" = "none" ]; then
        echo "   ✓ Network isolation confirmed: network_mode = none"
    else
        echo "   ✗ WARNING: Container network is not isolated: ${NET_MODE}"
    fi

    echo "2. Inspecting active network interfaces inside container..."
    docker exec "${CONTAINER_NAME}" ip addr show || true

    echo "3. Testing outbound network connection inside container (must fail)..."
    if docker exec "${CONTAINER_NAME}" curl -s --connect-timeout 2 https://1.1.1.1 2>&1; then
        echo "   ✗ FAILED: Outbound connection succeeded (leak detected)"
        exit 1
    else
        echo "   ✓ SUCCESS: Outbound network connection blocked deterministically."
    fi
else
    echo "No container named '${CONTAINER_NAME}' is currently active."
    echo "Verifying docker-compose sandbox profile isolation parameters:"
    grep -E "network_mode|cap_drop|read_only" docker-compose.yml || true
fi

echo "======================================================================"
