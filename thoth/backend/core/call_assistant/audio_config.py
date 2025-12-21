"""
Audio source configuration for different use cases on Linux.

This module provides audio source selection logic based on the operating system
and use case (testing vs production).
"""

import platform
import subprocess


def get_audio_source_for_testing():
    """
    Get the audio source for testing purposes.
    
    On Linux: Returns virtual_speaker.monitor for testing
    On Windows: Returns None (uses default WASAPI)
    
    Returns:
        str or None: Audio source name, or None for default
    """
    if platform.system() != "Linux":
        return None
    
    # Look for virtual_speaker monitor
    try:
        result = subprocess.run(['pactl', 'list', 'sources', 'short'], 
                              capture_output=True, text=True, timeout=2)
        
        for line in result.stdout.strip().split('\n'):
            if not line or line.startswith('#'):
                continue
            
            parts = line.split()
            if len(parts) >= 2:
                source_name = parts[1]
                if 'virtual_speaker' in source_name.lower() and 'monitor' in source_name.lower():
                    print(f"[AudioConfig] Using virtual_speaker for testing: {source_name}")
                    return source_name
        
        print("[AudioConfig] ⚠️  virtual_speaker.monitor not found for testing")
        return None
        
    except Exception as e:
        print(f"[AudioConfig] Error finding test audio source: {e}")
        return None


def get_audio_source_for_production():
    """
    Get the audio source for production (real calls).
    
    On Linux: Returns Jabra Evolve2 monitor for production calls
    On Windows: Returns None (uses default WASAPI)
    
    Returns:
        str or None: Audio source name, or None for default
    """
    if platform.system() != "Linux":
        return None
    
    # Look for Jabra Evolve2 monitor
    try:
        result = subprocess.run(['pactl', 'list', 'sources', 'short'], 
                              capture_output=True, text=True, timeout=2)
        
        for line in result.stdout.strip().split('\n'):
            if not line or line.startswith('#'):
                continue
            
            parts = line.split()
            if len(parts) >= 2:
                source_name = parts[1]
                # Look for Jabra Evolve2 monitor
                if 'jabra' in source_name.lower() and 'evolve2' in source_name.lower() and 'monitor' in source_name.lower():
                    print(f"[AudioConfig] Using Jabra Evolve2 for production: {source_name}")
                    return source_name
        
        print("[AudioConfig] ⚠️  Jabra Evolve2 not found, will use system default")
        return None
        
    except Exception as e:
        print(f"[AudioConfig] Error finding production audio source: {e}")
        return None


def get_audio_source(is_testing=False):
    """
    Get the appropriate audio source based on use case.
    
    Args:
        is_testing: If True, use testing audio source (virtual_speaker).
                   If False, use production audio source (Jabra Evolve2).
    
    Returns:
        str or None: Audio source name, or None for default
    """
    if is_testing:
        return get_audio_source_for_testing()
    else:
        return get_audio_source_for_production()


def list_available_sources():
    """
    List all available audio sources.
    
    Returns:
        list: List of dicts with source information
    """
    if platform.system() != "Linux":
        return []
    
    try:
        result = subprocess.run(['pactl', 'list', 'sources', 'short'], 
                              capture_output=True, text=True, timeout=2)
        
        sources = []
        for line in result.stdout.strip().split('\n'):
            if not line or line.startswith('#'):
                continue
            
            parts = line.split()
            if len(parts) >= 2:
                source_info = {
                    'name': parts[1],
                    'status': parts[-1] if len(parts) > 2 else 'UNKNOWN'
                }
                sources.append(source_info)
        
        return sources
        
    except Exception as e:
        print(f"[AudioConfig] Error listing sources: {e}")
        return []


if __name__ == "__main__":
    """Test audio configuration"""
    print("Available audio sources:")
    for source in list_available_sources():
        print(f"  - {source['name']} [{source['status']}]")
    
    print("\nTesting audio source:")
    test_source = get_audio_source_for_testing()
    print(f"  {test_source}")
    
    print("\nProduction audio source:")
    prod_source = get_audio_source_for_production()
    print(f"  {prod_source}")
