#!/bin/bash
# Test PulseAudio setup for Thoth Voice Assistant

set -e

echo "=========================================="
echo "Testing PulseAudio Setup"
echo "=========================================="
echo ""

# Check if virtual speaker exists
if pactl list sinks short | grep -q "virtual_speaker"; then
    echo "✓ Virtual speaker found: virtual_speaker"
else
    echo "❌ Virtual speaker not found!"
    echo "   Please run: bash scripts/setup_pulseaudio.sh"
    exit 1
fi

echo ""
echo "Testing TTS output to virtual speaker..."
echo ""

# Test with a simple beep or tone
echo "You should hear a test tone if everything is working."
echo "Playing test tone to virtual_speaker..."

# Generate a 1-second beep using paplay
paplay --device=virtual_speaker /usr/share/sounds/alsa/Front_Center.wav 2>/dev/null || \
    echo "⚠ Could not find test sound file, skipping audio test"

echo ""
echo "If you heard the tone, your setup is working!"
echo ""

# Show current PulseAudio routing
echo "Current audio routing:"
echo "=========================================="
echo "Sinks (output devices):"
pactl list sinks short
echo ""
echo "Loopbacks:"
pactl list modules short | grep module-loopback || echo "  No loopbacks configured"
echo ""

echo "=========================================="
echo "Test complete!"
echo "=========================================="
