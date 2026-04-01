import yt_dlp

def test_search(q):
    ydl_opts = {
        'quiet': True,
        'extract_flat': 'in_playlist',
        'skip_download': True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(f"ytsearch3:{q}", download=False)
        entries = info.get('entries', [])
        for entry in entries:
            print(f"ID: {entry.get('id')} | Title: {entry.get('title')}")

if __name__ == "__main__":
    test_search("interstellar soundtrack")
