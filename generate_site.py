import os
import requests
import time
import json

# Configuration
OUTPUT_DIR = "public"
SERIES_DIR = os.path.join(OUTPUT_DIR, "series") 
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
    while attempts < 3:
        try:
            response = session.post(url, json={'query': query, 'variables': {'search': search_term, 'type': media_type}}, timeout=15)
            if response.status_code == 429:
                wait_time = max(int(response.headers.get('Retry-After', 60)), 5)
                time.sleep(wait_time)
                continue
            response.raise_for_status()
            data = response.json()
            if data and data.get('data'):
                media = data['data'].get('Media')
                if media:
                    t = (media.get('title') or {})
                    title = t.get('english') or t.get('romaji') or search_term
                    c = (media.get('coverImage') or {})
                    cover = c.get('large') or "https://via.placeholder.com/200x300?text=No+Cover"
                    time.sleep(0.8) 
                    return title, cover
            break
        except Exception:
            attempts += 1
            time.sleep(2)
            
    return search_term, "https://via.placeholder.com/200x300?text=No+Cover"

def main():
    if not os.path.exists(OUTPUT_DIR): os.makedirs(OUTPUT_DIR)
    if not os.path.exists(SERIES_DIR):
        os.makedirs(SERIES_DIR)
        print(f"Created {SERIES_DIR}. Please move your series folders there!")
        return

    config = load_config()
    series_data = []
    session = requests.Session()
    valid_dirs = [d for d in os.listdir(SERIES_DIR) if os.path.isdir(os.path.join(SERIES_DIR, d)) and not d.startswith('.')]

    print(f"Found {len(valid_dirs)} folders to process...")
    for index, series in enumerate(valid_dirs, 1):
        print(f"[{index}/{len(valid_dirs)}] Processing: {series}")
        title, cover_url = fetch_info(series, session, config)
        
        current_series_path = os.path.join(SERIES_DIR, series)
        images = sorted([img for img in os.listdir(current_series_path) if img.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp'))])
        
        series_data.append({'id': series, 'title': title, 'cover': cover_url, 'images': images})

    series_data.sort(key=lambda x: str(x['title']).lower())

    # Bundle everything into one HTML file
    index_html_path = os.path.join(OUTPUT_DIR, "index.html")
    json_payload = json.dumps(series_data)
    
    with open(index_html_path, "w", encoding="utf-8") as f:
        f.write(f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>croixph's badges</title>
    <script src="https://unpkg.com/vue@3/dist/vue.global.prod.js"></script>
    <style>
        body {{ font-family: 'Segoe UI', sans-serif; background-color: #121212; color: #ffffff; margin: 0; padding: 0; }}
        .header-container {{ padding: 40px 20px; background-color: #1a1a1a; border-bottom: 2px solid #333; text-align: center; }}
        h1 {{ font-size: 2.5em; margin: 0 0 10px 0; color: #e0e0e0; }}
        #searchBar {{ width: 80%; max-width: 400px; padding: 12px 20px; margin: 20px 0; border-radius: 25px; border: 1px solid #444; background: #222; color: white; font-size: 16px; outline: none; }}
        .grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 25px; max-width: 1200px; margin: 30px auto; padding: 0 20px; }}
        .card {{ background: #1e1e1e; border-radius: 12px; overflow: hidden; text-decoration: none; color: white; transition: 0.2s; display: flex; flex-direction: column; cursor: pointer; }}
        .card:hover {{ transform: translateY(-5px); box-shadow: 0 10px 20px rgba(0,0,0,0.5); }}
        .card img {{ width: 100%; height: 300px; object-fit: cover; }}
        .card .title {{ padding: 15px; font-weight: bold; background: #222; flex-grow: 1; display: flex; align-items: center; justify-content: center; }}
        .badge-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 15px; max-width: 1200px; margin: 0 auto; padding: 20px; }}
        .badge-grid img {{ width: 100%; border-radius: 8px; cursor: pointer; transition: 0.2s; background: #222; }}
        .badge-grid img:hover {{ transform: scale(1.05); }}
        .back-btn {{ position: fixed; top: 20px; left: 20px; width: 40px; height: 40px; background: #333; border-radius: 50%; display: flex; align-items: center; justify-content: center; z-index: 100; cursor: pointer; border: none; color: white; }}
        .modal {{ position: fixed; z-index: 1000; left: 0; top: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.9); display: flex; align-items: center; justify-content: center; }}
        .modal img {{ max-width: 90%; max-height: 90%; border-radius: 8px; }}
        [v-cloak] {{ display: none; }}
    </style>
</head>
<body>
    <div id="app" v-cloak>
        <div v-if="!activeId">
            <div class="header-container">
                <h1>croixph's badges</h1>
                <input type="text" v-model="search" id="searchBar" placeholder="Search series...">
                <h2 style="font-size: 0.8em; color: #a0a0a0; font-weight: 400;">Category names are based on the AniList ENGLISH title.<br>Exceptions include collection series (e.g. Fate, Monogatari) and anything not on AniList.<br>In that case, follow your heart.</h2>
            </div>
            <div class="grid">
                <a v-for="s in filteredSeries" :key="s.id" :href="'#' + encodeURIComponent(s.id)" class="card">
                    <img :src="s.cover" :alt="s.title" loading="lazy">
                    <div class="title">{{{{ s.title }}}}</div>
                </a>
            </div>
        </div>

        <div v-else>
            <button class="back-btn" @click="goHome">
                <svg fill="currentColor" viewBox="0 0 24 24" width="24" height="24"><path d="M20 11H7.83l5.59-5.59L12 4l-8 8 8 8 1.41-1.41L7.83 13H20v-2z"></path></svg>
            </button>
            <div class="header-container">
                <h2>{{{{ currentSeries?.title || 'Loading...' }}}}</h2>
            </div>
            <div class="badge-grid" v-if="currentSeries">
                <img v-for="img in currentSeries.images" 
                     :key="img" 
                     :src="'series/' + currentSeries.id + '/' + img" 
                     @click="selectedImg = 'series/' + currentSeries.id + '/' + img">
            </div>
        </div>

        <div v-if="selectedImg" class="modal" @click="selectedImg = null">
            <img :src="selectedImg">
        </div>
    </div>

    <script>
        const {{ createApp, ref, computed, onMounted }} = Vue;
        const seriesData = {json_payload};

        createApp({{
            setup() {{
                const search = ref('');
                const activeId = ref('');
                const selectedImg = ref(null);

                const getHash = () => decodeURIComponent(window.location.hash.replace('#', ''));

                const filteredSeries = computed(() => 
                    seriesData.filter(s => s.title.toLowerCase().includes(search.value.toLowerCase()))
                );

                const currentSeries = computed(() => 
                    seriesData.find(s => s.id === activeId.value)
                );

                const goHome = () => {{ window.location.hash = ''; }};

                const updateRoute = () => {{
                    activeId.value = getHash();
                    window.scrollTo(0, 0);
                }};

                onMounted(() => {{
                    window.addEventListener('hashchange', updateRoute);
                    updateRoute(); // Initial check
                }});

                return {{ search, activeId, filteredSeries, currentSeries, goHome, selectedImg }};
            }}
        }}).mount('#app');
    </script>
</body>
</html>""")
    
    print(f"\nSuccess! Site generated at {index_html_path}")

if __name__ == "__main__":
    main()