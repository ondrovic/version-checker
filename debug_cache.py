#!/usr/bin/env python3
"""Debug script to test caching functionality."""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from version_checker.core.version_reader import VersionReader

def test_caching():
    """Test the caching functionality."""
    
    # Test with a common Windows executable
    test_file = r"C:\Windows\System32\notepad.exe"
    
    if not os.path.exists(test_file):
        print(f"Test file {test_file} not found. Please provide a valid executable path.")
        return
    
    print(f"Testing caching with: {test_file}")
    print("=" * 50)
    
    # Create a reader with caching enabled
    reader = VersionReader(use_cache=True)
    
    print(f"Cache object: {reader.cache}")
    print(f"Cache type: {type(reader.cache)}")
    
    # Test getting version
    print("\n1. Getting version (should create cache)...")
    version = reader.get_version(test_file)
    print(f"Version: {version}")
    
    # Check if cache file was created
    cache_path = reader.cache.get_cache_path(test_file)
    print(f"Cache path: {cache_path}")
    print(f"Cache file exists: {cache_path.exists()}")
    
    if cache_path.exists():
        print("Cache file contents:")
        try:
            with open(cache_path, 'r') as f:
                print(f.read())
        except Exception as e:
            print(f"Error reading cache: {e}")
    
    # Test getting version again (should use cache)
    print("\n2. Getting version again (should use cache)...")
    version2 = reader.get_version(test_file)
    print(f"Version: {version2}")
    
    # Test cache validity
    print(f"\nCache valid: {reader.cache.is_cache_valid(test_file)}")
    
    # Test direct cache methods
    print("\n3. Testing direct cache methods...")
    cached_version = reader.cache.get_cached_version(test_file)
    print(f"Cached version: {cached_version}")

if __name__ == "__main__":
    test_caching()