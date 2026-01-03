from http.server import BaseHTTPRequestHandler
import json
import os
import requests
from PIL import Image, ImageDraw, ImageFont
import textwrap
import io

# --- CONFIGURATION ---
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

# --- DEBUG & FONT LOADER ---
def get_font(font_name, size):
    # 1. Look in the "fonts" folder relative to this script
    base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    font_path = os.path.join(base_path, 'fonts', font_name)
    
    if os.path.exists(font_path):
        return ImageFont.truetype(font_path, size)
    
    # 2. If not found, log it and return Default
    print(f"WARNING: Font not found at {font_path}. Using Default.")
    try:
        # Debug: Print what IS in the root folder so we can fix it later
        print(f"Root contents: {os.listdir(base_path)}")
        if os.path.exists(os.path.join(base_path, 'fonts')):
             print(f"Fonts folder contents: {os.listdir(os.path.join(base_path, 'fonts'))}")
    except:
        pass
    return ImageFont.load_default()

# --- FETCH DATA ---
def fetch_source_data():
    url = "https://vocabdaily.vercel.app/get"
    try:
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        return response.json()['data']
    except Exception as e:
        print(f"Fetch Error: {e}")
        return None

# --- ENRICH DATA (Groq) ---
def get_groq_enrichment(source_data):
    if not source_data: return None
    
    # Fallback if no API key
    if not GROQ_API_KEY:
        print("No Groq API Key found. Using raw data.")
        return {
            "term": source_data.get('term', 'Error'),
            "pos": "noun",
            "meaning": source_data.get('meaning', 'No definition available.'),
            "derivatives": [],
            "synonyms": source_data.get('synonyms', [])[:4],
            "examples": [source_data.get('example', 'No example provided.')]
        }

    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    
    prompt = f"""
    Analyze "{source_data['term']}". 
    Return JSON: {{
        "term": "{source_data['term']}",
        "pos": "part of speech", 
        "meaning": "Short definition (max 15 words).",
        "derivatives": [{{"word": "derived1", "pos": "adj"}}],
        "synonyms": ["syn1", "syn2", "syn3"], 
        "examples": ["Short example sentence."]
    }}
    """

    try:
        payload = {
            "model": "llama-3.1-8b-instant",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.3
        }
        response = requests.post(url, headers=headers, data=json.dumps(payload), timeout=10)
        content = response.json()['choices'][0]['message']['content']
        clean_content = content.replace('```json', '').replace('```', '').strip()
        return json.loads(clean_content)
    except Exception as e:
        print(f"Groq Error: {e}")
        # Return fallback data
        return {
            "term": source_data.get('term'),
            "pos": "word",
            "meaning": source_data.get('meaning'),
            "derivatives": [],
            "synonyms": [],
            "examples": ["AI enrichment failed."]
        }

# --- GENERATE IMAGE ---
def create_vocab_card_bytes(data):
    # USE SCALE 2 TO SAVE MEMORY
    SCALE = 2 
    W, H = 1200 * SCALE, 1400 * SCALE
    
    img = Image.new("RGB", (W, H), color="#FFFFFF")
    draw = ImageDraw.Draw(img)
    
    # Load Fonts
    title_font = get_font("arialbd.ttf", int(125 * SCALE))
    body_font = get_font("arial.ttf", int(48 * SCALE))
    pos_font = get_font("ariali.ttf", int(57 * SCALE))
    
    # Check if we are using the broken default font
    is_default = "arial" not in str(title_font).lower() and "FreeType" not in str(title_font)

    if is_default:
        # --- SAFE MODE (Prevents 500 Crash) ---
        # Default fonts cannot use advanced sizing like textbbox
        print("Using Safe/Simple Drawing Mode")
        draw.text((50, 50), f"WORD: {data.get('term', '')}", font=title_font, fill="black")
        draw.text((50, 150), f"POS: {data.get('pos', '')}", font=title_font, fill="black")
        draw.text((50, 300), f"MEANING: {data.get('meaning', '')}", font=title_font, fill="black")
        draw.text((50, 500), "Note: Fonts not found on server.", font=title_font, fill="red")
        
    else:
        # --- FANCY MODE (Your Original Design) ---
        margin_x = int(80 * SCALE)
        cursor_y = int(50 * SCALE)

        # 1. Header
        term_text = data.get('term', 'Error').capitalize()
        draw.text((margin_x, cursor_y), term_text, font=title_font, fill="black")
        
        # Calculate width for POS
        bbox = draw.textbbox((0,0), term_text, font=title_font)
        title_w = bbox[2] - bbox[0]
        title_h = bbox[3] - bbox[1]
        
        draw.text((margin_x + title_w + int(30*SCALE), cursor_y + int(60*SCALE)), 
                 data.get('pos', ''), font=pos_font, fill="gray")
        
        cursor_y += title_h + int(40 * SCALE)

        # 2. Meaning
        meaning_text = data.get('meaning', '')
        wrapped_meaning = textwrap.wrap(meaning_text, width=50)
        for line in wrapped_meaning:
            draw.text((margin_x, cursor_y), line, font=body_font, fill="black")
            cursor_y += int(55 * SCALE)
            
        # (Add other sections like synonyms here if desired, following the same pattern)

    # Output to Bytes
    img_byte_arr = io.BytesIO()
    img.save(img_byte_arr, format='PNG')
    img_byte_arr.seek(0)
    return img_byte_arr

# --- VERCEL HANDLER ---
class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            # 1. Pipeline
            source = fetch_source_data()
            if not source: raise Exception("Source API failed")
            
            final_data = get_groq_enrichment(source)
            image_bytes = create_vocab_card_bytes(final_data)
            
            # 2. Respond
            self.send_response(200)
            self.send_header('Content-type', 'image/png')
            self.end_headers()
            self.wfile.write(image_bytes.getvalue())
            
        except Exception as e:
            # 3. Crash Handler
            print(f"CRITICAL ERROR: {e}")
            self.send_response(500)
            self.wfile.write(f"Server Error: {str(e)}".encode())