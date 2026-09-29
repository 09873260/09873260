import os
import sys
import zipfile
import requests
from github import Github

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
REPO_NAME = os.getenv("GITHUB_REPOSITORY")
SEARCH_QUERY = os.getenv("SEARCH_QUERY", "Matrix")
RESULT_INDEX = int(
    os.getenv("RESULT_INDEX", "1")
)  # 0 = All, 1+ = Specific movie number


def search_movies_archive_org(query):
  torrents = []
  print(f"[*] Searching Internet Archive for movies: {query}")
  try:
    url = f"https://archive.org/advancedsearch.php?q={query} AND mediatype:movies&fl[]=identifier&fl[]=title&rows=5&output=json"
    response = requests.get(url, timeout=10)
    if response.status_code == 200:
      data = response.json()
      docs = data.get("response", {}).get("docs", [])
      for doc in docs:
        identifier = doc.get("identifier")
        title = doc.get("title", identifier)
        torrent_url = f"https://archive.org/download/{identifier}/{identifier}_archive.torrent"
        torrents.append({"name": f"Movie - {title}", "url": torrent_url})
  except Exception as e:
    print(f"[!] Error: {e}")
  return torrents


def process_and_upload(torrent_info):
  name = torrent_info["name"]
  url = torrent_info["url"]

  safe_name = "".join(
      c for c in name if c.isalnum() or c in (" ", "-", "_")
  ).strip()
  if not safe_name:
    safe_name = "movie_torrent"

  safe_name = safe_name[:40]
  torrent_filename = f"{safe_name}.torrent"
  zip_filename = f"{safe_name}.zip"

  print(f"\n[*] Downloading approved torrent: {name}")
  try:
    res = requests.get(url, timeout=15)
    if res.status_code != 200:
      print(f"[!] Failed to download torrent")
      return

    with open(torrent_filename, "wb") as f:
      f.write(res.content)

    with zipfile.ZipFile(
        zip_filename, "w", zipfile.ZIP_DEFLATED
    ) as zipf:
      zipf.write(torrent_filename)

    g = Github(GITHUB_TOKEN)
    repo = g.get_repo(REPO_NAME)
    tag_name = (
        f"movie-{safe_name.lower().replace(' ', '-')}-{os.urandom(2).hex()}"
    )
    release_title = f"Movie Torrent: {name[:50]}"

    release = repo.create_git_release(
        tag=tag_name,
        name=release_title,
        message=f"Approved and uploaded torrent for {name}.",
        draft=False,
        prerelease=False,
    )
    release.upload_asset(zip_filename, label=zip_filename)
    print(f"[+] Successfully uploaded: {release_title}")

  except Exception as e:
    print(f"[!] Error: {e}")
  finally:
    if os.path.exists(torrent_filename):
      os.remove(torrent_filename)
    if os.path.exists(zip_filename):
      os.remove(zip_filename)


if __name__ == "__main__":
  results = search_movies_archive_org(SEARCH_QUERY)
  print(f"[*] Found {len(results)} movies:")
  for i, item in enumerate(results, 1):
    print(f"  [{i}] {item['name']}")

  if not results:
    print("[!] No movies found.")
    sys.exit(0)

  if RESULT_INDEX == 0:
    print("[*] Downloading ALL found movies...")
    for item in results:
      process_and_upload(item)
  elif 1 <= RESULT_INDEX <= len(results):
    selected = results[RESULT_INDEX - 1]
    print(f"[*] User approved movie [{RESULT_INDEX}]: {selected['name']}")
    process_and_upload(selected)
  else:
    print(f"[!] Invalid selection index: {RESULT_INDEX}")
