"""
Development server runner for Legal Assistant API
"""
import uvicorn

if __name__ == "__main__":
    print("🚀 Starting Legal Assistant API (Development Mode)...")
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=5000,
        reload=True,  # Auto-reload on code changes
        reload_dirs=["app"],  # Only watch app directory
        log_level="info"
    )