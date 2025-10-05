import os
import json
import time
import feedparser
import tweepy
from openai import OpenAI
from dotenv import load_dotenv
import requests
import mimetypes
from bs4 import BeautifulSoup

# ==========================
# 🔧 Setup
# ==========================
load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
TWITTER_API_KEY = os.getenv("TWITTER_API_KEY")
TWITTER_API_SECRET = os.getenv("TWITTER_API_SECRET")
TWITTER_ACCESS_TOKEN = os.getenv("TWITTER_ACCESS_TOKEN")
TWITTER_ACCESS_SECRET = os.getenv("TWITTER_ACCESS_SECRET")
GOOGLE_CSE_ID = os.getenv("GOOGLE_CSE_ID")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

# Initialize OpenAI client
client = OpenAI(api_key=OPENAI_API_KEY)

# Initialize Tweepy (Twitter API v2 with OAuth 1.0a for media upload)
auth = tweepy.OAuth1UserHandler(
    consumer_key=TWITTER_API_KEY,
    consumer_secret=TWITTER_API_SECRET,
    access_token=TWITTER_ACCESS_TOKEN,
    access_token_secret=TWITTER_ACCESS_SECRET
)
api = tweepy.API(auth, wait_on_rate_limit=True)  # For media upload
twitter = tweepy.Client(
    consumer_key=TWITTER_API_KEY,
    consumer_secret=TWITTER_API_SECRET,
    access_token=TWITTER_ACCESS_TOKEN,
    access_token_secret=TWITTER_ACCESS_SECRET,
    wait_on_rate_limit=True
)

# ==========================
# 📡 RSS Feed
# ==========================
FEEDS = ["https://www.animenewsnetwork.com/news/rss.xml?ann-edition=us"]

POSTED_FILE = "posted.json"

# ==========================
# 💾 Utility Functions
# ==========================
def load_posted():
    if os.path.exists(POSTED_FILE):
        with open(POSTED_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def save_posted(posted):
    with open(POSTED_FILE, "w", encoding="utf-8") as f:
        json.dump(posted, f, indent=2)

def download_image(url):
    """Download image from URL and save temporarily."""
    try:
        response = requests.get(url, stream=True, timeout=10)
        if response.status_code == 200:
            content_type = response.headers.get('content-type', '')
            extension = mimetypes.guess_extension(content_type) or '.jpg'
            temp_file = f"temp_image{extension}"
            with open(temp_file, 'wb') as f:
                for chunk in response.iter_content(1024):
                    f.write(chunk)
            return temp_file
        return None
    except Exception as e:
        print(f"⚠️ Error downloading image: {e}")
        return None

def scrape_article_image(url):
    """Scrape the article page for an image."""
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            og_image = soup.find('meta', property='og:image')
            if og_image and og_image.get('content'):
                return og_image['content']
            img = soup.find('img', src=True)
            if img and img['src'].startswith('http'):
                return img['src']
        return None
    except Exception as e:
        print(f"⚠️ Error scraping image from {url}: {e}")
        return None

def search_google_image(query):
    """Search Google Custom Search for an image URL."""
    if not GOOGLE_API_KEY or not GOOGLE_CSE_ID:
        print("⚠️ Google Custom Search keys not set.")
        return None
    url = "https://www.googleapis.com/customsearch/v1"
    params = {
        "q": query,
        "cx": GOOGLE_CSE_ID,
        "key": GOOGLE_API_KEY,
        "searchType": "image",
        "num": 1,
        "imgType": "photo",
        "rights": "cc_publicdomain"  # Prefer free-to-use images
    }
    try:
        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data.get("items"):
                return data["items"][0]["link"]
        print(f"⚠️ Google image search failed: {response.status_code} - {response.text}")
        return None
    except Exception as e:
        print(f"⚠️ Google image search error: {e}")
        return None

# ==========================
# 📰 News Fetching
# ==========================
def fetch_latest_news():
    """Fetch latest anime news from ANN RSS, excluding non-news."""
    news_items = []
    for feed_url in FEEDS:
        try:
            feed = feedparser.parse(feed_url)
            print(f"📡 Parsing ANN feed: {len(feed.entries)} entries found.")
            for entry in feed.entries[:5]:  # Latest 5
                title = entry.title
                link = entry.link
                # Debug: Log tags
                tags = [tag.term.lower() for tag in entry.tags] if hasattr(entry, 'tags') else []
                print(f"ℹ️ Entry: {title}, Tags: {tags}")
                # Filter for news
                is_news = False
                exclude_terms = ['review', 'interview', 'column', 'editorial', 'interest']
                if hasattr(entry, 'tags'):
                    is_news = any(tag.term.lower() in ['news', 'press release', 'announcement'] for tag in entry.tags)
                if not is_news and not any(term in title.lower() for term in exclude_terms):
                    is_news = True  # Include if no exclude terms
                if not is_news:
                    print(f"ℹ️ Skipping non-news: {title}")
                    continue
                image_url = None
                if hasattr(entry, 'media_content') and entry.media_content:
                    image_url = entry.media_content[0].get('url')
                elif hasattr(entry, 'enclosures') and entry.enclosures:
                    for enc in entry.enclosures:
                        if enc.get('type', '').startswith('image/'):
                            image_url = enc.get('href')
                            break
                elif hasattr(entry, 'content') and entry.content:
                    soup = BeautifulSoup(entry.content[0].value, 'html.parser')
                    img = soup.find('img')
                    if img and img.get('src'):
                        image_url = img['src']
                if not image_url:
                    image_url = scrape_article_image(link)
                news_items.append({"title": title, "link": link, "image_url": image_url})
        except Exception as e:
            print(f"⚠️ Error fetching {feed_url}: {e}")
    print(f"📈 Fetched {len(news_items)} anime news articles.")
    return news_items

# ==========================
# 🤖 Rewriting Function
# ==========================
def rewrite_news(title):
    """Ask GPT to rewrite the news headline with a natural tone."""
    prompt = (
        f"Rewrite this anime news headline to make it sound more natural and engaging for X (Twitter), "
        f"while keeping it factual and under 240 characters. If it sounds like a rumor, start with 'Rumor:'.\n\n"
        f"Headline: {title}"
    )
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.8,
            max_tokens=100
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"❌ OpenAI error: {e}")
        return title

# ==========================
# 🐦 Tweeting
# ==========================
def post_tweet(text, image_url, fallback_query):
    if len(text) > 280:
        text = text[:277] + "..."
    final_image_url = image_url
    if not final_image_url:
        print(f"🔄 No RSS/article image; using Google image search for '{fallback_query}'.")
        final_image_url = search_google_image(fallback_query)
    if not final_image_url:
        print("⚠️ No image found; skipping tweet.")
        return False
    try:
        temp_file = download_image(final_image_url)
        if temp_file:
            try:
                media = api.media_upload(temp_file)
                twitter.create_tweet(text=text, media_ids=[media.media_id])
                print(f"✅ Posted with image: {text[:100]}...")
                return True
            finally:
                os.remove(temp_file)
        else:
            print(f"⚠️ Image download failed for {final_image_url}; skipping tweet.")
            return False
    except Exception as e:
        print(f"❌ Tweet failed: {e}")
        return False

# ==========================
# 🚀 Main Bot
# ==========================
def run_bot():
    posted = load_posted()
    news_list = fetch_latest_news()

    if not news_list:
        print("⚠️ No anime news articles found; skipping run.")
        return

    for item in news_list:
        if item["link"] in posted:
            continue

        tweet_text = rewrite_news(item["title"])
        success = post_tweet(tweet_text, item["image_url"], f"anime {tweet_text}")
        if success:
            posted.append(item["link"])
            save_posted(posted)
            break  # One per run
    else:
        print("⚠️ No new news articles; try next run.")

if __name__ == "__main__":
    try:
        run_bot()
    except Exception as e:
        print(f"❌ Bot crashed: {e}")
