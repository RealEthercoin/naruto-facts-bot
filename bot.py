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
openai.api_key = OPENAI_API_KEY
client = openai.OpenAI(api_key=OPENAI_API_KEY)

# Initialize Tweepy client
twitter = tweepy.Client(
    consumer_key=TWITTER_API_KEY,
    consumer_secret=TWITTER_API_SECRET,
    access_token=TWITTER_ACCESS_TOKEN,
    access_token_secret=TWITTER_ACCESS_SECRET,
    wait_on_rate_limit=True
)

HASHTAGS = "#AnimeFacts #Weeb #Otaku"
FACTS_FILE = "facts.json"
MODEL_PRIORITY = ["gpt-4o-mini", "gpt-3.5-turbo"]
FALLBACK_FACT = "Did you know? The first anime ever created was 'Namakura Gatana' in 1917, making anime over a century old!"

def load_facts():
    """Load previously posted facts."""
    if os.path.exists(FACTS_FILE):
        try:
            with open(FACTS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError:
            return []
    return []

def save_fact(fact):
    """Save a posted fact."""
    facts = load_facts()
    facts.append(fact)
    with open(FACTS_FILE, "w", encoding="utf-8") as f:
        json.dump(facts, f, indent=2, ensure_ascii=False)

def generate_fact(max_retries=3):
    """Generate one unique anime fact."""
    posted_facts = load_facts()
    recent_facts = posted_facts[-200:] if len(posted_facts) > 0 else []
    prompt = (
        "Give me one unique, interesting fact about any anime or manga (not limited to Naruto or Boruto). "
        "The fact should be under 240 characters. Avoid repeating facts similar to this list: "
        f"{recent_facts}"
    )

    for model in MODEL_PRIORITY:
        for attempt in range(max_retries):
            try:
                response = openai.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=100,
                    temperature=0.8
                )
                fact = response.choices[0].message.content.strip()

                # Ensure uniqueness
                if fact in posted_facts:
                    print("⚠️ Fact already posted. Retrying...")
                    continue

                # Hard enforce tweet length
                tweet_preview = f"{fact} {HASHTAGS}"
                if len(tweet_preview) > 280:
                    # Try cutting at sentence boundaries or ellipsis cleanly
                    allowed = 280 - len(HASHTAGS) - 1
                    if '.' in fact[:allowed]:
                        fact = fact[:allowed].rsplit('.', 1)[0] + '.'
                    else:
                        fact = fact[:allowed - 3].rstrip() + "..."
                
                return fact

            except openai.error.OpenAIError as e:
                print(f"❌ OpenAI error: {e}")
                if attempt < max_retries - 1:
                    time.sleep(5)
                continue

    print("❌ Failed to generate fact with all models.")
    return FALLBACK_FACT

def post_fact(fact):
    """Post fact to Twitter."""
    if not fact:
        print("⚠️ No fact to post.")
        return

    tweet_text = f"{fact} {HASHTAGS}"
    if len(tweet_text) > 280:
        allowed = 280 - len(HASHTAGS) - 1
        tweet_text = fact[:allowed - 3].rstrip() + "..." + " " + HASHTAGS

    try:
        twitter.create_tweet(text=tweet_text)
        save_fact(fact)
        print(f"✅ Tweet posted successfully:\n{tweet_text}")
    except tweepy.TweepyException as e:
        print(f"❌ Twitter error: {e}")

def run_bot():
    fact = generate_fact()
    post_fact(fact)

if __name__ == "__main__":
    run_bot()
