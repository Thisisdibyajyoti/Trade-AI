"""
Vercel Serverless Function entry point.
Wraps the FastAPI application using Mangum for AWS Lambda / Vercel serverless compatibility.
"""
import sys
import os

# Add the project root to the Python path so backend imports work
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# Also add backend/ directly since the FastAPI app uses bare imports like `from market_data.fetcher import ...`
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backend"))

from mangum import Mangum
from backend.api.main import app

# Mangum wraps the ASGI app for serverless deployment
handler = Mangum(app, lifespan="off")
