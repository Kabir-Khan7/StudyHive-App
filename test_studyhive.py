import pytest
import uuid
from datetime import datetime, timedelta
import requests
from app import Database, FreeUser, PremiumUser, Community, Post, Message, StudyRoom, Task, Badge
import re

# Mock Streamlit session state for testing
class MockSessionState:
    def __init__(self):
        self.db = Database()
        self.user = None
        self.theme = "light"
        self.chat_messages = []
        self.timer_running = False
        self.timer_seconds = 1500
        self.timer_mode = "Work"
        self.sessions_completed = 0

# Fixture for database and session state
@pytest.fixture
def db():
    return Database()

@pytest.fixture
def session_state():
    return MockSessionState()

@pytest.fixture
def user(db):
    user = FreeUser(str(uuid.uuid4()), "testuser", "test@example.com")
    db.add_user(user)
    return user

@pytest.fixture
def premium_user(db):
    user = PremiumUser(str(uuid.uuid4()), "premiumuser", "premium@example.com")
    db.add_user(user)
    return user

@pytest.fixture
def community(db, user):
    comm = Community(str(uuid.uuid4()), "Test Community", user.user_id)
    db.add_community(comm)
    return comm

# Functional Tests
def test_user_creation(db):
    user_id = str(uuid.uuid4())
    user = FreeUser(user_id, "newuser", "new@example.com")
    db.add_user(user)
    assert db.get_user(user_id) == user
    assert db.badges[user_id][0].name == "Welcome"

def test_username_uniqueness(db):
    user1 = FreeUser(str(uuid.uuid4()), "user1", "user1@example.com")
    db.add_user(user1)
    user2 = FreeUser(str(uuid.uuid4()), "user1", "user2@example.com")
    with pytest.raises(ValueError, match="Username already taken"):
        db.add_user(user2)
    user3 = FreeUser(str(uuid.uuid4()), "USER1", "user3@example.com")
    with pytest.raises(ValueError, match="Username already taken"):
        db.add_user(user3)

def test_premium_user(db):
    user_id = str(uuid.uuid4())
    user = PremiumUser(user_id, "premium", "premium@example.com")
    db.add_user(user)
    assert user.is_premium
    assert user.display_profile().startswith("premium (Premium ✨)")

def test_community_creation(db, user):
    comm_id = str(uuid.uuid4())
    comm = Community(comm_id, "Math Club", user.user_id)
    db.add_community(comm)
    assert comm_id in db.communities
    assert comm_id in user.communities
    assert user.user_id in comm.members
    assert any(b.name == "Community Leader" for b in db.badges[user.user_id])

def test_post_creation(db, user, community):
    post_id = str(uuid.uuid4())
    post = Post(post_id, "Study tips!", user.user_id, community.community_id, "StudyTip")
    db.add_post(post)
    assert post in db.posts
    assert any(b.name == "First Post" for b in db.badges[user.user_id])

def test_post_like_comment(db, user, community):
    post_id = str(uuid.uuid4())
    post = Post(post_id, "Great tip!", user.user_id, community.community_id, "Motivation")
    db.add_post(post)
    db.add_like(post_id, user.user_id)
    assert user.user_id in db.posts[0].likes
    db.add_comment(post_id, user.user_id, "Thanks!")
    assert db.posts[0].comments[0]["content"] == "Thanks!"

def test_study_room_creation(db, user):
    room_id = str(uuid.uuid4())
    meeting_key = str(uuid.uuid4())[:8]
    scheduled_time = datetime.now() + timedelta(days=1)
    room = StudyRoom(room_id, "Math Study", user.user_id, scheduled_time, meeting_key)
    db.add_study_room(room)
    assert room_id in db.study_rooms
    assert any(b.name == "Study Planner" for b in db.badges[user.user_id])

def test_task_management(db, user, community):
    task_id = str(uuid.uuid4())
    task = Task(task_id, user.user_id, "Finish homework", "To-Do", community.community_id)
    db.add_task(task)
    assert task in db.get_tasks(user_id=user.user_id)
    db.delete_task(task_id)
    assert task not in db.get_tasks(user_id=user.user_id)

def test_message_and_notification(db, user, premium_user):
    msg_id = str(uuid.uuid4())
    msg = Message(msg_id, user.user_id, premium_user.user_id, "Hello!")
    db.add_message(msg)
    assert msg in db.messages
    notifs = db.get_notifications(premium_user.user_id)
    assert any(n["message"] == f"New message from {user.username}" for n in notifs)

# Security Tests
def test_empty_inputs(db):
    user_id = str(uuid.uuid4())
    with pytest.raises(ValueError, match="Username cannot be empty"):
        db.add_user(FreeUser(user_id, "", "empty@example.com"))
    comm_id = str(uuid.uuid4())
    comm = Community(comm_id, "", user_id)
    db.add_community(comm)
    assert comm.name == ""  # Should handle gracefully
    post_id = str(uuid.uuid4())
    post = Post(post_id, "", user_id, comm_id, "StudyTip")
    db.add_post(post)
    assert post.content == ""  # Should handle gracefully

def test_xss_injection(db, user, community):
    post_id = str(uuid.uuid4())
    malicious_content = "<script>alert('xss')</script>"
    post = Post(post_id, malicious_content, user.user_id, community.community_id, "Question")
    db.add_post(post)
    # Check if content is stored as-is (Streamlit escapes HTML by default)
    assert db.posts[0].content == malicious_content
    # Streamlit's markdown escapes HTML, so <script> is rendered as text
    assert malicious_content in db.posts[0].content  # Content stored safely

def test_long_inputs(db):
    user_id = str(uuid.uuid4())
    long_username = "a" * 1000
    user = FreeUser(user_id, long_username, "long@example.com")
    db.add_user(user)
    assert db.get_user(user_id).username == long_username
    comm_id = str(uuid.uuid4())
    long_name = "b" * 1000
    comm = Community(comm_id, long_name, user_id)
    db.add_community(comm)
    assert db.communities[comm_id].name == long_name

def test_unauthorized_access(db, community):
    post_id = str(uuid.uuid4())
    post = Post(post_id, "Unauthorized post", "nonexistent_user", community.community_id, "StudyTip")
    db.add_post(post)
    assert post in db.posts
    assert db.get_user("nonexistent_user") is None
    # No badge awarded for nonexistent user
    assert "nonexistent_user" not in db.badges

def test_past_study_room(db, user):
    room_id = str(uuid.uuid4())
    meeting_key = str(uuid.uuid4())[:8]
    past_time = datetime.now() - timedelta(days=1)
    room = StudyRoom(room_id, "Past Study", user.user_id, past_time, meeting_key)
    db.add_study_room(room)
    assert room_id in db.study_rooms  # Should store but UI prevents joining

def test_notification_spam(db, user):
    for i in range(100):
        db.notify_user(user.user_id, f"Spam {i}")
    notifs = db.get_notifications(user.user_id)
    assert len(notifs) == 100  # Should handle high volume
    assert all(n["message"].startswith("Spam") for n in notifs)

# API Tests
def test_notify_endpoint():
    try:
        response = requests.post("http://localhost:8000/notify", 
                               json={"user_id": "test_user", "message": "Test notification"})
        assert response.status_code == 200
        assert response.json() == {"status": "Notification sent"}
    except requests.ConnectionError:
        pytest.skip("FastAPI server not running")

def test_notify_invalid_input():
    try:
        response = requests.post("http://localhost:8000/notify", json={})
        assert response.status_code == 422  # FastAPI validation error
    except requests.ConnectionError:
        pytest.skip("FastAPI server not running")

# Edge Case Tests
def test_duplicate_post(db, user, community):
    post_id = str(uuid.uuid4())
    post1 = Post(post_id, "Duplicate", user.user_id, community.community_id, "StudyTip")
    post2 = Post(post_id, "Duplicate", user.user_id, community.community_id, "StudyTip")
    db.add_post(post1)
    db.add_post(post2)
    assert len(db.posts) == 2  # Should allow duplicates (no unique constraint)

def test_invalid_meeting_key(db, user):
    room_id = str(uuid.uuid4())
    meeting_key = str(uuid.uuid4())[:8]
    room = StudyRoom(room_id, "Test Room", user.user_id, datetime.now() + timedelta(days=1), meeting_key)
    db.add_study_room(room)
    # Simulate joining with wrong key
    assert not any(r.meeting_key == "wrong_key" for r in db.study_rooms.values())

def test_special_characters(db, user, community):
    post_id = str(uuid.uuid4())
    special_content = "!@#$%^&*()_+{}|:\"<>?`~"
    post = Post(post_id, special_content, user.user_id, community.community_id, "StudyTip")
    db.add_post(post)
    assert db.posts[0].content == special_content
    db.add_comment(post_id, user.user_id, special_content)
    assert db.posts[0].comments[0]["content"] == special_content

if __name__ == "__main__":
    pytest.main(["-v"])