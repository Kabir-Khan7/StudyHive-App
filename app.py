import streamlit as st
import uuid
from abc import ABC, abstractmethod
from datetime import datetime
import pandas as pd

# Simulated database (in-memory)
class Database:
    def __init__(self):
        self.users = {}  # {user_id: User}
        self.communities = {}  # {community_id: Community}
        self.posts = []  # List of Post objects
        self.messages = []  # List of Message objects
        self.study_rooms = {}  # {room_id: StudyRoom}
        self.badges = {}  # {user_id: [Badge]}

    def add_user(self, user):
        self.users[user.user_id] = user
        self.badges[user.user_id] = []

    def get_user(self, user_id):
        return self.users.get(user_id)

    def add_community(self, community):
        self.communities[community.community_id] = community

    def add_post(self, post):
        self.posts.append(post)
        # Award badge for first post
        user_id = post.user_id
        if not any(p.user_id == user_id for p in self.posts[:-1]):
            self.badges[user_id].append(Badge(str(uuid.uuid4()), "First Post", user_id))

    def add_message(self, message):
        self.messages.append(message)

    def add_study_room(self, room):
        self.study_rooms[room.room_id] = room

    def award_badge(self, user_id, badge_name):
        badge = Badge(str(uuid.uuid4()), badge_name, user_id)
        self.badges[user_id].append(badge)

# Abstract base class for Users
class User(ABC):
    def __init__(self, user_id, username, email):
        self.user_id = user_id
        self.username = username
        self.email = email
        self.communities = []  # List of community_ids
        self.is_premium = False

    @abstractmethod
    def display_profile(self):
        pass

    def join_community(self, community_id):
        if community_id not in self.communities:
            self.communities.append(community_id)

# Concrete user classes
class FreeUser(User):
    def display_profile(self):
        return f"{self.username} (Free) | Communities: {len(self.communities)}"

class PremiumUser(User):
    def __init__(self, user_id, username, email):
        super().__init__(user_id, username, email)
        self.is_premium = True

    def display_profile(self):
        return f"{self.username} (Premium ✨) | Communities: {len(self.communities)} | Ad-Free"

# Community class
class Community:
    def __init__(self, community_id, name, creator_id):
        self.community_id = community_id
        self.name = name
        self.creator_id = creator_id
        self.members = [creator_id]  # List of user_ids

# Post class
class Post:
    def __init__(self, post_id, content, user_id, community_id, tag):
        self.post_id = post_id
        self.content = content
        self.user_id = user_id
        self.community_id = community_id
        self.tag = tag
        self.timestamp = datetime.now()

# Message class
class Message:
    def __init__(self, message_id, sender_id, receiver_id, content, community_id=None):
        self.message_id = message_id
        self.sender_id = sender_id
        self.receiver_id = receiver_id  # None for community messages
        self.content = content
        self.community_id = community_id
        self.timestamp = datetime.now()

# StudyRoom class
class StudyRoom:
    def __init__(self, room_id, name, creator_id, scheduled_time):
        self.room_id = room_id
        self.name = name
        self.creator_id = creator_id
        self.scheduled_time = scheduled_time
        self.participants = [creator_id]  # List of user_ids

# Badge class
class Badge:
    def __init__(self, badge_id, name, user_id):
        self.badge_id = badge_id
        self.name = name
        self.user_id = user_id
        self.timestamp = datetime.now()

# Abstract PaymentProcessor
class PaymentProcessor(ABC):
    @abstractmethod
    def process_payment(self, amount):
        pass

class DummyPaymentProcessor(PaymentProcessor):
    def process_payment(self, amount):
        return f"Processed payment of ${amount:.2f} (Dummy)"

# Initialize database
if "db" not in st.session_state:
    st.session_state.db = Database()

# Streamlit App
def main():
    st.set_page_config(page_title="StudyHive", page_icon="🐝")
    st.title("StudyHive: Connect, Study, Thrive 🐝")
    st.markdown("Join academic communities, share posts, chat with peers, and study together!")

    # Sidebar navigation
    menu = ["Home", "Signup", "Login", "Profile", "Communities", "Study Rooms", "Premium"]
    choice = st.sidebar.selectbox("Navigate", menu, help="Choose an option to explore StudyHive")

    # Home page
    if choice == "Home":
        st.header("Welcome to StudyHive")
        st.write("A platform for students to connect, collaborate, and succeed.")
        if "user" in st.session_state:
            st.success(f"Logged in as: {st.session_state.user.display_profile()}")
        else:
            st.info("Please sign up or log in to get started!")

    # Signup
    elif choice == "Signup":
        st.header("Sign Up")
        with st.form("signup_form"):
            username = st.text_input("Username", placeholder="Choose a unique username")
            email = st.text_input("Email", placeholder="Enter your student email")
            user_type = st.selectbox("Account Type", ["Free", "Premium"], help="Premium offers ad-free and priority features")
            submit = st.form_submit_button("Sign Up")
            if submit:
                username = username.lower()  # Normalize to lowercase
                if not username or not email:
                    st.error("Please fill in all fields!")
                elif username in [u.username.lower() for u in st.session_state.db.users.values()]:
                    st.error("Username already taken!")
                else:
                    user_id = str(uuid.uuid4())
                    user = PremiumUser(user_id, username, email) if user_type == "Premium" else FreeUser(user_id, username, email)
                    st.session_state.db.add_user(user)
                    st.success(f"Account created for {username}! Please log in.")

    # Login
    elif choice == "Login":
        st.header("Login")
        with st.form("login_form"):
            username = st.text_input("Username", placeholder="Enter your username")
            submit = st.form_submit_button("Login")
            if submit:
                username = username.lower()  # Normalize to lowercase
                if not username:
                    st.error("Please enter a username!")
                else:
                    user = next((u for u in st.session_state.db.users.values() if u.username.lower() == username), None)
                    if user:
                        st.session_state.user = user
                        st.success(f"Welcome back, {user.username}!")
                    else:
                        st.error("Username not found!")

    # Profile (requires login)
    elif choice == "Profile":
        if "user" in st.session_state:
            user = st.session_state.user
            st.header("Your Profile")
            st.markdown(f"**{user.display_profile()}**")
            
            # Display badges
            badges = st.session_state.db.badges.get(user.user_id, [])
            if badges:
                st.subheader("Your Badges")
                badge_names = [f"{b.name} (Earned: {b.timestamp.strftime('%Y-%m-%d %H:%M')})" for b in badges]
                st.write(", ".join(badge_names))
            else:
                st.write("No badges yet! Start posting or creating communities to earn some.")

            # Create post
            st.subheader("Share a Post")
            with st.form("post_form"):
                community_options = [(c.community_id, c.name) for c in st.session_state.db.communities.values() if user.user_id in c.members]
                community_id = st.selectbox("Community", [c[0] for c in community_options], format_func=lambda x: next(c[1] for c in community_options if c[0] == x)) if community_options else None
                tag = st.selectbox("Tag", ["StudyTip", "Motivation", "Question", "Experience"], help="Categorize your post")
                content = st.text_area("Post Content", placeholder="Share your thoughts or tips...")
                submit = st.form_submit_button("Post")
                if submit:
                    if not community_id:
                        st.error("Join a community first!")
                    elif not content:
                        st.error("Post content cannot be empty!")
                    else:
                        post_id = str(uuid.uuid4())
                        post = Post(post_id, content, user.user_id, community_id, tag)
                        st.session_state.db.add_post(post)
                        st.success("Post shared successfully!")

            # Send message
            st.subheader("Send a Message")
            with st.form("message_form"):
                receiver_username = st.text_input("Receiver Username (optional for community)", placeholder="Leave blank for community message")
                community_options = [(c.community_id, c.name) for c in st.session_state.db.communities.values() if user.user_id in c.members]
                community_id = st.selectbox("Community (optional)", ["None"] + [c[0] for c in community_options], format_func=lambda x: next(c[1] for c in community_options if c[0] == x) if x != "None" else "None")
                content = st.text_area("Message", placeholder="Type your message...")
                submit = st.form_submit_button("Send")
                if submit:
                    if not content:
                        st.error("Message cannot be empty!")
                    else:
                        receiver = next((u for u in st.session_state.db.users.values() if u.username.lower() == receiver_username.lower()), None) if receiver_username else None
                        if receiver_username and not receiver:
                            st.error("Receiver not found!")
                        else:
                            message_id = str(uuid.uuid4())
                            receiver_id = receiver.user_id if receiver else None
                            community_id = community_id if community_id != "None" else None
                            message = Message(message_id, user.user_id, receiver_id, content, community_id)
                            st.session_state.db.add_message(message)
                            st.success("Message sent!")

            # Display private messages
            st.subheader("Your Private Messages")
            private_messages = [m for m in st.session_state.db.messages if m.receiver_id == user.user_id]
            if private_messages:
                for message in private_messages:
                    sender = st.session_state.db.get_user(message.sender_id)
                    with st.expander(f"From {sender.username} ({message.timestamp.strftime('%Y-%m-%d %H:%M')})"):
                        st.write(message.content)
            else:
                st.write("No private messages yet!")
        else:
            st.error("Please log in to view your profile!")

    # Communities
    elif choice == "Communities":
        st.header("Communities")
        
        # Create community
        if "user" in st.session_state:
            st.subheader("Create a Community")
            with st.form("community_form"):
                name = st.text_input("Community Name", placeholder="e.g., CS101 Study Group")
                submit = st.form_submit_button("Create")
                if submit:
                    if not name:
                        st.error("Community name cannot be empty!")
                    elif name in [c.name for c in st.session_state.db.communities.values()]:
                        st.error("Community name already taken!")
                    else:
                        community_id = str(uuid.uuid4())
                        community = Community(community_id, name, st.session_state.user.user_id)
                        st.session_state.db.add_community(community)
                        st.session_state.user.join_community(community_id)
                        st.session_state.db.award_badge(st.session_state.user.user_id, "Community Leader")
                        st.success(f"Created community: {name}")

        # Join community
        st.subheader("Join a Community")
        available_communities = [(c.community_id, c.name) for c in st.session_state.db.communities.values()]
        if available_communities:
            community_id = st.selectbox("Select Community", [c[0] for c in available_communities], format_func=lambda x: next(c[1] for c in available_communities if c[0] == x))
            if st.button("Join Community"):
                if "user" in st.session_state:
                    if community_id in st.session_state.user.communities:
                        st.warning("You're already a member of this community!")
                    else:
                        st.session_state.user.join_community(community_id)
                        st.session_state.db.communities[community_id].members.append(st.session_state.user.user_id)
                        st.success(f"Joined {st.session_state.db.communities[community_id].name}!")
                else:
                    st.error("Please log in to join communities!")

        # View community posts and messages
        if available_communities:
            st.subheader("Explore Communities")
            selected_community = st.selectbox("Choose Community", [c[0] for c in available_communities], format_func=lambda x: next(c[1] for c in available_communities if c[0] == x), key="community_view")
            community = st.session_state.db.communities[selected_community]
            
            # Display posts
            st.markdown(f"### Posts in {community.name}")
            posts = [p for p in st.session_state.db.posts if p.community_id == selected_community]
            if posts:
                post_data = [{
                    "Username": st.session_state.db.get_user(p.user_id).username,
                    "Tag": p.tag,
                    "Content": p.content,
                    "Posted": p.timestamp.strftime("%Y-%m-%d %H:%M")
                } for p in posts]
                st.dataframe(pd.DataFrame(post_data), use_container_width=True)
            else:
                st.write("No posts yet. Be the first to share!")

            # Display messages
            st.markdown(f"### Messages in {community.name}")
            messages = [m for m in st.session_state.db.messages if m.community_id == selected_community]
            if messages:
                for message in messages:
                    sender = st.session_state.db.get_user(message.sender_id)
                    with st.expander(f"{sender.username} ({message.timestamp.strftime('%Y-%m-%d %H:%M')})"):
                        st.write(message.content)
            else:
                st.write("No messages yet. Start the conversation!")

    # Study Rooms
    elif choice == "Study Rooms":
        st.header("Study Rooms")
        
        # Create study room
        if "user" in st.session_state:
            st.subheader("Create a Study Room")
            with st.form("study_room_form"):
                name = st.text_input("Room Name", placeholder="e.g., Calculus Study Session")
                scheduled_time = st.text_input("Scheduled Time", placeholder="e.g., 2025-05-15 14:00")
                submit = st.form_submit_button("Create")
                if submit:
                    if not name or not scheduled_time:
                        st.error("Please fill in all fields!")
                    else:
                        room_id = str(uuid.uuid4())
                        room = StudyRoom(room_id, name, st.session_state.user.user_id, scheduled_time)
                        st.session_state.db.add_study_room(room)
                        st.session_state.db.award_badge(st.session_state.user.user_id, "Study Planner")
                        st.success(f"Created study room: {name}")

        # Join study room
        st.subheader("Join a Study Room")
        available_rooms = [(r.room_id, r.name) for r in st.session_state.db.study_rooms.values()]
        if available_rooms:
            room_id = st.selectbox("Select Study Room", [r[0] for r in available_rooms], format_func=lambda x: next(r[1] for r in available_rooms if r[0] == x))
            if st.button("Join Study Room"):
                if "user" in st.session_state:
                    if st.session_state.user.user_id in st.session_state.db.study_rooms[room_id].participants:
                        st.warning("You're already in this study room!")
                    else:
                        st.session_state.db.study_rooms[room_id].participants.append(st.session_state.user.user_id)
                        st.success(f"Joined {st.session_state.db.study_rooms[room_id].name}!")
                else:
                    st.error("Please log in to join study rooms!")

        # View study rooms
        if available_rooms:
            st.subheader("Available Study Rooms")
            room_data = [{
                "Name": r.name,
                "Creator": st.session_state.db.get_user(r.creator_id).username,
                "Scheduled Time": r.scheduled_time,
                "Participants": len(r.participants)
            } for r in st.session_state.db.study_rooms.values()]
            st.dataframe(pd.DataFrame(room_data), use_container_width=True)

    # Premium Subscription
    elif choice == "Premium":
        st.header("Upgrade to Premium")
        st.markdown("Unlock ad-free experience and priority features for just $6.99/month!")
        with st.form("payment_form"):
            amount = st.number_input("Amount ($)", min_value=0.0, value=6.99, step=0.01)
            submit = st.form_submit_button("Subscribe")
            if submit and "user" in st.session_state:
                processor = DummyPaymentProcessor()
                result = processor.process_payment(amount)
                user_id = st.session_state.user.user_id
                old_user = st.session_state.user
                new_user = PremiumUser(user_id, old_user.username, old_user.email)
                new_user.communities = old_user.communities
                st.session_state.db.users[user_id] = new_user
                st.session_state.user = new_user
                st.success(result)
            elif submit:
                st.error("Please log in to upgrade!")

    # Footer
    st.markdown("---")
    st.markdown("StudyHive © 2025 | Connect, Study, Thrive")

if __name__ == "__main__":
    main()