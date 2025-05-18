import pytest
from app import Database, FreeUser, PremiumUser, Community, Post, Message, Task, Badge
import uuid
from datetime import datetime

@pytest.fixture
def db():
    return Database()

def test_user_signup(db):
    user = FreeUser("u1", "testuser", "test@example.com")
    db.add_user(user)
    assert db.get_user("u1") == user
    assert len(db.badges["u1"]) == 1  # Welcome badge
    assert db.badges["u1"][0].name == "Welcome"
    
    # Test duplicate username (case-insensitive)
    with pytest.raises(ValueError, match="Username already taken"):
        db.add_user(FreeUser("u2", "TESTUSER", "test2@example.com"))

def test_premium_user(db):
    user = PremiumUser("u1", "premiumuser", "premium@example.com")
    db.add_user(user)
    assert db.get_user("u1").is_premium
    assert user.display_profile() == "premiumuser (Premium ✨) | Communities: 0 | Ad-Free"

def test_community_creation(db):
    user = FreeUser("u1", "testuser", "test@example.com")
    db.add_user(user)
    comm = Community("c1", "Math Club", "u1")
    db.add_community(comm)
    assert db.communities["c1"] == comm
    assert "c1" in db.get_user("u1").communities
    assert len(comm.members) == 1

def test_post_creation(db):
    user = FreeUser("u1", "testuser", "test@example.com")
    db.add_user(user)
    comm = Community("c1", "Math Club", "u1")
    db.add_community(comm)
    post = Post("p1", "Test post", "u1", "c1", "StudyTip")
    db.add_post(post)
    assert post in db.posts
    assert any(b.name == "First Post" for b in db.badges["u1"])
    assert len(db.badges["u1"]) == 2  # Welcome + First Post

def test_message_sending(db):
    user1 = FreeUser("u1", "testuser1", "test1@example.com")
    user2 = FreeUser("u2", "testuser2", "test2@example.com")
    db.add_user(user1)
    db.add_user(user2)
    msg = Message("m1", "u1", "u2", "Hello!")
    db.add_message(msg)
    assert msg in db.messages
    assert db.messages[0].content == "Hello!"
    assert db.messages[0].sender_id == "u1"
    assert db.messages[0].receiver_id == "u2"

def test_task_management(db):
    user = FreeUser("u1", "testuser", "test@example.com")
    db.add_user(user)
    task = Task("t1", "u1", "Read Ch. 1", "To-Do", room_id="r1")
    db.add_task(task)
    assert task in db.get_tasks(user_id="u1")
    assert db.get_tasks(room_id="r1") == [task]
    
    # Update task
    updated_task = Task("t1", "u1", "Read Ch. 1", "Done", room_id="r1")
    db.add_task(updated_task)
    assert db.get_tasks(user_id="u1")[0].status == "Done"
    
    # Delete task
    db.delete_task("t1")
    assert not db.get_tasks(user_id="u1")