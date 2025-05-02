#!/usr/bin/env python
"""
Script to start a Jupyter notebook server.
Run with: python start_jupyter.py
"""

import os
import sys
import subprocess

# Configuration
JUPYTER_PORT = 8888
JUPYTER_IP = "0.0.0.0"
NOTEBOOK_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "notebooks")

def main():
    """Start the Jupyter notebook server"""
    # Ensure the notebook directory exists
    if not os.path.exists(NOTEBOOK_DIR):
        os.makedirs(NOTEBOOK_DIR)
        print(f"Created notebook directory: {NOTEBOOK_DIR}")
    
    print(f"Starting Jupyter notebook server on port {JUPYTER_PORT}...")
    print(f"Notebook directory: {NOTEBOOK_DIR}")
    
    # Build the command
    cmd = [
        "jupyter", "notebook",
        f"--notebook-dir={NOTEBOOK_DIR}",
        f"--ip={JUPYTER_IP}",
        f"--port={JUPYTER_PORT}",
        "--no-browser",
        "--allow-root"
    ]
    
    # Start the server
    try:
        subprocess.run(cmd)
    except KeyboardInterrupt:
        print("\nJupyter notebook server stopped.")
    except Exception as e:
        print(f"Error starting Jupyter notebook server: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()