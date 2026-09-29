import os
import zipfile
import requests
from github import Github

# Configuration from GitHub Secrets / Environment
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
REPO_NAME = os.getenv("GITHUB_REPOSITORY")
SEARCH_QUERY = os.getenv("SEARCH_QUERY", "Ubuntu")


def search_torrents_multiple_sources(query):
  """Searches multiple public torrent sources/APIs for the query."""
  torrents = []

  # Source 1: Example public API (e.g., YTS API)
  print(f"[*] Searching Source 1 for: {query}")
  try:
    url = f"https://yts.mx/api/v2/list_movies.json?query_term={query}"
    response = requests.get(url, timeout=10)
    if response.status_code == 200:
      data = response.json()
      movies = data.get("data", {}).get("movies", [])
      for movie in movies:
        for torrent in movie.get("torrents", []):
          torrents.append({
              "name": f"{movie['title']} ({movie['year']}) - {torrent['quality']}",
              "url": torrent["url"],
          })
  except Exception as e:
    print(f"[!] Error searching Source 1: {e}")

  # You can add more sources here (e.g., Archive.org, other APIs)

  return torrents


def process_and_upload(torrent_info):
  """Downloads a torrent file, zips it, and uploads to GitHub Releases."""
  name = torrent_info["name"]
  url = torrent_info["url"]

  # Sanitize name for filenames
  safe_name = "".join(
      c for c in name if c.isalnum() or c in (" ", "-", "_")
  ).strip()
  torrent_filename = f"{safe_name}.torrent"
  zip_filename = f"{safe_name}.zip"

  print(f"\n[*] Downloading torrent: {name}")
  try:
    res = requests.get(url, timeout=10)
    if res.status_code != 200:
      print(f"[!] Failed to download torrent from {url}")
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

    # Create a unique tag name based on the safe name and a random/hash suffix if needed
    tag_name = (
        f"torrent-{safe_name[:25].lower().replace(' ', '-')}-{os.urandom(2).hex()}"
    )
    release_title = f"Torrent: {name}"

    try:
      release = repo.create_git_release(
          tag=tag_name,
          name=release_title,
          message=f"Automated cloud release containing the torrent file for {name}.",
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
    for item in results[:2]:  # Limits to first 2 to prevent rate limits
      process_and_upload(item)
