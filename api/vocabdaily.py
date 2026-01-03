from http.server import BaseHTTPRequestHandler
import json
import os
import requests
from PIL import Image, ImageDraw, ImageFont
import textwrap
import io

GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

# --- 1. DIRECT FONT LOADER ---
def get_font(font_filename, size):
    # This looks for fonts in the "fonts" folder in your project root
    font_path = os.path.join(os.getcwd(), 'fonts', font_filename)
    
    try:
        return ImageFont.truetype(font_path, size)
    except OSError:
        # If the filename is wrong, it prints what it was looking for so you can fix it
        print(f"ERROR: Could not find font at: {font_path}")
        return ImageFont.load_default()

# --- 2. FETCH DATA ---
def fetch_source_data():
    try:
        r = requests.get("https://vocabdaily.vercel.app/get", timeout=4)
        r.raise_for_status()
        return r.json()['data']
    except:
        return None

# --- 3. ENRICH DATA ---
def get_groq_enrichment(source_data):
    if not source_data: return None
    if not GROQ_API_KEY: return {**source_data, "pos": "noun", "examples": ["No API Key"]}

    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    
    prompt = f"""Analyze "{source_data['term']}". Return JSON: {{"term": "{source_data['term']}", "pos": "noun", "meaning": "def", "derivatives": [], "synonyms": ["a","b"], "examples": ["ex"]}}"""
    
    try:
        payload = {
            "model": "llama-3.1-8b-instant",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.3
        }
        res = requests.post(url, headers=headers, json=payload, timeout=8)
        content = res.json()['choices'][0]['message']['content']
        return json.loads(content.replace('```json', '').replace('```', '').strip())
    except:
        return {**source_data, "pos": "word", "examples": ["Enrichment failed"]}

# --- 4. GENERATE IMAGE ---
def create_vocab_card_bytes(data):
    SCALE = 2
    W, H = 1200 * SCALE, 1400 * SCALE
    img = Image.new("RGB", (W, H), color="#FFFFFF")
    draw = ImageDraw.Draw(img)

    # --- UPDATE THESE NAMES TO MATCH YOUR UPLOADED FILES ---
    # Example: If you uploaded "arial.ttf", change "Roboto-Bold.ttf" to "arial.ttf"
    title_font = get_font("Roboto-Bold.ttf", int(125 * SCALE)) 
    body_font  = get_font("Roboto-Regular.ttf", int(48 * SCALE))
    pos_font   = get_font("Roboto-Italic.ttf", int(57 * SCALE))

    # Draw
    margin_x = int(80 * SCALE)
    cursor_y = int(50 * SCALE)
    
    term = data.get('term', 'Error').capitalize()
    draw.text((margin_x, cursor_y), term, font=title_font, fill="black")
    
    try:
        bbox = draw.textbbox((0,0), term, font=title_font)
        title_h = bbox[3] - bbox[1]
    except:
        title_h = int(120 * SCALE)

    draw.text((margin_x, cursor_y + title_h + int(20*SCALE)), 
              data.get('pos', 'noun'), font=pos_font, fill="gray")
    
    cursor_y += title_h + int(80 * SCALE)

    wrapped = textwrap.wrap(data.get('meaning', ''), width=50)
    for line in wrapped:
        draw.text((margin_x, cursor_y), line, font=body_font, fill="black")
        cursor_y += int(55 * SCALE)

    img_byte_arr = io.BytesIO()
    img.save(img_byte_arr, format='PNG')
    img_byte_arr.seek(0)
    return img_byte_arr

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            source = fetch_source_data()
            final_data = get_groq_enrichment(source)
            image_bytes = create_vocab_card_bytes(final_data)
            self.send_response(200)
            self.send_header('Content-type', 'image/png')
            self.end_headers()
            self.wfile.write(image_bytes.getvalue())
        except Exception as e:
            self.send_response(500)
            self.wfile.write(f"Error: {str(e)}".encode())