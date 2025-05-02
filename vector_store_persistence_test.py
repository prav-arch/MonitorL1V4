#!/usr/bin/env python
"""
Script to test the Vector Store persistence functionality.
Run with: python vector_store_persistence_test.py
"""

import os
import sys
import time
import pickle
import numpy as np
from pathlib import Path

# Add the current directory to path so we can import the utils module
sys.path.append('.')

try:
    from utils.vector_store import VectorStore
    print("Successfully imported VectorStore")
except ImportError as e:
    print(f"Error importing VectorStore: {e}")
    sys.exit(1)

def examine_vector_store_files():
    """Look at the current vector store files."""
    vector_index_path = 'data/vector_index'
    index_file = f"{vector_index_path}.index"
    metadata_file = f"{vector_index_path}.metadata"
    
    print(f"Index file exists: {os.path.exists(index_file)}")
    print(f"Metadata file exists: {os.path.exists(metadata_file)}")
    
    # If the files exist, look at their size
    if os.path.exists(index_file):
        print(f"Index file size: {os.path.getsize(index_file) / 1024:.2f} KB")
        
    if os.path.exists(metadata_file):
        print(f"Metadata file size: {os.path.getsize(metadata_file) / 1024:.2f} KB")

def inspect_metadata():
    """Examine the metadata contents."""
    vector_index_path = 'data/vector_index'
    metadata_file = f"{vector_index_path}.metadata"
    
    if os.path.exists(metadata_file):
        try:
            with open(metadata_file, 'rb') as f:
                metadata = pickle.load(f)
            
            print(f"Number of entries in metadata: {len(metadata)}")
            
            # Show a few sample entries
            if len(metadata) > 0:
                print("\nSample metadata entries:")
                for i in range(min(3, len(metadata))):
                    print(f"\nEntry {i+1}:")
                    print(metadata[i])
        except Exception as e:
            print(f"Error loading metadata: {e}")
    else:
        print("No metadata file found.")

def test_vector_store_persistence():
    """Create a test vector store and verify that changes are immediately saved."""
    test_vector_store_path = 'data/test_vector_index'
    try:
        test_vs = VectorStore(index_path=test_vector_store_path)
        print("Created test vector store")
        
        # Add a vector and check if it's saved immediately
        test_vector = np.random.random(384).astype(np.float32)  # 384 is the default dimension
        test_metadata = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "level": "INFO",
            "message": "Test vector store entry",
            "service": "test",
            "additional_fields": {"test_id": 1}
        }
        
        # Before adding, check if files exist
        print(f"Before adding - Index file exists: {os.path.exists(test_vector_store_path + '.index')}")
        print(f"Before adding - Metadata file exists: {os.path.exists(test_vector_store_path + '.metadata')}")
        
        # Add the vector
        test_vs.add_vector(test_vector, test_metadata)
        print("Added test vector")
        
        # After adding, check if files exist and verify they're not empty
        print(f"\nAfter adding - Index file exists: {os.path.exists(test_vector_store_path + '.index')}")
        print(f"After adding - Metadata file exists: {os.path.exists(test_vector_store_path + '.metadata')}")
        
        if os.path.exists(test_vector_store_path + '.metadata'):
            with open(test_vector_store_path + '.metadata', 'rb') as f:
                saved_metadata = pickle.load(f)
            print(f"\nNumber of entries in saved metadata: {len(saved_metadata)}")
            if len(saved_metadata) > 0:
                print("First saved metadata entry:")
                print(saved_metadata[0])
                print("\nTest successful! Vector was saved immediately after adding.")
            else:
                print("\nTest failed: Metadata file exists but is empty.")
        else:
            print("\nTest failed: Metadata file was not created.")
    except Exception as e:
        print(f"Error testing vector store persistence: {e}")
    
    # Clean up test files
    try:
        if os.path.exists(test_vector_store_path + '.index'):
            os.remove(test_vector_store_path + '.index')
            
        if os.path.exists(test_vector_store_path + '.metadata'):
            os.remove(test_vector_store_path + '.metadata')
            
        print("\nTest files cleaned up.")
    except Exception as e:
        print(f"Error cleaning up test files: {e}")

def main():
    """Run all test functions."""
    print("=== Examining Vector Store Files ===")
    examine_vector_store_files()
    
    print("\n=== Inspecting Metadata ===")
    inspect_metadata()
    
    print("\n=== Testing Vector Store Persistence ===")
    test_vector_store_persistence()

if __name__ == "__main__":
    main()