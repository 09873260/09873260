import json
import os
import feedparser
import requests

FEEDS = [
    "https://feeds.simplecast.com/54nAGcIl",
    "https://techblogwriter.libsyn.com/rss",
    "https://feeds.feedburner.com/TEDTalks_audio",
    "https://feeds.simplecast.com/ZgXQt_UM",
    "https://podcasts.files.bbci.co.uk/p02nq0gn.rss",
    "https://feed.podbean.com/dailyworldbrief/feed.xml",
    "https://rss.amperwave.net/v2/feed/audacynetwork/4cbf0abf775be3cab2bd61a739939f1b",
    "https://www.omnycontent.com/d/playlist/397b9456-4f75-4509-acff-ac0600b4a6a4/6b5c19f7-a385-49c0-bb95-ad4a0071daea/08535d76-8bf4-4bf2-af8d-ad4a007205a3/podcast.rss",
    "https://feeds.megaphone.fm/GLT1412515089",
    "https://omnycontent.com/d/playlist/e73c998e-6e60-432f-8610-ae210140c5b1/A91018A4-EA4F-4130-BF55-AE270180C327/44710ECC-10BB-48D1-93C7-AE270180C33E/podcast.rss",
    "https://www.omnycontent.com/d/playlist/2ee97a4e-8795-4260-9648-accf00a38c6a/ac2da21e-2193-4683-bcb5-accf011076ad/409bad89-c4c2-46cb-b69b-accf01152781/podcast.rss",
    "https://www.spreaker.com/show/6951904/episodes/feed",
    "https://feeds.simplecast.com/qm_9xx0g",
    "https://feeds.simplecast.com/JZSQrle9",
    "https://feeds.megaphone.fm/WWO7410387571",
    "https://feeds.megaphone.fm/RSV1597324942",
    "https://rss2.flightcast.com/xmsftuzjjykcmqwolaqn6mdn",
    "https://www.omnycontent.com/d/playlist/e73c998e-6e60-432f-8610-ae210140c5b1/32f1779e-bc01-4d36-89e6-afcb01070c82/e0c8382f-48d4-42bb-89d5-afcb01075cb4/podcast.rss",
    "https://anchor.fm/s/1007c648c/podcast/rss",
    "https://anchor.fm/s/102ae1cf0/podcast/rss",
    "https://tonyrobbins.libsyn.com/rss",
]

STATE_FILE = "seen.json"
DOWNLOAD_DIR = "podcasts"
TEST_SEND = os.environ.get("TEST_SEND") == "true"


def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def download_podcast(url, filename):
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    path = os.path.join(DOWNLOAD_DIR, filename)
    headers = {"User-Agent": "Mozilla/5.0"}
    with requests.get(url, headers=headers, stream=True, timeout=180) as r:
        r.raise_for_status()
        with open(path, "wb") as f:
            for chunk in r.iter_content(chunk_size=1024 * 256):
                f.write(chunk)
    return path


def process_entry(feed_title, entry):
    title = entry.get("title", "New episode")
    enclosures = entry.get("enclosures", [])
    if not enclosures:
        print(f"No audio file found for: {title}")
        return

    # המרת סוגריים מרובעים לגרשיים והסרת נקודתיים
    cleaned_feed = feed_title.replace("[", "'").replace("]", "'").replace(":", "")
    cleaned_title = title.replace("[", "'").replace("]", "'").replace(":", "")

    full_name = f"{cleaned_feed} - {cleaned_title}"
    # סינון תווים המותרים בשם הקובץ
    safe = "".join(c for c in full_name[:100] if c.isalnum() or c in " -_.,()'") or "episode"
    filename = f"{safe}.mp3"
    
    print(f"Downloading: {filename}")
    try:
        download_podcast(enclosures[0]["href"], filename)
    except Exception as e:
        print(f"Failed to download {filename}: {e}")


def main():
    state = load_state()
    for feed_url in FEEDS:
        if not feed_url.strip():
            continue

        parsed = feedparser.parse(feed_url)
        if not parsed.entries:
            continue

        feed_title = parsed.feed.get("title", "Podcast")
        entries = parsed.entries
        ids = [e.get("id") or e.get("link") for e in entries]

        if TEST_SEND and entries:
            process_entry(feed_title, entries[0])
            state.setdefault(feed_url, ids)
            continue

        if feed_url not in state:
            state[feed_url] = ids
            continue

        seen = set(state[feed_url])
        for entry, eid in reversed(list(zip(entries, ids))):
            if eid not in seen:
                process_entry(feed_title, entry)
                seen.add(eid)
        state[feed_url] = list(seen)

    save_state(state)


if __name__ == "__main__":
    main()
