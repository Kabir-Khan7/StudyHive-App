from fastapi import FastAPI, WebSocket, HTTPException
from fastapi.responses import JSONResponse
import json
from datetime import datetime

app = FastAPI()

# In-memory storage for notifications
notifications = []

@app.post("/notify")
async def notify(data: dict):
    if not data.get("user_id") or not data.get("message"):
        raise HTTPException(status_code=422, detail="user_id and message are required")
    notification = {
        "user_id": data["user_id"],
        "message": data["message"],
        "timestamp": datetime.now().isoformat()
    }
    notifications.append(notification)
    return {"status": "Notification sent"}

@app.get("/notifications")
async def get_notifications():
    return notifications

@app.websocket("/chat/{sender_id}/{receiver_id}")
async def websocket_endpoint(websocket: WebSocket, sender_id: str, receiver_id: str):
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_text()
            message = {
                "sender_id": sender_id,
                "receiver_id": receiver_id,
                "content": data,
                "timestamp": datetime.now().isoformat()
            }
            await websocket.send_text(json.dumps(message))
    except Exception as e:
        print(f"WebSocket error: {str(e)}")
    finally:
        await websocket.close()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)