import calendar
import json
import os
import time
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
    "https://feeds.acast.com/public/shows/67587e77c705e441797aff96",
    "https://feeds.megaphone.fm/ESP6921732651",
    "https://feeds.megaphone.fm/the-rich-roll-podcast",
    "https://anchor.fm/s/10d9805f4/podcast/rss",
    "https://podcastfeeds.nbcnews.com/dateline-nbc",
    "https://www.spreaker.com/show/5956723/episodes/feed",
    "https://feeds.megaphone.fm/SIXMSB5088139739",
    "https://feeds.npr.org/510298/podcast.xml",
    "https://feeds.transistor.fm/think-fast-talk-smart-communication-techniques",
    "https://feeds.megaphone.fm/NRD2548999404",
    "https://api.substack.com/feed/podcast/1449053.rss",
]

STATE_FILE = "seen.json"
DOWNLOAD_DIR = "podcasts_auto"
TEST_SEND = os.environ.get("TEST_SEND") == "true"

MAX_IDS_FALLBACK = 200   # IDs kept per feed that has no dates
FALLBACK_WINDOW = 20     # latest entries checked in a feed that has no dates


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
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    for attempt in range(1, 4):
        try:
            with requests.get(url, headers=headers, stream=True, timeout=300) as r:
                r.raise_for_status()
                with open(path, "wb") as f:
                    for chunk in r.iter_content(chunk_size=1024 * 512):
                        if chunk:
                            f.write(chunk)
            return path
        except Exception as e:
            print(f"ניסיון {attempt} נכשל בהורדת {filename}: {e}")
            if attempt == 3:
                raise e
            time.sleep(5)


def process_entry(feed_title, entry):
    title = entry.get("title", "New episode")
    enclosures = entry.get("enclosures", [])
    if not enclosures:
        print(f"No audio file found for: {title}")
        return

    cleaned_feed = feed_title.replace("[", "'").replace("]", "'").replace(":", "")
    cleaned_title = title.replace("[", "'").replace("]", "'").replace(":", "")

    full_name = f"{cleaned_feed} - {cleaned_title}"
    safe = "".join(c for c in full_name[:100] if c.isalnum() or c in " -_.,()'") or "episode"
    filename = f"{safe}.mp3"
    
    print(f"Downloading: {filename}")
    try:
        download_podcast(enclosures[0]["href"], filename)
    except Exception as e:
        print(f"Failed to download {filename}: {e}")


# ---------- Tracking which episodes were already handled ----------
def entry_ts(e):
    p = e.get("published_parsed") or e.get("updated_parsed")
    return calendar.timegm(p) if p else None


def entry_id(e):
    return e.get("id") or e.get("link")


def handle_dated(state, feed_url, feed_title, entries, stamps):
    """Default: store only the date of the last handled episode."""
    latest = max(stamps)
    old = state.get(feed_url)

    # First run: just mark, download nothing
    if old is None:
        state[feed_url] = latest
        return

    # Migration from the old format (list of IDs): handle what's new once, then switch to a date
    if isinstance(old, list):
        seen = set(old)
        for t, e in sorted(zip(stamps, entries), key=lambda x: x[0]):
            if entry_id(e) not in seen:
                process_entry(feed_title, e)
        state[feed_url] = latest
        return

    if not isinstance(old, int):
        state[feed_url] = latest
        return

    last = old
    new = sorted(((t, e) for t, e in zip(stamps, entries) if t > old), key=lambda x: x[0])
    for t, e in new:
        process_entry(feed_title, e)
        last = t
    state[feed_url] = last


def handle_undated(state, feed_url, feed_title, entries):
    """Feed without dates: short ID list, only the latest entries are checked."""
    window = entries[:FALLBACK_WINDOW]
    ids = [entry_id(e) for e in window]
    old = state.get(feed_url)

    if not isinstance(old, list):     # first run (or it used to be a number)
        state[feed_url] = ids
        return

    seen = set(old)
    for e, i in reversed(list(zip(window, ids))):
        if i in seen:
            continue
        process_entry(feed_title, e)
        seen.add(i)

    ids_set = set(ids)
    state[feed_url] = (ids + [i for i in old if i not in ids_set])[:MAX_IDS_FALLBACK]


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

        stamps = [entry_ts(e) for e in entries]
        is_dated = all(stamps)
        if not is_dated:
            print(f"No dates in feed ({sum(1 for t in stamps if t)}/{len(entries)} dated), "
                  f"using ID mode: {feed_title}")

        if TEST_SEND and entries:
            process_entry(feed_title, entries[0])
            if feed_url not in state:
                state[feed_url] = max(stamps) if is_dated else [entry_id(e) for e in entries[:FALLBACK_WINDOW]]
            continue

        if is_dated:
            handle_dated(state, feed_url, feed_title, entries, stamps)
        else:
            handle_undated(state, feed_url, feed_title, entries)

    save_state(state)


if __name__ == "__main__":
    main()
