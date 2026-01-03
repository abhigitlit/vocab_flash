import praw
import time
import schedule
import os
import sys
import vocabdaily

# --- 1. REDDIT CONFIGURATION ---
REDDIT_CONFIG = {
    "client_id": os.getenv("REDDIT_CLIENT_ID"),
    "client_secret": os.getenv("REDDIT_CLIENT_SECRET"),
    "user_agent": "script:vocabdaily_bot:v1.0 (by u/YOUR_USERNAME)",
    "username": os.getenv("REDDIT_USERNAME"),
    "password": os.getenv("REDDIT_PASSWORD")
}

SUBREDDIT_NAME = "Vocabdaily"

def job():
    print(f"\n--- Starting Scheduled Job: {time.strftime('%Y-%m-%d %H:%M:%S')} ---", flush=True)
    try:
        if not REDDIT_CONFIG["client_id"]:
            print("ERROR: Reddit API credentials missing! Check Environment Variables.", flush=True)
            return

        # 1. Initialize Reddit
        reddit = praw.Reddit(**REDDIT_CONFIG)
        subreddit = reddit.subreddit(SUBREDDIT_NAME)

        # 2. Generate Content
        print("Generating vocabulary card...", flush=True)
        image_path, data = vocabdaily.generate_content()

        if image_path and data:
            title = f"Word of the Hour: {data['term'].capitalize()} ({data['pos']})"
            print(f"Uploading to r/{SUBREDDIT_NAME}...", flush=True)
            
            # 3. Upload
            subreddit.submit_image(title=title, image_path=image_path)
            print(f"Posted successfully: {title}", flush=True)
            
            # Cleanup
            if os.path.exists(image_path):
                os.remove(image_path)
                print("Cleaned up local image file.", flush=True)
        else:
            print("Failed to generate content. Skipping this cycle.", flush=True)

    except Exception as e:
        print(f"CRITICAL ERROR: {e}", flush=True)

# --- 2. SCHEDULING ---
# Run every hour
schedule.every().hour.do(job)

print(f"Bot started for r/{SUBREDDIT_NAME}...", flush=True)
print("Waiting for next scheduled run...", flush=True)

# Run once immediately on startup? 
# Uncomment the next line if you want it to post IMMEDIATELY when deployed:
# job()

while True:
    schedule.run_pending()
    time.sleep(60)