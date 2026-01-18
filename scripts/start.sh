#!/bin/bash

# Start the Electron frontend
echo "Starting Electron frontend..."
cd "$(dirname "$0")/../frontend"
npm run electron &
ELECTRON_PID=$!

# Wait for Electron to start
sleep 2


: << 'END_COMMENT'
CSHARP_EXE_PATH="$(dirname "$0")/../bin/Release/YourApp.exe"

if [ -f "$CSHARP_EXE_PATH" ]; then
    echo "Starting C# application..."
    "$CSHARP_EXE_PATH"
else
    echo "Warning: C# executable not found at $CSHARP_EXE_PATH"
    echo "Please build the C# project first."
fi

# Wait for Electron process to finish
wait $ELECTRON_PID
END_COMMENT