import streamlit as st
from datetime import datetime
import bcrypt
#import json
#import os
import psycopg2
from psycopg2 import sql
from uuid import uuid4
from psycopg2 import Binary
conn = psycopg2.connect("postgresql://postgres:!Re2300135@db.eyjhuatnyozqlxdauqar.supabase.co:5432/postgres")

# --- SESSION STATE INITIALIZATION ---
SESSION_DEFAULTS = {
    "logged_in": False,
    "username": "",
    "videos": [],
    "page": "Home"
}

for key, default in SESSION_DEFAULTS.items():
    if key not in st.session_state:
        st.session_state[key] = default

# PostgreSQL DB config
DB_CONFIG = {
    "host": "db.eyjhuatnyozqlxdauqar.supabase.co",
    "port": 5432,
    "dbname": "postgres",
    "user": "postgres",
    "password": "!Re2300135"
}


def get_connection():
    return psycopg2.connect(**DB_CONFIG)

def save_reaction_to_db(video_id, username, reaction_type):
    try:
        conn = get_connection()
        cur = conn.cursor()

        # First remove existing reaction of this user for this video (if any)
        #cur.execute("""
        #    DELETE FROM public."MAVS_VIDEO_REACTIONS"
         #   WHERE "VIDEO_ID" = %s AND "USER_NAME" = %s
        #""", (video_id, username))

        # Insert new reaction
        cur.execute("""
            INSERT INTO public."MAVS_VIDEO_REACTIONS" (
                "VIDEO_ID", "USER_NAME", "REACTION_TYPE"
            ) VALUES (%s, %s, %s)
        """, (video_id, username, reaction_type))

        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        #st.error(f"Error saving reaction: {e}")
        # Silent fail - log to console but don't show in UI
        print(f"[save_reaction_to_db] Ignored error: {e}")

def save_rating_to_db(video_id, username, rating_value):
    try:
        conn = get_connection()
        cur = conn.cursor()

        # Upsert rating
        cur.execute("""
            INSERT INTO public."MAVS_VIDEO_RATINGS" (
                "VIDEO_ID", "USER_NAME", "RATING"
            ) VALUES (%s, %s, %s)
            ON CONFLICT ("VIDEO_ID", "USER_NAME") DO UPDATE
            SET "RATING" = EXCLUDED."RATING"
        """, (video_id, username, rating_value))

        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        st.error(f"Error saving rating: {e}")

def update_video_avg_rating(video_id):
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT ROUND(AVG("RATING")::numeric, 2)
            FROM public."MAVS_VIDEO_RATINGS"
            WHERE "VIDEO_ID" = %s
        """, (video_id,))
        avg = cur.fetchone()[0] or 0  # default 0 if no ratings yet

        cur.execute("""
            UPDATE public."MAVS_VIDEOS"
            SET "RATING" = %s,
                "MODIFIED_DATE" = CURRENT_DATE,
                "MODIFIED_TIME" = CURRENT_TIME
            WHERE "VIDEO_ID" = %s
        """, (avg, video_id))

        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        st.error(f"Failed to update avg rating: {e}")

def hash_password(password):
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def check_password(password, hashed):
    return bcrypt.checkpw(password.encode(), hashed.encode())

def load_users_from_db():
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""SELECT "USER_NAME", "PASSWORD" FROM public."MAVS_USERS" """)
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return {username: password_hash for username, password_hash in rows}
    except Exception as e:
        st.error(f"Error loading users: {e}")
        return {}

def save_user_to_db(username, password_hash):
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO public."MAVS_USERS" ("USER_NAME", "PASSWORD")
            VALUES (%s, %s)
        """, (username, password_hash))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        st.error(f"Error saving user: {e}")

def show_auth():
    st.title("📺 Welcome to Mavs(CGI GRAM)")
    tabs = st.tabs(["🔐 Login", "📝 Register"])

    with tabs[0]:
        username = st.text_input("Username", key="login_user")
        password = st.text_input("Password", type="password", key="login_pass")
        if st.button("Login"):
            users = load_users_from_db()
            if username in users and check_password(password, users[username]):
                st.session_state.logged_in = True
                st.session_state.username = username
                st.success(f"Welcome, {username}!")
                st.rerun()
            else:
                st.error("Invalid username or password.")

    with tabs[1]:
        new_user = st.text_input("Choose a username", key="reg_user")
        new_pass = st.text_input("Choose a password", type="password", key="reg_pass")
        confirm_pass = st.text_input("Confirm password", type="password", key="reg_conf")
        if st.button("Register"):
            users = load_users_from_db()
            if new_user in users:
                st.warning("Username already exists.")
            elif new_pass != confirm_pass:
                st.warning("Passwords do not match.")
            elif not new_user or not new_pass:
                st.warning("Username and password cannot be empty.")
            else:
                hashed = hash_password(new_pass)
                save_user_to_db(new_user, hashed)
                st.success("User registered! You can now log in.")

def update_video_stats(video_uuid, views, likes, dislikes, hearts, avg_rating=None):
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            UPDATE public."MAVS_VIDEOS"
            SET "VIEWS" = %s,
                "LIKES" = %s,
                "DISLIKES" = %s,
                "HEARTS" = %s,
                "RATING" = %s,
                "MODIFIED_DATE" = CURRENT_DATE,
                "MODIFIED_TIME" = CURRENT_TIME
            WHERE "VIDEO_ID" = %s
        """, (views, likes, dislikes, hearts, avg_rating, video_uuid))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        st.error(f"Failed to update video stats: {e}")
 
def save_comment_to_db(video_id, username, comment_text):
    try:
        conn = get_connection()
        cur = conn.cursor()

        # Generate COMMENT_ID
        cur.execute('SELECT COALESCE(MAX("COMMENT_ID"), 0) + 1 FROM public."MAVS_COMMENTS"')
        comment_id = cur.fetchone()[0]

        cur.execute("""
            INSERT INTO public."MAVS_COMMENTS" (
                "COMMENT_ID", "VIDEO_ID", "USER_NAME", "COMMENT_TEXT",
                "CREATED_DATE", "MODIFIED_DATE", "CREATED_TIME", "MODIFIED_TIME"
            )
            VALUES (%s, %s, %s, %s, CURRENT_DATE, CURRENT_DATE, CURRENT_TIME, CURRENT_TIME)
        """, (
            comment_id, video_id, username, comment_text
        ))

        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        st.error(f"Error saving comment to database: {e}")

# --- LOAD VIDEOS FROM DB ---
def load_videos_from_db():
    videos = []
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT "VIDEO_ID", "VIDEO_NAME", "VIEWS", "LIKES", "DISLIKES", "HEARTS",
                   "VIDEO_DATA", "THUMB_DATA", "VIDEO_DESC", "RATING"
            FROM public."MAVS_VIDEOS"
        """)
        video_rows = cur.fetchall()

        video_dict = {}
        for video_id, name, views, likes, dislikes, hearts, video_blob, thumb_blob, desc, rating in video_rows:
            video_dict[video_id] = {
                "uuid": video_id,
                "title": name,
                "desc": desc,
                "file": bytes(video_blob) if video_blob else None,
                "thumb": bytes(thumb_blob) if thumb_blob else None,
                "views": views,
                "liked_by": [],
                "disliked_by": [],
                "hearted_by": [],
                "comments": [],
                "ratings": {},  # keep for user-specific ratings if needed
                "RATING": float(rating) if rating is not None else 0,  # use DB rating
                "uploaded_by": "Unknown"
            }

        # Load reactions for all videos
        cur.execute("""
            SELECT "VIDEO_ID", "USER_NAME", "REACTION_TYPE"
            FROM public."MAVS_VIDEO_REACTIONS"
            WHERE "VIDEO_ID" = ANY(%s::UUID[])
        """, (list(video_dict.keys()),))
        for video_id, user_name, reaction_type in cur.fetchall():
            if video_id in video_dict:
                user = user_name.strip()
                reaction = reaction_type.strip()
                if reaction == 'L' and user not in video_dict[video_id]["liked_by"]:
                    video_dict[video_id]["liked_by"].append(user)
                elif reaction == 'D' and user not in video_dict[video_id]["disliked_by"]:
                    video_dict[video_id]["disliked_by"].append(user)
                elif reaction == 'H' and user not in video_dict[video_id]["hearted_by"]:
                    video_dict[video_id]["hearted_by"].append(user)

        cur.close()
        conn.close()
        videos = list(video_dict.values())

    except Exception as e:
        st.error(f"Failed to load videos from DB: {e}")
    return videos

def logout():
    st.session_state.logged_in = False
    st.session_state.username = ""
    st.success("Logged out successfully!")
    st.rerun()

# AUTH CHECK
if not st.session_state.logged_in:
    show_auth()
    st.stop()

# Load videos from DB once after login
if "videos" not in st.session_state or not st.session_state.videos:
    st.session_state.videos = load_videos_from_db()

# SHOW APP AFTER LOGIN
with st.sidebar:
    st.markdown('<h1 class="mavs-title no-gradient">📺 MAVS</h1>', unsafe_allow_html=True)

st.sidebar.success(f"Logged in as {st.session_state.username}")
with st.sidebar:
    st.markdown('<div class="custom-logout">', unsafe_allow_html=True)
    if st.button("Logout"):
        logout()
    st.markdown('</div>', unsafe_allow_html=True)

if "page" not in st.session_state:
    st.session_state.page = "Home"

pages = ["Home", "Upload", "Watch", "Analytics"]
selected_page = st.sidebar.radio("Go to", pages, index=pages.index(st.session_state.page), key="main_nav")

if selected_page != st.session_state.page:
    st.session_state.page = selected_page

page = st.session_state.page

import streamlit as st

st.markdown("""
<style>
/* ===== Sidebar (mild CGI style) ===== */
[data-testid="stSidebar"] {
   background-color: #C2182B !important; /* Softer burgundy */
   ## background-color: #000000 !important;
    color: #FFFFFF !important;
    min-width: 200px;
    padding-top: 20px;
    box-shadow: 1px 0 4px rgba(0,0,0,0.08);
}

/* Sidebar text */
[data-testid="stSidebar"] * {
    color: #FFFFFF !important;
    font-weight: 500;
}

/* MAVS text - force white, no gradient */
[data-testid="stSidebar"] h1.sidebar-title,
[data-testid="stSidebar"] h1.sidebar-title * {
    background: none !important;
    -webkit-background-clip: unset !important;
    -webkit-text-fill-color: unset !important;
    color: #FFFFFF !important;   /* Keep MAVS white */
    font-size: 28px !important;
    font-weight: bold !important;
    margin: 20px 10px 20px 10px;
    display: block !important;
}

/* Section headers */
[data-testid="stSidebar"] h2,
[data-testid="stSidebar"] h3 {
    color: #F4F4F4 !important;
    text-transform: uppercase;
    font-size: 13px;
    margin: 18px 10px 6px 10px;
    font-weight: 600;
}

/* Sidebar links */
[data-testid="stSidebar"] a {
    display: block;
    padding: 10px 15px;
    margin: 2px 10px;
    border-radius: 6px;
    text-decoration: none !important;
    color: #FFFFFF !important;
    transition: background 0.3s, font-weight 0.3s;
}

/* Hover effect */
[data-testid="stSidebar"] a:hover {
    background-color: rgba(227,25,55,0.1);
    font-weight: bold;
}

/* Active link */
[data-testid="stSidebar"] a:focus,
[data-testid="stSidebar"] a:active {
    background-color: #FFFFFF !important;
    color: #E31837 !important;
    font-weight: bold;
    border-left: 3px solid #E31837;
}

/* ===== Main page colors ===== */
.stApp {
    background-color: #F4F4F4;
    color: #212121;
    font-family: "Segoe UI", Arial, sans-serif;
}

/* ===== All headers default (Red-Blue Gradient) ===== */
h1:not(.no-gradient),
h2:not(.no-gradient),
h3:not(.no-gradient),
h4:not(.no-gradient),
h5:not(.no-gradient),
h6:not(.no-gradient) {
    background: linear-gradient(90deg, #E31837, #0a47a3) !important;
    -webkit-background-clip: text !important;
    -webkit-text-fill-color: transparent !important;
    font-weight: bold !important;
}

/* ===== Buttons (updated colors) ===== */
.stButton > button.primary {
    background-color: #E31837 !important;
    color: #FFFFFF !important;
    border-radius: 5px;
    padding: 0.6em 1.2em;
    font-weight: bold;
    transition: background-color 0.3s;
}
.stButton > button.primary:hover {
    background-color: #C2182B !important;
}

.stButton > button.secondary {
    background-color: #F76C6D !important;
    color: #FFFFFF !important;
    border-radius: 5px;
    padding: 0.6em 1.2em;
    font-weight: bold;
    transition: background-color 0.3s;
}
.stButton > button.secondary:hover {
    background-color: #E31837 !important;
}

.stButton > button.neutral {
    background-color: #4B4B4B !important;
    color: #FFFFFF !important;
    border-radius: 5px;
    padding: 0.6em 1.2em;
    font-weight: bold;
    transition: background-color 0.3s;
}
.stButton > button.neutral:hover {
    background-color: #333333 !important;
}

/* Logout button */
div.custom-logout > div > button,
div[data-testid="stSidebar"] div.custom-logout > div > button {
    background-color: #E31837 !important;
    color: #FFFFFF !important;
    font-weight: bold !important;
    border: #E31837 !important;
    border-radius: 6px !important;
    width: 100% !important;
    padding: 0.7em 1.2em !important;
    transition: background-color 0.3s ease-in-out;
}
div.custom-logout > div > button:hover,
div[data-testid="stSidebar"] div.custom-logout > div > button:hover {
    background-color: #C2182B !important;
    color: #FFFFFF !important;
}

/* Metrics / Cards */
div[data-testid="metric-container"] {
    background-color: #FFFFFF !important;
    border: 1px solid #E31837;
    border-radius: 10px;
    padding: 12px;
    box-shadow: 0 2px 6px rgba(0,0,0,0.1);
    color: #212121 !important;
}

/* Inputs / Select boxes */
.stTextInput input, .stTextArea textarea, .stSelectbox div[data-baseweb="select"] > div {
    background-color: #FFFFFF !important;
    border: 1px solid #E31837 !important;
    color: #212121 !important;
    border-radius: 5px;
}
.stTextInput input:focus, .stTextArea textarea:focus {
    outline: 2px solid #E31837 !important;
    border-color: #E31837 !important;
}

/* Hide Streamlit menu / footer */
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}

/* ==== DARK AMBER CUSTOM HEADERS ==== */
.rate-video, .rate-video * {
    color: #FFB300 !important;
    font-size: 22px !important;
}
.comments-header, .comments-header * {
    color: #FFB300 !important;
    font-size: 20px !important;
}
.analytics-top-rated, .analytics-top-rated * {
    color: #FFB300 !important;
    font-size: 24px !important;
    border-bottom: 2px solid #FFB300 !important;
    padding-bottom: 6px !important;
}
.analytics-overview, .analytics-overview * {
    color: #FFB300 !important;
    font-size: 24px !important;
    border-bottom: 2px solid #FFB300 !important;
    padding-bottom: 6px !important;
}

/* ==== HOME PAGE VIDEO HEADER (Red-Blue Gradient) ==== */
.video-header, .video-header * {
    background: linear-gradient(90deg, #E31837, #0a47a3);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    font-weight: bold !important;
    font-size: 26px !important;
    text-transform: uppercase;
}
            
/* ===== Center CGI GRAM Title on Watch Page ===== */
.center-title h1 {
    text-align: center !important;
    width: 100% !important;
    display: block !important;
}

/* ===== Force Center CGI GRAM Title ===== */
h1.center-title {
    text-align: center !important;
    width: 100% !important;
    display: flex !important;
    justify-content: center !important;
    align-items: center !important;
    margin: 0 auto !important;
}

</style>
""", unsafe_allow_html=True)

# --- HOME PAGE ---
if page == "Home":
    st.markdown('<h1 class="video-header">CGI GRAM – All Videos</h1>', unsafe_allow_html=True)

    search_col, sort_col = st.columns([4, 1])
    search_query = search_col.text_input("🔍 Search videos by title", key="home_search")

    with sort_col:
        sort_option = st.selectbox(
            " ",
            options=["No Sorting", "Most Views", "Most Likes", "Most Dislikes"],
            key="home_sort"
        )

    # Filter
    filtered_videos = [
        v for v in st.session_state.videos
        if search_query.lower() in v["title"].lower()
    ] if search_query else st.session_state.videos.copy()

    # Sort
    if sort_option == "Most Views":
        filtered_videos.sort(key=lambda v: v.get("views", 0), reverse=True)
    #elif sort_option == "Top Rated":
     #   filtered_videos.sort(key=lambda v: v.get("RATING", 0), reverse=True)
    elif sort_option == "Most Likes":
        filtered_videos.sort(key=lambda v: len(v.get("liked_by", [])), reverse=True)
    elif sort_option == "Most Dislikes":
        filtered_videos.sort(key=lambda v: len(v.get("disliked_by", [])), reverse=True)

    if not filtered_videos:
        st.info("No videos found matching your search.")
    else:
        for idx, v in enumerate(filtered_videos):
            st.markdown("---")
            cols = st.columns([1, 4])
            if v.get("thumb"):
                cols[0].image(v["thumb"], width=120)
            else:
                cols[0].image("https://via.placeholder.com/120x80.png?text=No+Thumbnail", width=120)
            with cols[1]:
                likes = len(v.get("liked_by", []))
                dislikes = len(v.get("disliked_by", []))
                hearts = len(v.get("hearted_by", []))
                st.subheader(v["title"])
                st.caption(f"Uploaded by: {v.get('uploaded_by', 'Unknown')}")
                st.write(f"{v['views']} Views | 👍 {likes} | 👎 {dislikes} | ❤️ {hearts}")

                # Watch button
                original_idx = st.session_state.videos.index(v)
                if st.button("Watch", key=f"watch_{original_idx}"):
                    st.session_state.current = original_idx
                    st.session_state.page = "Watch"
                    st.rerun()

# --- UPLOAD PAGE ---
elif page == "Upload":
    st.title("CGI GRAM - Upload Video")

    uploaded_video = st.file_uploader("Choose video", type=["mp4"])
    uploaded_thumb = st.file_uploader("Choose thumbnail (optional)", type=["jpg", "png"])
    title = st.text_input("Video Title")
    desc = st.text_area("Description")

    if st.button("Upload"):
        if uploaded_video and title and desc:
            video_data = uploaded_video.read()
            thumb_data = uploaded_thumb.read() if uploaded_thumb else None

            # Generate UUID for the video
            video_uuid = str(uuid4())

            # Add video to Streamlit session
            st.session_state.videos.append({
                "title": title,
                "desc": desc,
                "file": video_data,
                "thumb": thumb_data,
                "views": 0,
                "liked_by": [],
                "disliked_by": [],
                "hearted_by": [],
                "comments": [],
                "ratings": {},  # username -> rating
                "uploaded_by": st.session_state.username,
                "uuid": video_uuid  # store uuid for DB reference
            })

            try:
                conn = get_connection()
                cur = conn.cursor()

                # Use a new unique SYS_ID by getting the count of existing rows
                cur.execute('SELECT COUNT(*) FROM public."MAVS_VIDEOS"')
                sys_id = cur.fetchone()[0] + 1

                # Insert into database
                cur.execute("""
                    INSERT INTO public."MAVS_VIDEOS" (
                        "SYS_ID", "VIDEO_ID", "VIDEO_NAME", "VIEWS", "LIKES", "DISLIKES", "HEARTS",
                        "VIDEO_DATA", "THUMB_DATA","VIDEO_DESC",
                        "CREATED_DATE", "MODIFIED_DATE", "CREATED_TIME", "MODIFIED_TIME"
    )
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s,%s, CURRENT_DATE, CURRENT_DATE, CURRENT_TIME, CURRENT_TIME)
""", (
    sys_id,
    video_uuid,
    title,
    0, 0, 0, 0,
    psycopg2.Binary(video_data),
    psycopg2.Binary(thumb_data) if thumb_data else None,
    desc
))

                conn.commit()
                cur.close()
                conn.close()

                st.success("Video uploaded and saved to database successfully!")
            except Exception as e:
                st.error(f"Error saving video to database: {e}")
        else:
            st.error("Please provide at least video, title, and description.")

#watch page
elif page == "Watch":
    st.markdown("<h1 class='center-title'>CGI GRAM</h1>", unsafe_allow_html=True)
    idx = st.session_state.get("current", None)
    if idx is None or idx >= len(st.session_state.videos):
        st.warning("Select a video from Home first!")
        st.stop()
    
    video = st.session_state.videos[idx]
    video_uuid = video.get("uuid")

    # --- Helper functions for view tracking ---
    def has_user_viewed(video_id, username):
        try:
            conn = get_connection()
            cur = conn.cursor()
            cur.execute("""
                SELECT 1 FROM public."MAVS_VIDEO_VIEWS"
                WHERE "VIDEO_ID" = %s AND "USER_NAME" = %s
            """, (video_id, username))
            result = cur.fetchone()
            cur.close()
            conn.close()
            return result is not None
        except Exception as e:
            st.error(f"Error checking views: {e}")
            return False

    def mark_user_viewed(video_id, username):
        try:
            conn = get_connection()
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO public."MAVS_VIDEO_VIEWS" ("VIDEO_ID", "USER_NAME")
                VALUES (%s, %s)
                ON CONFLICT DO NOTHING
            """, (video_id, username))
            conn.commit()
            cur.close()
            conn.close()
        except Exception as e:
            st.error(f"Error saving view: {e}")

    # --- LOAD REACTIONS, RATINGS & COMMENTS FROM DB ---
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT "VIEWS", "LIKES", "DISLIKES", "HEARTS", "RATING"
            FROM public."MAVS_VIDEOS"
            WHERE "VIDEO_ID" = %s
        """, (video_uuid,))
        result = cur.fetchone()
        if result:
            views, likes, dislikes, hearts, avg_rating_db = result
        else:
            views = likes = dislikes = hearts = avg_rating_db = 0

        cur.execute("""
            SELECT "USER_NAME", "COMMENT_TEXT", "CREATED_DATE", "CREATED_TIME"
            FROM public."MAVS_COMMENTS"
            WHERE "VIDEO_ID" = %s
            ORDER BY "CREATED_DATE" DESC, "CREATED_TIME" DESC
        """, (video_uuid,))
        comments_db = cur.fetchall()

        cur.close()
        conn.close()

        video["views"] = views
        video["comments"] = [
            {"user": u, "text": t, "time": f"{d} {tm}"} for u, t, d, tm in comments_db
        ]

    except Exception as e:
        st.error(f"Error loading video details: {e}")

    st.title(video["title"])
    st.write(video["desc"])
    st.video(video["file"])

    likes = len(video.get("liked_by", []))
    dislikes = len(video.get("disliked_by", []))
    hearts = len(video.get("hearted_by", []))
    
    col1, col2, col3 = st.columns(3)

    def update_reactions_db(video_id, likes_count, dislikes_count, hearts_count):
        try:
            conn = get_connection()
            cur = conn.cursor()
            cur.execute("""
                UPDATE public."MAVS_VIDEOS"
                SET "LIKES" = %s,
                    "DISLIKES" = %s,
                    "HEARTS" = %s,
                    "MODIFIED_DATE" = CURRENT_DATE,
                    "MODIFIED_TIME" = CURRENT_TIME
                WHERE "VIDEO_ID" = %s
            """, (likes_count, dislikes_count, hearts_count, video_id))
            conn.commit()
            cur.close()
            conn.close()
        except Exception as e:
            st.error(f"Failed to update reactions: {e}")

    # LIKE
    if col1.button("👍 Like"):
        if st.session_state.username not in video["liked_by"]:
            video["liked_by"].append(st.session_state.username)
            if st.session_state.username in video["disliked_by"]:
                video["disliked_by"].remove(st.session_state.username)
        else:
            st.info("You’ve already Liked this video.")
        save_reaction_to_db(video_uuid, st.session_state.username, 'L')
        
        try:
            conn = get_connection()
            cur = conn.cursor()
            cur.execute("""
                DELETE FROM public."MAVS_VIDEO_REACTIONS"
                WHERE "VIDEO_ID" = %s AND "USER_NAME" = %s AND "REACTION_TYPE" = 'D'
            """, (video_uuid, st.session_state.username))
            conn.commit()
            cur.close()
            conn.close()
        except Exception as e:
            st.error(f"Error removing dislike: {e}")
        update_reactions_db(video_uuid, len(video["liked_by"]), len(video["disliked_by"]), len(video["hearted_by"]))
        st.rerun()

    # DISLIKE
    if col2.button("👎 Dislike"):
        if st.session_state.username not in video["disliked_by"]:
            video["disliked_by"].append(st.session_state.username)
            if st.session_state.username in video["liked_by"]:
                video["liked_by"].remove(st.session_state.username)
        else:
            st.info("You’ve already Disliked this video.")
        save_reaction_to_db(video_uuid, st.session_state.username, 'D')
        try:
            conn = get_connection()
            cur = conn.cursor()
            cur.execute("""
                DELETE FROM public."MAVS_VIDEO_REACTIONS"
                WHERE "VIDEO_ID" = %s AND "USER_NAME" = %s AND "REACTION_TYPE" = 'L'
            """, (video_uuid, st.session_state.username))
            conn.commit()
            cur.close()
            conn.close()
        except Exception as e:
            st.error(f"Error removing like: {e}")
            update_reactions_db(video_uuid, len(video["liked_by"]), len(video["disliked_by"]), len(video["hearted_by"]))
        st.rerun()

    # HEART
    if col3.button("❤️ Heart"):
        if st.session_state.username not in video["hearted_by"]:
            video["hearted_by"].append(st.session_state.username)
            save_reaction_to_db(video_uuid, st.session_state.username, 'H')
            update_reactions_db(video_uuid, len(video["liked_by"]), len(video["disliked_by"]), len(video["hearted_by"]))
            st.rerun()
        else:
            st.info("You’ve already hearted this video.")

    # ✅ FIXED VIEW COUNT — now DB-based
    if not has_user_viewed(video_uuid, st.session_state.username):
        mark_user_viewed(video_uuid, st.session_state.username)
        try:
            conn = get_connection()
            cur = conn.cursor()
            cur.execute("""
                UPDATE public."MAVS_VIDEOS"
                SET "VIEWS" = "VIEWS" + 1,
                    "MODIFIED_DATE" = CURRENT_DATE,
                    "MODIFIED_TIME" = CURRENT_TIME
                WHERE "VIDEO_ID" = %s
            """, (video_uuid,))
            conn.commit()
            cur.close()
            conn.close()
            video["views"] += 1
        except Exception as e:
            st.error(f"Failed to update views: {e}")

    st.write(f"{video['views']} Views | 👍 {likes} | 👎 {dislikes} | ❤️ {hearts}")

    # --- RATING ---
    st.markdown('<p class="rate-video">⭐ Rate this Video</p>', unsafe_allow_html=True)
    rating = st.slider("Your rating (1-5 stars)", 1, 5, 3)
    if st.button("Submit Rating"):
        save_rating_to_db(video_uuid, st.session_state.username, rating)
        update_video_avg_rating(video_uuid)
        st.success("Thanks for rating!")
        st.rerun()

    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT COUNT(*) AS rating_count,
                   ROUND(AVG("RATING")::numeric, 2) AS avg_rating
            FROM public."MAVS_VIDEO_RATINGS"
            WHERE "VIDEO_ID" = %s;
        """, (video_uuid,))
        count, avg = cur.fetchone()
        cur.close()
        conn.close()
        if count > 0:
            st.markdown(f"⭐ Average Rating: {avg} / 5 ({count} rating{'s' if count > 1 else ''})")
        else:
            st.write("⭐ No ratings yet")
    except Exception as e:
        st.error(f"Failed to load average rating: {e}")

    # --- COMMENTS ---
    st.subheader("Add a Comment")
    comment = st.text_input("Write your comment here...")
    if st.button("Post Comment"):
        if comment.strip():
            video["comments"].append({
                "user": st.session_state.username,
                "text": comment,
                "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            })
            save_comment_to_db(video_uuid, st.session_state.username, comment)
            st.success("Comment posted!")
            st.rerun()
        else:
            st.warning("Please enter a comment before posting.")

    st.markdown('<p class="comments-header">💬 Comments</p>', unsafe_allow_html=True)
    for c in video["comments"]:
        st.markdown(f"**{c['user']}** at *{c['time']}*")
        st.write(f"> {c['text']}")

# --- ANALYTICS PAGE ---  
elif page == "Analytics":
    st.title("CGI GRAM – Analytics")

    search_query = st.text_input("Search videos by title", key="analytics_search")

    vids = st.session_state.videos

    # Filter once, outside any loop
    if search_query:
        vids = [v for v in vids if search_query.lower() in v["title"].lower()]
        if not vids:
            st.info("No videos found matching your search.")
            st.stop()  # Halt rendering here if there are no matches

    # Analytics section: Ratings
    def fetch_avg_rating_for_video(video_id):
        try:
            conn = get_connection()
            cur = conn.cursor()
            cur.execute("""
                SELECT COUNT(*), ROUND(AVG("RATING")::numeric, 2)
                FROM public."MAVS_VIDEO_RATINGS"
                WHERE "VIDEO_ID" = %s;
            """, (video_id,))
            count, avg = cur.fetchone()
            cur.close()
            conn.close()
            return count or 0, avg or 0
        except:
            return 0, 0

    st.markdown('<p class="analytics-top-rated">🏆 Top Rated Videos</p>', unsafe_allow_html=True)

    st.markdown("---")
    rated_videos = []
    for v in vids:
        count, avg = fetch_avg_rating_for_video(v["uuid"])
        if count > 0:
            rated_videos.append((v, avg))

    if rated_videos:
        max_rating = max(rated_videos, key=lambda x: x[1])[1]
        top_rated_videos = [v for v in rated_videos if v[1] == max_rating]

        for top_video, top_avg_rating in top_rated_videos:
            col1, col2 = st.columns([1, 4])
            if top_video.get("thumb"):
                col1.image(top_video["thumb"], width=120)
            else:
                col1.image("https://via.placeholder.com/120x80.png?text=No+Thumbnail", width=120)

            with col2:
                st.subheader(top_video['title'])
                st.caption(f"Uploaded by: {top_video.get('uploaded_by', 'Unknown')}")
                st.write(f"Views: {top_video.get('views', 0)}")
                st.write(
                    f"👍 Likes: {len(top_video.get('liked_by', []))} | "
                    f"👎 Dislikes: {len(top_video.get('disliked_by', []))} | "
                    f"❤️ Hearts: {len(top_video.get('hearted_by', []))}"
                )
                st.write(f"⭐ Average Rating: {top_avg_rating}")
            st.markdown("---")
    else:
        st.info("No rated videos found.")

    # All Videos Overview
    st.markdown('<p class="analytics-overview">📊 All Videos Overview</p>', unsafe_allow_html=True)
    for v in vids:
        count, avg = fetch_avg_rating_for_video(v["uuid"])  # <-- fetch per video
        cols = st.columns([1, 4])
        if v.get("thumb"):
            cols[0].image(bytes(v["thumb"]), width=120)
        else:
            cols[0].image("https://via.placeholder.com/120x80.png?text=No+Thumbnail", width=120)

        with cols[1]:
            st.write(f"**{v['title']}**")
            st.write(f"Views: {v.get('views', 0)}")
            st.write(
                f"👍 Likes: {len(v.get('liked_by', []))} | "
                f"👎 Dislikes: {len(v.get('disliked_by', []))} | "
                f"❤️ Hearts: {len(v.get('hearted_by', []))}"
            )
            st.markdown(f"⭐ Average Rating: {avg} / 5 ({count} rating{'s' if count > 1 else ''})")
