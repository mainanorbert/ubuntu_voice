"""Backend root entrypoint for local FastAPI runs."""

import os

import uvicorn

from src.main import app


def main() -> None:
    # Start the API when running `python main.py` from the backend folder.
    uvicorn.run("main:app", host="0.0.0.0", port=int(os.getenv("PORT", "8000")))


if __name__ == "__main__":
    main()
