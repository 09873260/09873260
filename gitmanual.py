import json
import os
import re
import feedparser
import requests

# ===== הגדרות =====
STATE_FILE = "gitmanual_seen.json"  # שנוי שם קובץ המצב
DOWNLOAD_DIR = "podcasts"

ALLOWED_COUNTS = (5, 10, 15, 20, 30, 40, 100)
DEFAULT_COUNT = 5


def get_episodes_per_run():
    """כמות הפרקים מגיעה מהטופס בגיטהאב (EPISODES_PER_RUN). ערך לא תקין -> ברירת מחדל."""
    value = os.environ.get("EPISODES_PER_RUN", "").strip()
    if value.isdigit() and int(value) in ALLOWED_COUNTS:
        return int(value)
    if value:
        print(f"ערך לא תקין ב-EPISODES_PER_RUN: {value}. משתמש בברירת המחדל ({DEFAULT_COUNT}).")
    return DEFAULT_COUNT


EPISODES_PER_RUN = get_episodes_per_run()

def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

def sanitize_filename(name):
    cleaned = name.replace("[", "'").replace("]", "'").replace(":", "")
    return re.sub(r'[\\/*?:"<>|]', "", cleaned).strip() or "podcast_episode"

def download_podcast(url, filename, folder):
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, filename)
    headers = {"User-Agent": "Mozilla/5.0"}
    with requests.get(url, headers=headers, stream=True, timeout=180) as r:
        r.raise_for_status()
        with open(path, "wb") as f:
            for chunk in r.iter_content(chunk_size=1024 * 256):
                f.write(chunk)
    return path

def main():
    rss_url = os.environ.get("RSS_URL")
    if not rss_url:
        print("לא הוגדרה כתובת RSS.")
        return

    state = load_state()
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    
    print(f"בודק את הפיד: {rss_url}")
    print(f"כמות פרקים להורדה בהרצה זו: {EPISODES_PER_RUN}")
    parsed = feedparser.parse(rss_url)
    if not parsed.entries:
        print("לא נמצאו פרקים בפיד.")
        return

    feed_title = parsed.feed.get("title", "Podcast")
    
    # חילוץ שתי המילים הראשונות ויצירת Slug
    words = feed_title.strip().split()[:2]
    slug = "-".join(words).lower()
    slug = re.sub(r'[^a-z0-9\-]', '', slug)
    if not slug:
        slug = "podcast"
        
    github_env = os.environ.get("GITHUB_ENV")
    if github_env:
        with open(github_env, "a", encoding="utf-8") as env_file:
            env_file.write(f"PODCAST_SLUG={slug}\n")

    seen = set(state.get(rss_url, []))
    
    entries = parsed.entries
    ids = [e.get("id") or e.get("link") for e in entries]

    if rss_url not in state:
        state[rss_url] = []
        seen = set()

    downloaded_count = 0
    for entry, eid in reversed(list(zip(entries, ids))):
        if downloaded_count >= EPISODES_PER_RUN:
            break

        if eid not in seen:
            title = entry.get("title", "New episode")
            enclosures = entry.get("enclosures", [])
            
            if not enclosures:
                # אין קובץ שמע, אין מה להוריד (לא שומרים כ-seen כדי לא לפספס אם יתווסף בהמשך)
                continue

            audio_url = enclosures[0].get("href")
            safe_name = sanitize_filename(f"{feed_title} - {title}")
            filename = f"{safe_name}.mp3"

            print(f"מוריד: {filename}")
            try:
                # ההורדה מתבצעת; אם תזרק שגיאה, היא לא תיכנס ל-seen
                download_podcast(audio_url, filename, DOWNLOAD_DIR)
                
                # שומרים כנקצֶה רק לאחר הצלחה מלאה של ההורדה
                seen.add(eid)
                downloaded_count += 1
            except Exception as e:
                print(f"שגיאה בהורדת {filename}: {e} - הפרק לא יסומן כנקרא וינוסה שוב בריצה הבאה.")

    state[rss_url] = list(seen)
    save_state(state)

if __name__ == "__main__":
    main()
