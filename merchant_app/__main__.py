import uvicorn

from merchant_app.config import get_settings

if __name__ == "__main__":
    uvicorn.run("merchant_app.main:app", host="127.0.0.1", port=get_settings().port)
