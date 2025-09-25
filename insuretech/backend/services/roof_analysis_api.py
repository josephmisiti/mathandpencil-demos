import modal
import os
from fastapi import FastAPI, HTTPException, Depends
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Modal app setup
app = modal.App("roof-analysis-api")

# API authentication
api_secret = modal.Secret.from_name("acord-api-secret")

# Modal image with dependencies
image = modal.Image.debian_slim().pip_install(
    "fastapi",
    "pydantic",
)

# Request/Response models
class SaveImageRequest(BaseModel):
    image_data: str

volume = modal.Volume.from_name("insuretech-demos")

@app.function(image=image, volumes={"/my-volume": volume})
def save_image_to_volume(image_data: str):
    import base64
    import os
    from datetime import datetime

    image_data = image_data.split(",")[1]
    image_data = base64.b64decode(image_data)

    # Get the current date and time
    now = datetime.now()
    timestamp = now.strftime("%Y-%m-%d_%H-%M-%S")

    # Create the directory if it doesn't exist
    save_path = f"/my-volume/roof-analysis-results/inputs"
    os.makedirs(save_path, exist_ok=True)

    # Save the image
    filename = f"{save_path}/{timestamp}.png"
    with open(filename, "wb") as f:
        f.write(image_data)

    print(f"Image saved to {filename}")
    return {"message": f"Image saved to {filename}"}

# Authentication setup
security = HTTPBearer()

def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Verify the Bearer token"""
    expected_token = os.environ.get("API_TOKEN")
    if not expected_token:
        raise HTTPException(status_code=500, detail="Server configuration error")

    if credentials.credentials != expected_token:
        raise HTTPException(status_code=401, detail="Invalid authentication token")

    return credentials.credentials

# FastAPI app
web_app = FastAPI(title="Roof Analysis API", version="1.0.0")

web_app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",  # Your Vite dev server
        "http://localhost:3000",  # Common React dev port
        "https://demos.mathandpencil.com",  # Add your production domain
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

@web_app.post("/save-image")
def save_image(request: SaveImageRequest, token: str = Depends(verify_token)):
    result = save_image_to_volume.remote(request.image_data)
    return JSONResponse(content=result)

# Deploy the web app
@app.function(image=image, secrets=[api_secret])
@modal.asgi_app()
def fastapi_app():
    return web_app
