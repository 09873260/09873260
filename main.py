import os
import zipfile
import requests
from github import Github

# Configuration from GitHub Secrets / Environment
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
REPO_NAME = os.getenv("GITHUB_REPOSITORY")
SEARCH_QUERY = os.getenv("SEARCH_QUERY", "Ubuntu")


def search_archive_org(query):
  """Searches Internet Archive (Archive.org) for items with torrents."""
  torrents = []
  print(f"[*] Searching Internet Archive for: {query}")
  try:
    url = f"https://archive.org/advancedsearch.php?q={query}&fl[]=identifier&fl[]=title&rows=3&output=json"
    response = requests.get(url, timeout=10)
    if response.status_code == 200:
      data = response.json()
      docs = data.get("response", {}).get("docs", [])
      for doc in docs:
        identifier = doc.get("identifier")
        title = doc.get("title", identifier)
        # Archive.org automatically provides a .torrent file for every item
        torrent_url = f"https://archive.org/download/{identifier}/{identifier}_archive.torrent"
        torrents.append({"name": f"Archive - {title}", "url": torrent_url})
  except Exception as e:
    print(f"[!] Error searching Internet Archive: {e}")
  return torrents


def search_torrents_multiple_sources(query):
  """Combines search results from multiple public sources."""
  all_torrents = []

  # מקור 1: Internet Archive
  all_torrents.extend(search_archive_org(query))

  # אפשר להוסיף כאן מקורות נוספים בקלות בעתיד

  return all_torrents


def process_and_upload(torrent_info):
  """Downloads a torrent file, zips it, and uploads to GitHub Releases."""
  name = torrent_info["name"]
  url = torrent_info["url"]

  # Sanitize name for filenames
  safe_name = "".join(
      c for c in name if c.isalnum() or c in (" ", "-", "_")
  ).strip()
  if not safe_name:
    safe_name = "torrent_file"

  # הגבלת אורך השם למניעת שגיאות אורך ב-GitHub
  safe_name = safe_name[:40]
  torrent_filename = f"{safe_name}.torrent"
  zip_filename = f"{safe_name}.zip"

  print(f"\n[*] Downloading torrent from: {url}")
  try:
    res = requests.get(url, timeout=15)
    if res.status_code != 200:
      print(f"[!] Failed to download torrent (Status code: {res.status_code})")
      return

    with open(torrent_filename, "wb") as f:
      f.write(res.content)

    print(f"[*] Compressing into {zip_filename}...")
    with zipfile.ZipFile(
        zip_filename, "w", zipfile.ZIP_DEFLATED
    ) as zipf:
      zipf.write(torrent_filename)

    print(f"[*] Uploading to GitHub Release for repo: {REPO_NAME}")
    g = Github(GITHUB_TOKEN)
    repo = g.get_repo(REPO_NAME)

    tag_name = (
        f"torrent-{safe_name.lower().replace(' ', '-')}-{os.urandom(2).hex()}"
    )
    release_title = f"Torrent: {name[:50]}"

    try:
      release = repo.create_git_release(
          tag=tag_name,
          name=release_title,
          message=(
              "Automated cloud release containing the torrent file for"
              f" {name}."
          ),
          draft=False,
          prerelease=False,
      )
      release.upload_asset(zip_filename, label=zip_filename)
      print(f"[+] Successfully uploaded release: {release_title}")

    except Exception as e:
      print(f"[!] GitHub upload error: {e}")

  finally:
    if os.path.exists(torrent_filename):
      os.remove(torrent_filename)
    if os.path.exists(zip_filename):
      os.remove(zip_filename)


if __name__ == "__main__":
  if not GITHUB_TOKEN or not REPO_NAME:
    print("[!] GITHUB_TOKEN or REPO_NAME missing.")
  else:
    results = search_torrents_multiple_sources(SEARCH_QUERY)
    print(f"[*] Found {len(results)} torrents.")
    for item in results:
      process_and_upload(item)
