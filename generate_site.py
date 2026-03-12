import os
import requests
import time
import json

# Configuration
OUTPUT_DIR = "public"
SERIES_DIR = os.path.join(OUTPUT_DIR, "series") 
IGNORE_DIRS =[".git", ".github", "public", "__pycache__"]
CONFIG_FILE = "config.json"

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"⚠️ Error reading config.json: {e}")
    return {}

def fetch_info(series_folder_name, session, config):
    series_conf = config.get(series_folder_name, {})

    if "title" in series_conf and "cover" in series_conf:
        print(f"    -> Using custom override: {series_conf['title']}")
        return series_conf["title"], series_conf["cover"]

    search_term = series_folder_name.replace('_', ' ').replace('-', ' ')
    media_type = series_conf.get("type", "ANIME")
    
    query = '''
    query ($search: String, $type: MediaType) {
      Media (search: $search, type: $type) {
        title { english romaji }
        coverImage { large }
      }
    }
    '''
    url = 'https://graphql.anilist.co'
    
    attempts = 0
    max_attempts = 3
    # We use a while loop to handle rate limits without consuming our 'error' attempts
    while attempts < max_attempts:
        try:
            response = session.post(
                url, 
                json={'query': query, 'variables': {'search': search_term, 'type': media_type}}, 
                timeout=15
            )

            if response.status_code == 429:
                # If rate limited, wait at least 5 seconds even if header says 0
                wait_time = int(response.headers.get('Retry-After', 60))
                sleep_duration = max(wait_time, 5)
                print(f"    ⚠️ Rate limit hit! Waiting {sleep_duration} seconds before retrying...")
                time.sleep(sleep_duration)
                continue # Retry this same request without incrementing 'attempts'

            response.raise_for_status()
            data = response.json()

            if data and data.get('data'):
                media = data['data'].get('Media')
                if media:
                    title_data = media.get('title') or {}
                    title = title_data.get('english') or title_data.get('romaji') or search_term
                    cover_data = media.get('coverImage') or {}
                    cover = cover_data.get('large') or "https://via.placeholder.com/200x300?text=No+Cover"
                    
                    # Small delay after success to stay under the 90/min limit
                    time.sleep(0.8) 
                    return title, cover

            break # No media found, exit loop

        except Exception as e:
            attempts += 1
            print(f"    ⚠️ Attempt {attempts} failed for {series_folder_name}: {e}")
            time.sleep(2)
            
    return search_term, "https://via.placeholder.com/200x300?text=No+Cover"

def main():
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)
    
    if not os.path.exists(SERIES_DIR):
        os.makedirs(SERIES_DIR)
        print(f"Created {SERIES_DIR}. Please move your series folders there!")
        return

    config = load_config()
    series_data =[]

    # Write CSS
    with open(os.path.join(OUTPUT_DIR, "style.css"), "w") as f:
        f.write("""
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #121212; color: #ffffff; margin: 0; padding: 0; text-align: center; }
        .header-container { padding: 40px 20px; background-color: #1a1a1a; margin-bottom: 30px; border-bottom: 2px solid #333; }
        h1 { font-size: 2.5em; margin: 0 0 10px 0; color: #e0e0e0; }
        h2 { font-size: 1.2em; font-weight: 400; color: #a0a0a0; margin: 0; }
        #searchBar { width: 80%; max-width: 400px; padding: 12px 20px; margin: 20px 0; border-radius: 25px; border: 1px solid #444; background: #222; color: white; font-size: 16px; outline: none; transition: border-color 0.2s; }
        #searchBar:focus { border-color: #007bff; }
        .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 25px; max-width: 1200px; margin: 0 auto; padding: 0 20px 50px 20px; }
        .card { background: #1e1e1e; border-radius: 12px; overflow: hidden; text-decoration: none; color: white; transition: transform 0.2s, box-shadow 0.2s; display: flex; flex-direction: column; }
        .card:hover { transform: translateY(-5px); box-shadow: 0 10px 20px rgba(0,0,0,0.5); }
        .card img { width: 100%; height: 300px; object-fit: cover; }
        .card .title { padding: 15px; font-weight: bold; font-size: 1.1em; background: #222; flex-grow: 1; display: flex; align-items: center; justify-content: center; text-transform: capitalize; }
        .badge-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 15px; max-width: 1200px; margin: 0 auto; padding: 20px; }
        .badge-grid img { width: 100%; height: auto; border-radius: 8px; background: #222; cursor: pointer; transition: transform 0.2s; }
        .badge-grid img:hover { transform: scale(1.05); }
        .back-btn { position: absolute; top: 20px; left: 20px; width: 40px; height: 40px; display: flex; align-items: center; justify-content: center; color: #fff; text-decoration: none; background: #333; border-radius: 50%; z-index: 100; }
        .modal { position: fixed; z-index: 1000; left: 0; top: 0; width: 100%; height: 100%; background-color: rgba(0,0,0,0.8); display: flex; align-items: center; justify-content: center; opacity: 0; visibility: hidden; transition: opacity 0.3s, visibility 0.3s; }
        .modal.show { opacity: 1; visibility: visible; }
        .modal-content { max-width: 90%; max-height: 90%; border-radius: 8px; }
        .close { position: absolute; top: 20px; right: 30px; color: #f1f1f1; font-size: 40px; font-weight: bold; cursor: pointer; }
        """)

    session = requests.Session()
    valid_dirs =[d for d in os.listdir(SERIES_DIR) if os.path.isdir(os.path.join(SERIES_DIR, d)) and not d.startswith('.')]
    print(f"Found {len(valid_dirs)} folders in {SERIES_DIR} to process...\n")

    for index, series in enumerate(valid_dirs, 1):
        print(f"[{index}/{len(valid_dirs)}] Processing: {series}")
        title, cover_url = fetch_info(series, session, config)
        
        current_series_path = os.path.join(SERIES_DIR, series)
        images =[img for img in os.listdir(current_series_path) if img.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp'))]
        images.sort()
        
        series_data.append({'id': series, 'title': title, 'cover': cover_url, 'images': images})

        series_html_path = os.path.join(OUTPUT_DIR, f"{series}.html")
        with open(series_html_path, "w", encoding="utf-8") as f:
            f.write(f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title} - croixph's badges</title><link rel="stylesheet" href="style.css">
</head>
<body>
    <a href="index.html" class="back-btn"><svg fill="currentColor" viewBox="0 0 24 24" width="24" height="24"><path d="M20 11H7.83l5.59-5.59L12 4l-8 8 8 8 1.41-1.41L7.83 13H20v-2z"></path></svg></a>
    <div class="header-container"><h2 style="color: white;">{title}</h2></div>
    <div class="badge-grid">
""")
            for img in images:
                f.write(f'        <img src="series/{series}/{img}" alt="{img}" loading="lazy" onclick="openModal(this.src)">\n')
            f.write("""    </div>
    <div id="imageModal" class="modal" onclick="closeModal()"><span class="close" onclick="closeModal()">&times;</span><img class="modal-content" id="modalImg"></div>
    <script>
        function openModal(src) { document.getElementById('modalImg').src = src; document.getElementById('imageModal').classList.add('show'); }
        function closeModal() { document.getElementById('imageModal').classList.remove('show'); }
    </script>
</body></html>""")

    series_data.sort(key=lambda x: str(x['title']).lower())

    index_html_path = os.path.join(OUTPUT_DIR, "index.html")
    with open(index_html_path, "w", encoding="utf-8") as f:
        f.write("""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>croixph's badges</title><link rel="stylesheet" href="style.css">
</head>
<body>
    <div class="header-container">
        <h1>croixph's badges</h1>
        <input type="text" id="searchBar" onkeyup="filterSeries()" placeholder="Search series...">
        <h2 style="font-size:1em;">Category names are based on the AniList ENGLISH title.<br>Exceptions include collection series (e.g. Fate, Monogatari) and anything not on AniList.<br>In that case, follow your heart.</h2>
    </div>
    <div class="grid" id="seriesGrid">
""")
        for data in series_data:
            f.write(f"""        <a href="{data['id']}.html" class="card">
            <img src="{data['cover']}" alt="{data['title']}" loading="lazy">
            <div class="title">{data['title']}</div>
        </a>\n""")
        
        f.write("""    </div>
    <script>
        function filterSeries() {
            const input = document.getElementById('searchBar');
            const filter = input.value.toLowerCase();
            const cards = document.getElementsByClassName('card');
            for (let i = 0; i < cards.length; i++) {
                const title = cards[i].querySelector('.title').innerText.toLowerCase();
                cards[i].style.display = title.includes(filter) ? "" : "none";
            }
        }
    </script>
</body></html>""")
    
    print("\nAll pages generated successfully!")

if __name__ == "__main__":
    main()