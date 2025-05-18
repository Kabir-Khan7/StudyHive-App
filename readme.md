# StudyHive
A Streamlit-based social media platform for students to connect, study, and thrive. Features communities, posts, real-time chat, AI summaries, task management, study timers, and gamified leaderboards, powered by an in-memory database and FastAPI.

## Installation
1. Clone the repo: `git clone https://github.com/yourusername/studyhive.git`
2. Install dependencies: `pip install -r requirements.txt`
3. Run FastAPI server: `python api.py`
4. Run Streamlit app: `streamlit run app.py`

## Features
- Communities, posts, private messages
- Real-time chat (WebRTC)
- Study rooms with task management (simple table-based)
- Pomodoro timer and AI summaries (Hugging Face)
- Gamified leaderboards and notifications (FastAPI)
- Dark mode and responsive UI

## Requirements
- Python 3.8+ (tested with 3.13)
- FastAPI server running on `localhost:8000`
- Note: Data is in-memory (reset on restart)