import os
import requests

# 1. Create fonts directory
if not os.path.exists("fonts"):
    os.makedirs("fonts")

# 2. URLs for Roboto (Google's standard font)
fonts = {
    "Roboto-Bold.ttf": "https://github.com/google/fonts/raw/main/apache/roboto/Roboto-Bold.ttf",
    "Roboto-Regular.ttf": "https://github.com/google/fonts/raw/main/apache/roboto/Roboto-Regular.ttf",
    "Roboto-Italic.ttf": "https://github.com/google/fonts/raw/main/apache/roboto/Roboto-Italic.ttf"
}

print("Downloading fonts...")
for name, url in fonts.items():
    print(f"Fetching {name}...")
    r = requests.get(url)
    with open(f"fonts/{name}", "wb") as f:
        f.write(r.content)

print("Done! You now have a 'fonts' folder.")