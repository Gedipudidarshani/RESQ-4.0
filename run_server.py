"""
RESQ 4.0 Server Launcher
Starts the FastAPI application and Operator Intelligence Dashboard via Uvicorn.
"""
import sys
import os
import uvicorn

# Ensure project root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def main():
    host = "0.0.0.0"
    port = 8000
    print("=" * 70)
    print("  RESQ 4.0: Failure-Aware Agentic Emergency Intelligence Platform")
    print("  Tagline: Listen. Understand. Validate. Recover. Coordinate. Escalate. Learn.")
    print("=" * 70)
    print(f"  * Web Dashboard:        http://127.0.0.1:{port}/")
    print(f"  * Swagger API Docs:     http://127.0.0.1:{port}/docs")
    print(f"  * System Health Check:  http://127.0.0.1:{port}/api/health")
    print("=" * 70)
    
    uvicorn.run("backend.main:app", host=host, port=port, log_level="info")

if __name__ == "__main__":
    main()
