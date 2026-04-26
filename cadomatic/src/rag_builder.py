import os
import time
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_community.embeddings import HuggingFaceEmbeddings

from requests.adapters import HTTPAdapter

# For newer versions of requests (>=2.28), use this safe import:
try:
    from requests.packages.urllib3.util.retry import Retry
except ImportError:
    # Fallback if requests doesn't bundle urllib3 (rare)
    from urllib3.util.retry import Retry

BASE_URL_WIKI = "https://wiki.freecad.org/Power_users_hub"
BASE_URL_GITHUB = "https://github.com/shaise/FreeCAD_FastenersWB"
ASSEMBLE_WB_URL = "https://wiki.freecad.org/Assembly_Workbench"

DOMAIN_WHITELIST = [
    "https://wiki.freecad.org",
    "https://github.com/shaise"
]

LANG_IDENTIFIERS = [
    "/id", "/de", "/tr", "/es", "/fr", "/hr", "/it", "/pl",
    "/pt", "/pt-br", "/ro", "/fi", "/sv", "/cs", "/ru", "/zh-cn",
    "/zh-tw", "/ja", "/ko", '/lt', '/hu', '/bg', '/uk', '/ar', '/zh', '/sk'
]

CHECKPOINT_INTERVAL = 500  # save every 500 pages

VECTORSTORE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../vectorstore")
os.makedirs(VECTORSTORE_PATH, exist_ok=True)

def get_url_with_retry(url, timeout=10, max_retries=3, backoff_factor=0.5):
    session = requests.Session()
    
    retry_strategy = Retry(
        total=max_retries,
        status_forcelist=[429, 500, 502, 503, 504],
        backoff_factor=backoff_factor,
        raise_on_status=False
    )
    
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    
    try:
        response = session.get(url, timeout=timeout)
        response.raise_for_status()
        return response
    finally:
        session.close()

def is_excluded_url(url):
    url_lower = url.lower()
    if "wiki.freecad.org" in url_lower:
        if any(lang in url_lower for lang in LANG_IDENTIFIERS):
            return True
    return (
        ".jpg" in url_lower or
        ".png" in url_lower or
        "edit&section" in url_lower or
        'wiki.freecad.org/index.php' in url_lower or
        'wiki.freecad.org/help:introduction' in url_lower or
        'wiki.freecad.org/interesting_links' in url_lower or
        '#' in url_lower or
        'assembly2' in url_lower or
        'assembly3' in url_lower or
        'assembly4' in url_lower or
        'assembly5' in url_lower or
        'wiki.freecad.org/special:' in url_lower or
        'wiki.freecad.org/template:' in url_lower or
        'wiki.freecad.org/user:' in url_lower or
        'github.com/shaise' in url_lower and ('github.com/shaise/freeCAD_fastenerswb' not in url_lower and 'https://github.com/shaise/freeCAD_fastenerswb' not in url_lower) or
        'github.com/shaise' in url_lower and (
            "/search?" in url_lower or
            "/tree/" in url_lower or
            "/commits/" in url_lower or
            "/branches" in url_lower or
            "/tags" in url_lower or
            "?tab=" in url_lower or
            "?direction=" in url_lower or
            "/activity" in url_lower or
            "/network/" in url_lower or
            "/stargazers?" in url_lower or
            "/watchers" in url_lower            
        )
    )

def crawl_wiki(start_url, max_pages):
    visited = set()
    to_visit = [start_url]
    pages = []

    while to_visit and len(visited) < max_pages:
        url = to_visit.pop(0)
        if url in visited or is_excluded_url(url):
            continue
        time.sleep(0.5) #dont spam requests
        try:
            print(f"Fetching: {url}")
            visited.add(url)
            res = get_url_with_retry(url, timeout=3, max_retries=3, backoff_factor=0.5)
            res.raise_for_status()
            soup = BeautifulSoup(res.text, "html.parser")

            tags_to_exclude = ["script", "style", "header", "footer", "nav", "aside"]
            if 'wiki.freecad.org' in url:
                content_div = soup.find("div", id="mw-content-text")
                if content_div:
                    for tag in content_div(tags_to_exclude):
                        tag.extract()

                    lang_banner = content_div.find("div", class_="mw-pt-languages")
                    if lang_banner:
                        lang_banner.decompose()  # remove from tree

                    text = content_div.get_text(separator='\n', strip=True)
                else:
                    text = ""
            else:
                for tag in soup(tags_to_exclude):
                    tag.extract()
                text = soup.get_text(separator="\n")

            clean = "\n".join([line.strip() for line in text.splitlines() if line.strip()])

            if clean == '':
                print("url has no parsed text:", url)
            else:
                pages.append({"url": url, "text": clean})

            # Queue internal links
            for a in soup.find_all("a", href=True):
                full = urljoin(url, a["href"])
                if any(full.startswith(domain) for domain in DOMAIN_WHITELIST):
                    if full not in visited and not is_excluded_url(full):
                        to_visit.append(full)

            # --- Checkpoint: save every N pages ---
            if len(pages) % CHECKPOINT_INTERVAL == 0:
                save_vectorstore_checkpoint(pages, checkpoint_suffix=f"checkpoint_{len(pages)}")
                print(f"Checkpoint saved after {len(pages)} pages")
        except Exception as e:
            print(f"Error fetching {url}: {e}")

    return pages

def save_vectorstore_checkpoint(pages, checkpoint_suffix="latest"):
    texts = [p["text"] for p in pages]
    metadatas = [{"source": p["url"]} for p in pages]

    splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=150)
    docs = splitter.create_documents(texts, metadatas=metadatas)

    embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
    vectorstore = FAISS.from_documents(docs, embeddings)

    checkpoint_path = os.path.join(VECTORSTORE_PATH, checkpoint_suffix)
    os.makedirs(checkpoint_path, exist_ok=True)
    vectorstore.save_local(checkpoint_path)

def build_vectorstore():
    wiki_pages = crawl_wiki(BASE_URL_WIKI, max_pages=2000)
    assemble_pages = crawl_wiki(ASSEMBLE_WB_URL, max_pages=100)
    github_pages = crawl_wiki(BASE_URL_GITHUB, max_pages=450)
    
    all_pages = wiki_pages + assemble_pages + github_pages

    if not all_pages:
        print("No pages crawled. Exiting.")
        return

    # Final save
    save_vectorstore_checkpoint(all_pages, checkpoint_suffix="final")
    print(f"Vectorstore fully saved to {VECTORSTORE_PATH}/final")

if __name__ == "__main__":
    build_vectorstore()
