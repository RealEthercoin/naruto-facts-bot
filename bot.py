import os
import json
import openai
import tweepy
import time
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Retrieve and validate environment variables
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
TWITTER_API_KEY = os.getenv("TWITTER_API_KEY")
TWITTER_API_SECRET = os.getenv("TWITTER_API_SECRET")
TWITTER_ACCESS_TOKEN = os.getenv("TWITTER_ACCESS_TOKEN")
TWITTER_ACCESS_SECRET = os.getenv("TWITTER_ACCESS_SECRET")

# Validate environment variables
required_vars = {
    "OPENAI_API_KEY": OPENAI_API_KEY,
    "TWITTER_API_KEY": TWITTER_API_KEY,
    "TWITTER_API_SECRET": TWITTER_API_SECRET,
    "TWITTER_ACCESS_TOKEN": TWITTER_ACCESS_TOKEN,
    "TWITTER_ACCESS_SECRET": TWITTER_ACCESS_SECRET,
}
for var_name, var_value in required_vars.items():
    if not var_value:
        raise ValueError(f"❌ {var_name} is not set in .env file")

# Initialize OpenAI client
try:
    openai.api_key = OPENAI_API_KEY
    client = openai.OpenAI(api_key=OPENAI_API_KEY)
    client.models.list()  # Test API key
    print("✅ OpenAI authentication successful")
except openai.AuthenticationError as e:
    raise ValueError(f"❌ OpenAI authentication failed: {e}")
except Exception as e:
    raise ValueError(f"❌ OpenAI initialization failed: {e}")

# Initialize Tweepy v2 Client with OAuth 1.0a User Context
try:
    twitter = tweepy.Client(
        consumer_key=TWITTER_API_KEY,
        consumer_secret=TWITTER_API_SECRET,
        access_token=TWITTER_ACCESS_TOKEN,
        access_token_secret=TWITTER_ACCESS_SECRET,
        wait_on_rate_limit=True
    )
    twitter.get_me()  # Test authentication (requires Basic tier or higher for full access)
    print("✅ Twitter authentication successful")
except tweepy.TweepyException as e:
    raise ValueError(f"❌ Twitter authentication failed: {e}")

HASHTAGS = "#NARUTO #BORUTO"
FACTS_FILE = "facts.json"
MODEL_PRIORITY = ["gpt-4o-mini", "gpt-3.5-turbo"]
FALLBACK_FACT = "Naruto's favorite food is ramen, especially from Ichiraku Ramen!"

def load_facts():
    """Load facts from JSON file."""
    if os.path.exists(FACTS_FILE):
        try:
            with open(FACTS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            print(f"❌ Error reading facts file: {e}")
            return []
    return []

def save_fact(fact):
    """Save a new fact to the JSON file."""
    facts = load_facts()
    facts.append(fact)
    try:
        with open(FACTS_FILE, "w", encoding="utf-8") as f:
            json.dump(facts, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"❌ Error saving fact: {e}")

def generate_fact(max_retries=3):
    """Generate a unique fact using OpenAI with retries."""
    posted_facts = load_facts()
    prompt = (
        "Give me one unique, interesting fact about Naruto or Boruto anime/manga. "
        "Keep it under 240 characters. Do not repeat any facts from this list: "
        f"{posted_facts[-200:]}"
    )
    for model in MODEL_PRIORITY:
        for attempt in range(max_retries):
            try:
                response = openai.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=80,  # Reduced to conserve tokens
                    temperature=0.8
                )
                fact = response.choices[0].message.content.strip()
                if fact in posted_facts:
                    print(f"⚠️ Fact already posted: {fact}")
                    continue
                if len(fact) > 240:
                    print(f"⚠️ Fact too long ({len(fact)} characters), trimming...")
                    fact = fact[:237] + "..."  # Trim to fit
                return fact
            except openai.RateLimitError as e:
                print(f"⚠️ Rate limit error with {model} (attempt {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    time.sleep(10)  # Wait before retrying
                continue
            except openai.AuthenticationError as e:
                print(f"❌ Authentication error with {model}: {e}")
                break
            except openai.OpenAIError as e:
                print(f"❌ OpenAI error with {model}: {e}")
                break
    print("❌ Failed to generate fact with all models")
    return FALLBACK_FACT  # Use fallback fact if all attempts fail

def post_fact(fact):
    """Post a fact to Twitter using v2 API."""
    if not fact:
        print("⚠️ No fact to post.")
        return
    tweet_text = f"{fact} {HASHTAGS}"
    if len(tweet_text) > 280:
        tweet_text = tweet_text[:277] + "..."
    try:
        twitter.create_tweet(text=tweet_text)
        save_fact(fact)
        print(f"✅ Posted tweet: {tweet_text}")
    except tweepy.TweepyException as e:
        print(f"❌ Error posting tweet: {e}")

def run_bot():
    """Run the bot to generate and post a fact."""
    fact = generate_fact()
    post_fact(fact)

if __name__ == "__main__":
    try:
        run_bot()
    except Exception as e:
        print(f"❌ Bot failed: {e}")
