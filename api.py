from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import asyncio
import json
from datetime import datetime
from typing import List, Dict
import uuid

app = FastAPI()

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8501"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory storage for notifications and WebRTC signaling
notifications: List[Dict] = []
webrtc_sessions: Dict[str, List[WebSocket]] = {}
chat_sessions: Dict[str, List[WebSocket]] = {}

@app.get("/notifications")
async def get_notifications():
    return notifications

@app.post("/notify")
async def notify(data: dict):
    notification = {
        "id": str(uuid.uuid4()),
        "user_id": data.get("user_id", ""),
        "message": data["message"],
        "timestamp": datetime.now().isoformat()
    }
    notifications.append(notification)
    return {"status": "success"}

@app.websocket("/webrtc/{room_id}/{user_id}")
async def webrtc_signaling(websocket: WebSocket, room_id: str, user_id: str):
    await websocket.accept()
    if room_id not in webrtc_sessions:
        webrtc_sessions[room_id] = []
    webrtc_sessions[room_id].append(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            for ws in webrtc_sessions[room_id]:
                if ws != websocket:
                    await ws.send_text(data)
    except Exception as e:
        webrtc_sessions[room_id].remove(websocket)
        if not webrtc_sessions[room_id]:
            del webrtc_sessions[room_id]

@app.websocket("/chat/{sender_id}/{receiver_id}")
async def chat_websocket(websocket: WebSocket, sender_id: str, receiver_id: str):
    await websocket.accept()
    session_key = f"{min(sender_id, receiver_id)}-{max(sender_id, receiver_id)}"
    if session_key not in chat_sessions:
        chat_sessions[session_key] = []
    chat_sessions[session_key].append(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            message = {
                "sender_id": sender_id,
                "content": data,
                "timestamp": datetime.now().isoformat()
            }
            for ws in chat_sessions[session_key]:
                await ws.send_json(message)
    except Exception as e:
        chat_sessions[session_key].remove(websocket)
        if not chat_sessions[session_key]:
            del chat_sessions[session_key]

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)