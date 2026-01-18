#!/bin/bash

# Start VirtualBox VM and open 3CX Desktop App on host
# Configuration is loaded from .env file

# Load .env file
ENV_FILE="$(dirname "$0")/.env"

if [ ! -f "$ENV_FILE" ]; then
    echo "Error: .env file not found at $ENV_FILE"
    echo "Please copy .env.example to .env and fill in your values"
    exit 1
fi

# Load environment variables
export $(cat "$ENV_FILE" | grep -v '^#' | xargs)

# Validate required variables
for var in VM_NAME VM_USERNAME VM_PASSWORD TARGET_URL; do
    if [ -z "${!var}" ]; then
        echo "Error: $var is not set in .env file"
        exit 1
    fi
done

echo "Starting 3CX environment setup..." 
echo "═══════════════════════════════════"

# Step 1: Open Firefox on host OS with target URL
echo "Step 1: Opening Firefox on host OS..."
firefox "https://$TARGET_URL" &
FIREFOX_PID=$!
echo "Firefox opened with PID: $FIREFOX_PID"

# Step 2: Start the VirtualBox VM
echo "Step 2: Starting VirtualBox VM: $VM_NAME"
VBoxManage startvm "$VM_NAME" --type headless
if [ $? -eq 0 ]; then
    echo "✓ VM started successfully"
else
    echo "✗ Error starting VM"
    exit 1
fi

# Step 3: Wait for VM to fully boot
echo "Step 3: Waiting ${WAIT_TIME_BOOT:-15} seconds for VM to boot..."
sleep "${WAIT_TIME_BOOT:-15}"

# Step 4: Launch 3CX Desktop App inside the VM
echo "Step 4: Launching 3CX Desktop App inside VM..."
VBoxManage guestcontrol "$VM_NAME" run \
    --username "$VM_USERNAME" \
    --password "$VM_PASSWORD" \
    --exe "C:\\Program Files\\3CX\\3CXPhone.exe" \
    2>/dev/null &

echo "✓ 3CX launch command sent to VM"

echo "═══════════════════════════════════"
echo "Setup complete!"
echo "  Host OS: Firefox opened with $TARGET_URL"
echo "  VM: $VM_NAME (3CX launching...)"
