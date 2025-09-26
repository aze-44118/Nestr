# Import the FastAPI app from the app module
from app import app

if __name__ == "__main__":
    # Optional local run: uvicorn main:app --host $HOST --port $PORT
    import uvicorn
    import os
    from dotenv import load_dotenv
    
    load_dotenv()
    HOST = os.getenv("HOST", "0.0.0.0")
    PORT = int(os.getenv("PORT", "8080"))

    uvicorn.run("main:app", host=HOST, port=PORT, reload=False)


