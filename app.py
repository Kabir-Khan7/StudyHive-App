import streamlit as st
import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
import pandas as pd
import plotly.express as px
from whoosh.index import create_in, open_dir, exists_in
from whoosh.fields import Schema, TEXT, ID
from whoosh.qparser import QueryParser
import os
import requests
from transformers import pipeline
import pypdf
from streamlit_javascript import st_javascript
import asyncio
import aiohttp
import base64
import json

# Set page config
st.set_page_config(page_title="StudyHive Ultimate", page_icon="🐝", layout="wide")

# Custom CSS for modern UI
st.markdown(
    """
    <style>
    .main { 
        background-color: #f5f5f5; 
        color: #333333; 
    }
    .stButton>button {
        background-color: #2E8B57;
        color: white;
        border-radius: 8px;
        padding: 10px 20px;
        transition: all 0.3s;
    }
    .stButton>button:hover {
        background-color: #1E6B47;
        transform: scale(1.05);
    }
    .card {
        background: white;
        border-radius: 10px;
        padding: 15px;
        box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        margin-bottom: 15px;
        color: #333333;
    }
    .card strong, .card em, .card p, .card small {
        color: #333333;
    }
    .card .badge {
        background: #FFD700;
        color: #333333;
        padding: 5px 10px;
        border-radius: 12px;
        font-size: 12px;
    }
    .dark-mode {
        background: #1a1a1a;
        color: #f5f5f5;
    }
    .dark-mode .main {
        background: #1a1a1a;
        color: #f5f5f5;
    }
    .dark-mode .card {
        background: #2a2a2a;
        color: #f5f5f5;
    }
    .dark-mode .card strong, .dark-mode .card em, .dark-mode .card p, .dark-mode .card small {
        color: #f5f5f5;
    }
    .dark-mode .card .badge {
        background: #FFD700;
        color: #333333;
    }
    .task-table {
        width: 100%;
        border-collapse: collapse;
    }
    .task-table th, .task-table td {
        padding: 8px;
        text-align: left;
        border-bottom: 1px solid #ddd;
    }
    .stMarkdown, .stText {
        color: #333333;
    }
    .dark-mode .stMarkdown, .dark-mode .stText {
        color: #f5f5f5;
    }
    .profile-pic {
        border-radius: 50%;
        width: 100px;
        height: 100px;
        object-fit: cover;
    }
    .chat-box {
        max-height: 400px;
        overflow-y: auto;
        border: 1px solid #ddd;
        padding: 10px;
        border-radius: 8px;
    }
    .chat-message {
        margin: 5px 0;
        padding: 8px;
        border-radius: 5px;
    }
    .chat-message.sent {
        background: #2E8B57;
        color: white;
        text-align: right;
    }
    .chat-message.received {
        background: #f0f0f0;
        color: #333;
    }
    </style>
    """,
    unsafe_allow_html=True
)

# In-Memory Database
class Database:
    def __init__(self):
        self.users = {}  # user_id -> User
        self.communities = {}  # community_id -> Community
        self.posts = []  # List of Post
        self.messages = []  # List of Message
        self.study_rooms = {}  # room_id -> StudyRoom
        self.badges = {}  # user_id -> List of Badge
        self.posts_ratings = {}  # post_id -> rating
        self.communities_ratings = {}  # community_id -> rating
        self.tasks = []  # List of Task
        self.notifications = []  # List of Notification

    def add_user(self, user):
        if not user.username.strip():
            raise ValueError("Username cannot be empty")
        if any(u.username.lower() == user.username.lower() for u in self.users.values()):
            raise ValueError("Username already taken")
        self.users[user.user_id] = user
        self.badges[user.user_id] = [Badge(str(uuid.uuid4()), "Welcome", user.user_id)]

    def get_user(self, user_id):
        return self.users.get(user_id)

    def update_user(self, user):
        self.users[user.user_id] = user

    def add_community(self, community):
        self.communities[community.community_id] = community
        creator = self.get_user(community.creator_id)
        if creator:
            creator.join_community(community.community_id)
            self.award_badge(creator.user_id, "Community Leader")

    def add_post(self, post):
        self.posts.append(post)
        is_first = not any(p.user_id == post.user_id for p in self.posts[:-1])
        if is_first and post.user_id in self.users:
            self.award_badge(post.user_id, "First Post")

    def add_like(self, post_id, user_id):
        post = next((p for p in self.posts if p.post_id == post_id), None)
        if post and user_id not in post.likes:
            post.likes.append(user_id)

    def add_comment(self, post_id, user_id, content):
        post = next((p for p in self.posts if p.post_id == post_id), None)
        if post:
            post.comments.append({"user_id": user_id, "content": content, "timestamp": datetime.now()})

    def add_message(self, message):
        self.messages.append(message)
        self.notify_user(message.receiver_id, f"New message from {self.get_user(message.sender_id).username}")

    def add_study_room(self, room):
        self.study_rooms[room.room_id] = room
        if room.creator_id in self.users:
            self.award_badge(room.creator_id, "Study Planner")

    def award_badge(self, user_id, badge_name):
        badge = Badge(str(uuid.uuid4()), badge_name, user_id)
        self.badges[user_id].append(badge)

    def add_rating(self, post_id, rating):
        self.posts_ratings[post_id] = rating

    def add_community_rating(self, community_id, rating):
        self.communities_ratings[community_id] = rating

    def add_task(self, task):
        for i, t in enumerate(self.tasks):
            if t.task_id == task.task_id:
                self.tasks[i] = task
                return
        self.tasks.append(task)

    def delete_task(self, task_id):
        self.tasks = [t for t in self.tasks if t.task_id != task_id]

    def get_tasks(self, user_id=None, room_id=None):
        if room_id:
            return [t for t in self.tasks if t.room_id == room_id]
        elif user_id:
            return [t for t in self.tasks if t.user_id == user_id]
        return self.tasks

    def notify_user(self, user_id, message):
        self.notifications.append({"user_id": user_id, "message": message, "timestamp": datetime.now()})

    def get_notifications(self, user_id):
        return [n for n in self.notifications if n["user_id"] == user_id]

# User Classes
class User(ABC):
    def __init__(self, user_id, username, email, bio="", profile_picture=None):
        self.user_id = user_id
        self.username = username
        self.email = email
        self.bio = bio
        self.profile_picture = profile_picture
        self.communities = []
        self.is_premium = False

    def join_community(self, community_id):
        if community_id not in self.communities:
            self.communities.append(community_id)

    @abstractmethod
    def display_profile(self):
        pass

class FreeUser(User):
    def display_profile(self):
        return f"{self.username} (Free) | Communities: {len(self.communities)}"

class PremiumUser(User):
    def __init__(self, user_id, username, email, bio="", profile_picture=None):
        super().__init__(user_id, username, email, bio, profile_picture)
        self.is_premium = True

    def display_profile(self):
        return f"{self.username} (Premium ✨) | Communities: {len(self.communities)} | Ad-Free"

# Community
class Community:
    def __init__(self, community_id, name, creator_id):
        self.community_id = community_id
        self.name = name
        self.creator_id = creator_id
        self.members = [creator_id]

# Post
class Post:
    def __init__(self, post_id, content, user_id, community_id, tag, timestamp=None):
        self.post_id = post_id
        self.content = content
        self.user_id = user_id
        self.community_id = community_id
        self.tag = tag
        self.timestamp = timestamp or datetime.now()
        self.likes = []
        self.comments = []

# Message
class Message:
    def __init__(self, message_id, sender_id, receiver_id, content, community_id=None, timestamp=None):
        self.message_id = message_id
        self.sender_id = sender_id
        self.receiver_id = receiver_id
        self.content = content
        self.community_id = community_id
        self.timestamp = timestamp or datetime.now()

# Study Room
class StudyRoom:
    def __init__(self, room_id, name, creator_id, scheduled_time, meeting_key, participants=None):
        self.room_id = room_id
        self.name = name
        self.creator_id = creator_id
        self.scheduled_time = scheduled_time
        self.meeting_key = meeting_key
        self.participants = participants or [creator_id]

# Badge
class Badge:
    def __init__(self, badge_id, name, user_id, timestamp=None):
        self.badge_id = badge_id
        self.name = name
        self.user_id = user_id
        self.timestamp = timestamp or datetime.now()

# Task
class Task:
    def __init__(self, task_id, user_id, title, status, room_id=None):
        self.task_id = task_id
        self.user_id = user_id
        self.title = title
        self.status = status
        self.room_id = room_id

# Initialize Database
if "db" not in st.session_state:
    st.session_state.db = Database()

# Feature 1: Study Timer (Pomodoro)
def study_timer():
    st.subheader("Pomodoro Study Timer ⏰")
    if "timer_running" not in st.session_state:
        st.session_state.timer_running = False
        st.session_state.timer_seconds = 1500
        st.session_state.timer_mode = "Work"
        st.session_state.sessions_completed = 0

    if st.button("Start/Stop Timer"):
        st.session_state.timer_running = not st.session_state.timer_running

    if st.session_state.timer_running:
        js_code = """
        let seconds = parseInt(document.getElementById('timer_seconds') ? document.getElementById('timer_seconds').value : 1500);
        let interval = setInterval(() => {
            if (seconds > 0) {
                seconds--;
                if (document.getElementById('timer_seconds')) {
                    document.getElementById('timer_seconds').value = seconds;
                }
            } else {
                clearInterval(interval);
                window.location.reload();
            }
        }, 1000);
        """
        st_javascript(js_code)

    if st.session_state.timer_seconds <= 0:
        st.session_state.timer_running = False
        if st.session_state.timer_mode == "Work":
            st.session_state.timer_mode = "Break"
            st.session_state.timer_seconds = 300
            st.session_state.sessions_completed += 1
            if st.session_state.sessions_completed % 4 == 0 and "user" in st.session_state:
                st.session_state.db.award_badge(st.session_state.user.user_id, "Pomodoro Master")
        else:
            st.session_state.timer_mode = "Work"
            st.session_state.timer_seconds = 1500
        st.rerun()

    minutes, seconds = divmod(st.session_state.timer_seconds, 60)
    st.markdown(f"<input type='hidden' id='timer_seconds' value='{st.session_state.timer_seconds}'>", unsafe_allow_html=True)
    st.metric("Timer", f"{minutes:02d}:{seconds:02d} ({st.session_state.timer_mode})")
    st.write(f"Sessions Completed: {st.session_state.sessions_completed}")

# Feature 2: AI-Powered Summaries
@st.cache_resource
def load_summarizer():
    return pipeline("summarization", model="facebook/bart-large-cnn")

def summarize_text(text, is_premium=False):
    summarizer = load_summarizer()
    max_length = 200 if is_premium else 100
    try:
        summary = summarizer(text, max_length=max_length, min_length=30, do_sample=False)[0]["summary_text"]
        return summary
    except Exception as e:
        st.error(f"Failed to generate summary: {str(e)}")
        return ""

def process_pdf(file):
    try:
        reader = pypdf.PdfReader(file)
        text = ""
        for page in reader.pages:
            text += page.extract_text() or ""
        return text
    except Exception as e:
        st.error(f"Failed to process PDF: {str(e)}")
        return ""

# Feature 3: Simplified Task Management
def task_manager(user_id, room_id=None):
    st.subheader("Your Tasks" if not room_id else f"Tasks for Study Room")
    tasks = st.session_state.db.get_tasks(user_id=user_id, room_id=room_id)
    if not tasks:
        st.info("No tasks yet. Add some below!")
    else:
        df = pd.DataFrame([
            {"Task ID": t.task_id, "Title": t.title, "Status": t.status}
            for t in tasks
        ])
        st.dataframe(df, use_container_width=True)

        st.subheader("Edit Task")
        task_options = [(t.task_id, t.title) for t in tasks]
        if task_options:
            task_id = st.selectbox("Select Task to Edit", [t[0] for t in task_options],
                                  format_func=lambda x: next(t[1] for t in task_options if t[0] == x))
            selected_task = next(t for t in tasks if t.task_id == task_id)
            with st.form(f"edit_task_form_{task_id}"):
                title = st.text_input("Task Title", value=selected_task.title)
                status = st.selectbox("Status", ["To-Do", "In Progress", "Done"], 
                                     index=["To-Do", "In Progress", "Done"].index(selected_task.status))
                col1, col2 = st.columns(2)
                with col1:
                    submit = st.form_submit_button("Update Task")
                with col2:
                    delete = st.form_submit_button("Delete Task")
                if submit:
                    if not title:
                        st.error("Task title cannot be empty!")
                    else:
                        st.session_state.db.add_task(Task(task_id, user_id, title, status, room_id))
                        st.success("Task updated!")
                        st.rerun()
                if delete:
                    st.session_state.db.delete_task(task_id)
                    st.success("Task deleted!")
                    st.rerun()

    st.subheader("Add New Task")
    with st.form("add_task_form"):
        title = st.text_input("Task Title")
        status = st.selectbox("Status", ["To-Do", "In Progress", "Done"], key="add_task_status")
        submit = st.form_submit_button("Add Task")
        if submit:
            if not title:
                st.error("Task title cannot be empty!")
            else:
                task_id = str(uuid.uuid4())
                st.session_state.db.add_task(Task(task_id, user_id, title, status, room_id))
                st.success("Task added!")
                st.rerun()

# Feature 4: Notifications
async def fetch_notifications():
    for _ in range(2):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get("http://localhost:8000/notifications", timeout=5) as resp:
                    if resp.status == 200:
                        return await resp.json()
        except Exception as e:
            st.warning(f"Failed to fetch notifications: {str(e)}")
            await asyncio.sleep(1)
    return []

def display_notifications(user_id):
    notifications = st.session_state.db.get_notifications(user_id)
    if notifications:
        st.subheader("Notifications 🔔")
        for notif in notifications:
            st.markdown(f"<div class='card'>{notif['message']} ({notif['timestamp'].strftime('%Y-%m-%d %H:%M')})</div>", unsafe_allow_html=True)

# Feature 5: Leaderboard
def leaderboard():
    data = []
    for user in st.session_state.db.users.values():
        badge_count = len(st.session_state.db.badges.get(user.user_id, []))
        post_count = sum(1 for p in st.session_state.db.posts if p.user_id == user.user_id)
        tasks_done = sum(1 for t in st.session_state.db.tasks if t.user_id == user.user_id and t.status == "Done")
        score = badge_count * 10 + post_count * 5 + tasks_done * 3
        data.append({"Username": user.username, "Badges": badge_count, "Posts": post_count, 
                     "Tasks Done": tasks_done, "Score": score})
    df = pd.DataFrame(data)
    if not df.empty:
        fig = px.bar(df, x="Username", y="Score", color="Score", 
                     title="StudyHive Leaderboard", text_auto=True)
        st.plotly_chart(fig)
    else:
        st.info("No leaderboard data yet.")

# Feature 6: Real-Time Chat
async def chat_client(user_id, receiver_id):
    ws_url = f"ws://localhost:8000/chat/{user_id}/{receiver_id}"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.ws_connect(ws_url) as ws:
                st.session_state.ws = ws
                async for msg in ws:
                    if msg.type == aiohttp.WSMsgType.TEXT:
                        data = json.loads(msg.data)
                        st.session_state.chat_messages.append({
                            "sender_id": data["sender_id"],
                            "content": data["content"],
                            "timestamp": datetime.fromisoformat(data["timestamp"])
                        })
                        st.rerun()
    except Exception as e:
        st.error(f"Chat connection failed: {str(e)}")

def display_chat(user, receiver_id):
    st.subheader("Messages 💬")
    receiver = st.session_state.db.get_user(receiver_id)
    if not receiver:
        st.error("Receiver not found!")
        return

    if "chat_messages" not in st.session_state:
        st.session_state.chat_messages = [
            m for m in st.session_state.db.messages
            if (m.sender_id == user.user_id and m.receiver_id == receiver_id) or
               (m.sender_id == receiver_id and m.receiver_id == user.user_id)
        ]

    with st.container():
        for msg in st.session_state.chat_messages:
            sender = st.session_state.db.get_user(msg["sender_id"])
            cls = "sent" if msg["sender_id"] == user.user_id else "received"
            st.markdown(
                f"<div class='chat-message {cls}'>{sender.username}: {msg['content']} "
                f"(<small>{msg['timestamp'].strftime('%H:%M')})</small></div>",
                unsafe_allow_html=True
            )

    with st.form("chat_form"):
        message = st.text_input("Type a message")
        submit = st.form_submit_button("Send")
        if submit and message:
            msg_id = str(uuid.uuid4())
            st.session_state.db.add_message(
                Message(msg_id, user.user_id, receiver_id, message)
            )
            st.session_state.chat_messages.append({
                "sender_id": user.user_id,
                "content": message,
                "timestamp": datetime.now()
            })
            try:
                requests.post("http://localhost:8000/notify",
                             json={"user_id": receiver_id, "message": f"New message from {user.username}"})
            except Exception as e:
                st.warning(f"Failed to send notification: {str(e)}")
            st.rerun()

# Existing Features
def plot_user_community_activity():
    data = [{"Username": user.username, "Communities Joined": len(user.communities)} 
            for user in st.session_state.db.users.values()]
    df = pd.DataFrame(data)
    if not df.empty:
        fig = px.bar(df, x="Username", y="Communities Joined", title="User Community Activity")
        st.plotly_chart(fig)
    else:
        st.info("No data to display.")

def file_upload():
    uploaded = st.file_uploader("Upload Study Material", type=["pdf", "txt", "docx"])
    if uploaded:
        st.success(f"File uploaded: {uploaded.name}")
        if uploaded.type == "text/plain":
            try:
                content = uploaded.getvalue().decode("utf-8")
                st.text_area("File Content", content, height=200)
                if st.button("Summarize Text"):
                    is_premium = st.session_state.user.is_premium if "user" in st.session_state else False
                    summary = summarize_text(content, is_premium)
                    if summary:
                        st.markdown(f"**Summary:** {summary}")
            except UnicodeDecodeError:
                st.warning("Unable to decode text file.")
        elif uploaded.type == "application/pdf":
            content = process_pdf(uploaded)
            if content and st.button("Summarize PDF"):
                is_premium = st.session_state.user.is_premium if "user" in st.session_state else False
                summary = summarize_text(content, is_premium)
                if summary:
                    st.markdown(f"**Summary:** {summary}")

def rate_post(post_id):
    rating = st.slider("Rate this post", 1, 5, key=f"post_rating_{post_id}")
    st.session_state.db.add_rating(post_id, rating)
    st.success(f"Rated post with {rating} stars.")

def rate_community(community_id):
    rating = st.slider("Rate this community", 1, 5, key=f"community_rating_{community_id}")
    st.session_state.db.add_community_rating(community_id, rating)
    st.success(f"Rated community with {rating} stars.")

def index_posts():
    schema = Schema(post_id=ID(stored=True), content=TEXT(stored=True))
    index_dir = "index"
    if not os.path.exists(index_dir):
        os.mkdir(index_dir)
    if not exists_in(index_dir):
        ix = create_in(index_dir, schema)
    else:
        ix = open_dir(index_dir)
    writer = ix.writer()
    for post in st.session_state.db.posts:
        writer.add_document(post_id=post.post_id, content=post.content)
    writer.commit()

def search_posts(query_string):
    try:
        if not os.path.exists("index") or not exists_in("index"):
            index_posts()
        ix = open_dir(index_dir)
        with ix.searcher() as searcher:
            query = QueryParser("content", ix.schema).parse(query_string)
            results = searcher.search(query)
            if results:
                for result in results:
                    st.markdown(f"<div class='card'>Post ID: {result['post_id']}<br>Content: {result['content']}</div>", 
                               unsafe_allow_html=True)
            else:
                st.info("No matching posts found.")
    except Exception as e:
        st.warning(f"Search unavailable: {str(e)}. Reindexing posts...")
        index_posts()

# UI Functions
def enhanced_header(title, icon=""):
    st.markdown(
        f"""
        <div style='text-align: center;'>
            <h2 style='color: #2E8B57;'>{icon} {title} {icon}</h2>
            <hr style='border-top: 3px solid #2E8B57;'>
        </div>
        """,
        unsafe_allow_html=True
    )

def display_post(post, db, user):
    user_obj = db.get_user(post.user_id) or FreeUser("unknown", "Unknown", "unknown@example.com")
    community = db.communities.get(post.community_id, Community("unknown", "Unknown", "unknown"))
    rating = db.posts_ratings.get(post.post_id, "Not rated")
    like_count = len(post.likes)
    st.markdown(
        f"""
        <div class='card'>
            <strong>{user_obj.username}</strong> in <em>{community.name}</em><br>
            <small>{post.timestamp.strftime('%Y-%m-%d %H:%M')}</small><br>
            <p>{post.content}</p>
            <span class='badge'>{post.tag}</span><br>
            <small>Rating: {rating}/5 | Likes: {like_count}</small>
        </div>
        """,
        unsafe_allow_html=True
    )
    if user:
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Like", key=f"like_{post.post_id}"):
                db.add_like(post.post_id, user.user_id)
                st.rerun()
        with col2:
            with st.form(f"comment_form_{post.post_id}"):
                comment = st.text_input("Add a comment", key=f"comment_{post.post_id}")
                submit = st.form_submit_button("Comment")
                if submit and comment:
                    db.add_comment(post.post_id, user.user_id, comment)
                    st.rerun()
        for comment in post.comments:
            commenter = db.get_user(comment["user_id"]) or FreeUser("unknown", "Unknown", "unknown@example.com")
            st.markdown(
                f"<div class='card' style='margin-left: 20px;'><small>{commenter.username}: {comment['content']} "
                f"({comment['timestamp'].strftime('%Y-%m-%d %H:%M')})</small></div>",
                unsafe_allow_html=True
            )

def display_community(community, members_count):
    creator = st.session_state.db.get_user(community.creator_id) or FreeUser("unknown", "Unknown", "unknown@example.com")
    rating = st.session_state.db.communities_ratings.get(community.community_id, "Not rated")
    st.markdown(
        f"<div class='card'>**{community.name}** by *{creator.username}* ({members_count} members) | Rating: {rating}/5</div>",
        unsafe_allow_html=True
    )

def display_study_room(room):
    creator = st.session_state.db.get_user(room.creator_id) or FreeUser("unknown", "Unknown", "unknown@example.com")
    st.markdown(
        f"""
        <div class='card'>
            <strong>{room.name}</strong> | Created by {creator.username}<br>
            Scheduled: {room.scheduled_time.strftime('%Y-%m-%d %H:%M')}<br>
            Meeting Key: {room.meeting_key}
        </div>
        """,
        unsafe_allow_html=True
    )

def display_profile(user, db):
    st.subheader("Edit Profile")
    with st.form("profile_form"):
        username = st.text_input("Username", value=user.username)
        email = st.text_input("Email", value=user.email)
        bio = st.text_area("Bio", value=user.bio or "")
        profile_pic = st.file_uploader("Profile Picture", type=["png", "jpg", "jpeg"])
        submit = st.form_submit_button("Update Profile")
        if submit:
            if not username or not email:
                st.error("Username and email are required!")
            else:
                profile_picture = user.profile_picture
                if profile_pic:
                    profile_picture = base64.b64encode(profile_pic.read()).decode()
                new_user = PremiumUser(user.user_id, username, email, bio, profile_picture) if user.is_premium else \
                           FreeUser(user.user_id, username, email, bio, profile_picture)
                new_user.communities = user.communities
                db.update_user(new_user)
                st.session_state.user = new_user
                st.success("Profile updated!")
                st.rerun()

    st.subheader("Profile Details")
    profile_pic_html = f"<img src='data:image/png;base64,{user.profile_picture}' class='profile-pic'>" if user.profile_picture else \
                       "<div style='width:100px;height:100px;border-radius:50%;background:#ddd;'></div>"
    st.markdown(
        f"""
        <div class='card'>
            {profile_pic_html}
            <h3>{user.username}</h3>
            <p><strong>Email:</strong> {user.email}</p>
            <p><strong>Bio:</strong> {user.bio or 'No bio yet'}</p>
            <p><strong>Account Type:</strong> {'Premium ✨' if user.is_premium else 'Free'}</p>
            <p><strong>Communities:</strong> {len(user.communities)}</p>
        </div>
        """,
        unsafe_allow_html=True
    )
    badges = db.badges.get(user.user_id, [])
    if badges:
        st.subheader("Badges")
        for badge in badges:
            st.markdown(
                f"<span class='badge'>{badge.name} ({badge.timestamp.strftime('%Y-%m-%d')})</span>",
                unsafe_allow_html=True
            )
    posts = [p for p in db.posts if p.user_id == user.user_id]
    if posts:
        st.subheader("Your Posts")
        for post in sorted(posts, key=lambda x: x.timestamp, reverse=True):
            display_post(post, db, user)

# Main App
def main():
    db = st.session_state.db
    user = st.session_state.get("user")

    # Theme Toggle
    if "theme" not in st.session_state:
        st.session_state.theme = "light"
    if st.sidebar.button("Toggle Dark Mode"):
        st.session_state.theme = "dark" if st.session_state.theme == "light" else "light"
    if st.session_state.theme == "dark":
        st.markdown("<style>.main { background: #1a1a1a; } .stMarkdown, .stText { color: #f5f5f5; }</style>", 
                    unsafe_allow_html=True)

    # Login/Signup
    if not user:
        st.sidebar.subheader("Login / Signup")
        with st.sidebar.form("auth_form"):
            username = st.text_input("Username")
            email = st.text_input("Email")
            is_premium = st.checkbox("Premium Account")
            submit = st.form_submit_button("Login / Signup")
            if submit:
                if not username or not email:
                    st.error("Username and email are required!")
                else:
                    try:
                        user_id = str(uuid.uuid4())
                        user = PremiumUser(user_id, username, email) if is_premium else FreeUser(user_id, username, email)
                        db.add_user(user)
                        st.session_state.user = user
                        st.success(f"Welcome, {username}!")
                        st.rerun()
                    except ValueError as e:
                        st.error(str(e))
    else:
        st.sidebar.write(f"Logged in as: {user.username}")
        if st.sidebar.button("Logout"):
            del st.session_state.user
            st.rerun()

    st.sidebar.image("https://img.icons8.com/fluency/96/bee.png", width=80)
    menu = ["🏠 Home", "📅 Communities", "🚀 Explore", "🤝 Profile", "🎓 Study Rooms", 
            "🌟 Premium", "📄 Posts", "⏰ Timer", "📋 Tasks", "🏆 Leaderboard", "💬 Messages"]
    choice = st.sidebar.selectbox("Navigate", menu)

    if choice == "🏠 Home":
        enhanced_header("StudyHive: Ultimate Student Hub", "🐝")
        st.markdown("<p style='text-align:center'>Connect, Study, and Thrive with peers worldwide!</p>", 
                    unsafe_allow_html=True)
        col1, col2 = st.columns(2)
        with col1:
            plot_user_community_activity()
        with col2:
            leaderboard()
        if user:
            display_notifications(user.user_id)

    elif choice == "📅 Communities":
        enhanced_header("Communities", "🛋")
        if user:
            with st.container():
                st.subheader("Create a Community")
                name = st.text_input("Community Name")
                if st.button("Create"):
                    if not name:
                        st.error("Community name cannot be empty!")
                    elif name in [c.name for c in db.communities.values()]:
                        st.error("Community name already taken!")
                    else:
                        cid = str(uuid.uuid4())
                        db.add_community(Community(cid, name, user.user_id))
                        user.join_community(cid)
                        db.communities[cid].members.append(user.user_id)
                        db.award_badge(user.user_id, "Community Leader")
                        st.success("Community created!")
                        try:
                            requests.post("http://localhost:8000/notify", 
                                        json={"user_id": "", "message": f"New community: {name}"})
                        except Exception as e:
                            st.warning(f"Failed to send notification: {str(e)}")

            with st.container():
                st.subheader("Join Community")
                options = [(c.community_id, c.name) for c in db.communities.values() 
                          if c.community_id not in user.communities]
                if options:
                    cid = st.selectbox("Choose", [o[0] for o in options], 
                                      format_func=lambda x: next(o[1] for o in options if o[0] == x))
                    if st.button("Join"):
                        user.join_community(cid)
                        db.communities[cid].members.append(user.user_id)
                        st.success("Joined community!")
                else:
                    st.info("No communities to join.")

            with st.container():
                st.subheader("Rate Community")
                options = [(c.community_id, c.name) for c in db.communities.values() 
                          if c.community_id in user.communities]
                if options:
                    cid = st.selectbox("Select Community to Rate", [o[0] for o in options], 
                                      format_func=lambda x: next(o[1] for o in options if o[0] == x), 
                                      key="rate_community")
                    rate_community(cid)

            st.subheader("My Communities")
            for cid in user.communities:
                community = db.communities.get(cid)
                if community:
                    display_community(community, len(community.members))
        else:
            st.warning("Please log in to manage communities.")

    elif choice == "🚀 Explore":
        enhanced_header("Explore Posts", "📰")
        if db.posts:
            for post in sorted(db.posts, key=lambda x: x.timestamp, reverse=True):
                display_post(post, db, user)
                if user:
                    rate_post(post.post_id)
        else:
            st.info("No posts yet.")
        search_posts(st.text_input("Search Posts:"))

    elif choice == "🤝 Profile":
        enhanced_header("My Profile", "👤")
        if user:
            display_profile(user, db)
        else:
            st.error("Please log in.")

    elif choice == "🎓 Study Rooms":
        enhanced_header("Study Rooms", "📖")
        if user:
            with st.container():
                st.subheader("Schedule a Room")
                name = st.text_input("Room Name")
                date = st.date_input("Date")
                time = st.time_input("Time")
                if st.button("Schedule"):
                    if not name or not date or not time:
                        st.error("All fields required!")
                    else:
                        dt = datetime.combine(date, time)
                        if dt < datetime.now():
                            st.error("Cannot schedule in the past!")
                        else:
                            rid = str(uuid.uuid4())
                            meeting_key = str(uuid.uuid4())[:8]
                            db.add_study_room(StudyRoom(rid, name, user.user_id, dt, meeting_key))
                            db.award_badge(user.user_id, "Study Planner")
                            st.success(f"Room scheduled! Meeting Key: {meeting_key}")
                            try:
                                requests.post("http://localhost:8000/notify", 
                                            json={"user_id": "", "message": f"New study room: {name} (Key: {meeting_key})"})
                            except Exception as e:
                                st.warning(f"Failed to send notification: {str(e)}")

            with st.container():
                st.subheader("Join Room")
                meeting_key = st.text_input("Enter Meeting Key")
                if st.button("Join"):
                    room = next((r for r in db.study_rooms.values() if r.meeting_key == meeting_key), None)
                    if room:
                        if user.user_id not in room.participants:
                            room.participants.append(user.user_id)
                            st.success(f"Joined room: {room.name}")
                        st.warning("Video calls require HTTPS. Run the app with SSL certificates to enable video.")
                    else:
                        st.error("Invalid meeting key!")

            st.subheader("Upcoming Rooms")
            for room in sorted(db.study_rooms.values(), key=lambda x: x.scheduled_time):
                display_study_room(room)
                if user and user.user_id in room.participants:
                    st.subheader(f"Tasks for {room.name}")
                    task_manager(user.user_id, room.room_id)
                    if st.button(f"Join Video Call: {room.name}", key=f"video_{room.room_id}"):
                        st.warning("Video calls require HTTPS. Run the app with SSL certificates to enable video.")
        else:
            st.warning("Please log in.")

    elif choice == "🌟 Premium":
        enhanced_header("Upgrade to Premium", "🌟")
        if user:
            if not user.is_premium:
                st.markdown(
                    "<div class='card'>**Premium Benefits:**<br>- Ad-Free<br>- Longer AI Summaries<br>"
                    "- Exclusive Rooms<br>- Cost: $6.99/month</div>",
                    unsafe_allow_html=True
                )
                with st.form("payment_form"):
                    amount = st.number_input("Amount ($)", min_value=0.0, value=6.99, step=0.01)
                    submit = st.form_submit_button("Subscribe")
                    if submit:
                        user_id = user.user_id
                        new_user = PremiumUser(user_id, user.username, user.email, user.bio, user.profile_picture)
                        new_user.communities = user.communities
                        db.users[user_id] = new_user
                        st.session_state.user = new_user
                        st.success(f"Processed ${amount:.2f}. Upgraded to Premium!")
            else:
                st.success("You're a Premium Member!")
        else:
            st.warning("Please log in.")

    elif choice == "📄 Posts":
        enhanced_header("Create a Post", "📄")
        if user:
            if user.communities:
                with st.form("post_form"):
                    options = [(c.community_id, c.name) for c in db.communities.values() 
                              if c.community_id in user.communities]
                    cid = st.selectbox("Community", [o[0] for o in options], 
                                      format_func=lambda x: next(o[1] for o in options if o[0] == x),
                                      key="post_community_select")
                    tag = st.selectbox("Tag", ["StudyTip", "Motivation", "Question", "Experience"], key="post_tag")
                    content = st.text_area("Content", key="post_content")
                    submit = st.form_submit_button("Post")
                    if submit:
                        if not content:
                            st.error("Content cannot be empty!")
                        else:
                            pid = str(uuid.uuid4())
                            db.add_post(Post(pid, content, user.user_id, cid, tag))
                            index_posts()
                            st.success("Posted!")
                            try:
                                community_name = next(o[1] for o in options if o[0] == cid)
                                requests.post("http://localhost:8000/notify", 
                                            json={"user_id": "", 
                                                  "message": f"New post in community {community_name}"})
                            except Exception as e:
                                st.warning(f"Failed to send notification: {str(e)}")
            else:
                st.info("Join a community first!")
        else:
            st.warning("Please log in.")

    elif choice == "⏰ Timer":
        enhanced_header("Study Timer", "⏰")
        if user:
            study_timer()
        else:
            st.warning("Please log in.")

    elif choice == "📋 Tasks":
        enhanced_header("Task Manager", "📋")
        if user:
            task_manager(user.user_id)
        else:
            st.warning("Please log in.")

    elif choice == "🏆 Leaderboard":
        enhanced_header("Leaderboard", "🏆")
        leaderboard()

    elif choice == "💬 Messages":
        enhanced_header("Messages", "💬")
        if user:
            receiver_username = st.text_input("Receiver Username")
            receiver = next((u for u in db.users.values() 
                            if u.username.lower() == receiver_username.lower()), None)
            if receiver:
                display_chat(user, receiver.user_id)
                asyncio.run(chat_client(user.user_id, receiver.user_id))
            else:
                st.info("Enter a username to start chatting.")
        else:
            st.warning("Please log in.")

if __name__ == "__main__":
    main()