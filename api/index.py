import os
import requests
import json
from PIL import Image, ImageDraw, ImageFont
import textwrap
import math
from http.server import BaseHTTPRequestHandler
import io
# --- 1. CONFIGURATION ---
GROQ_API_KEY = os.environ.get("GROQ_API_KEY") 

def get_font(font_name, size):
    # This assumes api/index.py structure. We look one folder up for 'fonts'
    base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    font_path = os.path.join(base_path, 'fonts', font_name)
    
    try:
        return ImageFont.truetype(font_path, size)
    except Exception as e:
        # --- IF THIS RUNS, CHECK YOUR VERCEL LOGS ---
        print(f"CRITICAL ERROR: Could not load font at: {font_path}")
        print(f"Error details: {e}")
        
        # Print what actually exists so we aren't guessing
        print(f"--- DEBUGGING FILE SYSTEM ---")
        try:
            print(f"Current Directory (os.getcwd): {os.getcwd()}")
            print(f"Root Dir (base_path): {base_path}")
            print(f"Contents of Root: {os.listdir(base_path)}")
            if os.path.exists(os.path.join(base_path, 'fonts')):
                print(f"Contents of /fonts: {os.listdir(os.path.join(base_path, 'fonts'))}")
            else:
                print("ERROR: 'fonts' folder does NOT exist in root.")
        except Exception as debug_err:
            print(f"Debug crashed too: {debug_err}")
            
        return ImageFont.load_default()

# --- 2. FETCH DATA (Source API) ---
def fetch_source_data():
    url = "https://vocabdaily.vercel.app/get"
    try:
        print(f"Fetching random word from {url}...")
        response = requests.get(url)
        response.raise_for_status()
        full_response = response.json()
        return full_response['data'] 
    except Exception as e:
        print(f"Error fetching from Render API: {e}")
        return None

# --- 3. ENRICH DATA (Groq - Specific Structure) ---
def get_groq_enrichment(source_data):
    word = source_data['term']
    print(f"Enriching '{word}'...")
    
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    
    prompt_text = f"""
    Analyze the word "{word}". 
    Return ONLY a valid JSON object (no markdown) with this structure:
    {{
        "term": "{word}",
        "pos": "noun/verb", 
        "meaning": "A clear, concise definition (max 20 words).",
        "derivatives": [
            {{"word": "derivative1", "pos": "adj."}},
            {{"word": "derivative2", "pos": "adv."}},
            {{"word": "derivative3", "pos": "n."}}
        ],
        "synonyms": ["syn1", "syn2", "syn3", "syn4"], 
        "examples": ["Sentence 1", "Sentence 2"]
    }}
    Rules:
    1. 'pos': Short form of main word's part of speech (e.g., 'noun', 'adj.').
    2. 'derivatives': List 3 related forms with their shorthand POS (e.g. 'controversial', 'adj.').
    3. 'synonyms': Exactly 4 distinct synonyms.
    4. 'examples': 2 sentences. Max 15 words each.
    """

    payload = {
        "model": "llama-3.1-8b-instant",
        "messages": [{"role": "user", "content": prompt_text}],
        "temperature": 0.3
    }

    try:
        response = requests.post(url, headers=headers, data=json.dumps(payload))
        response.raise_for_status()
        content = response.json()['choices'][0]['message']['content']
        data = json.loads(content.replace('```json', '').replace('```', '').strip())
        return data

    except Exception as e:
        print(f"Groq API Error: {e}")
        return {
            "term": source_data['term'],
            "pos": "word",
            "meaning": source_data['meaning'],
            "derivatives": [],
            "synonyms": source_data.get('synonyms', [])[:4],
            "examples": [source_data.get('example', "")]
        }

# --- 4. GENERATE IMAGE ---
def create_vocab_card_bytes(data, output_filename="vocab_card_modified.png"):
    # CONFIG: Vertical Layout
    SCALE = 0.5
    Base_W, Base_H = 1200, 1400
    W, H = Base_W * SCALE, Base_H * SCALE
    
    # COLORS
    bg_color = "#FFFFFF"
    text_main = "#000000"
    text_gray = "#808080"
    bullet_blue = "#007BFF"
    box_fill = "#F0F0F0"
    separator_color = "#E0E0E0"

    img = Image.new("RGB", (W, H), color=bg_color)
    draw = ImageDraw.Draw(img)

    def s(pixels): return int(pixels * SCALE)

    # FONTS
    try:
        title_font = get_font("Roboto-Bold.ttf", s(125))
        pos_font = get_font("Roboto-Italic.ttf", s(57))
        little_pos_font = get_font("Roboto-Italic.ttf", s(45))
        body_font = get_font("Roboto-Regular.ttf", s(48))
        bold_body_font = get_font("Roboto-Bold.ttf", s(48))
        header_font = get_font("Roboto-Bold.ttf", s(42))
        small_font = get_font("Roboto-Regular.ttf", s(35))
        
        # New Bold CTA Font
        cta_font = ImageFont.truetype("arial.ttf", s(37))
    except IOError:
        print("Warning: Arial fonts not found. Using default.")
        title_font = pos_font = body_font = bold_body_font = header_font = small_font = cta_font = ImageFont.load_default()

    margin_x = s(80)
    
    # FIXED: Reduced top margin to move word up
    cursor_y = s(50) 

    # POSITIONS
    FOOTER_FROM_BOTTOM = s(60)
    footer_y = H - FOOTER_FROM_BOTTOM

    # 1. HEADER: Title + POS (Inline Layout)
    term_text = data['term'].capitalize()
    
    # Draw Word
    draw.text((margin_x, cursor_y), term_text, font=title_font, fill=text_main)
    
    # Calculate word dimensions to place POS next to it
    bbox = draw.textbbox((0,0), term_text, font=title_font)
    title_w = bbox[2] - bbox[0]
    title_h = bbox[3] - bbox[1]
    
    # POS Position
    # x: End of word + spacing
    pos_x = margin_x + title_w + s(30)
    
    # y: Align baselines.
    pos_y_offset = s(60) 
    
    draw.text((pos_x, cursor_y + pos_y_offset), data['pos'], font=pos_font, fill=text_gray)
    
    # Move cursor down for next section (Meaning)
    cursor_y += title_h + s(40) 

    # 2. DEFINITION
    wrapped_meaning = textwrap.wrap(data['meaning'], width=50) 
    for line in wrapped_meaning:
        draw.text((margin_x, cursor_y), line, font=body_font, fill=text_main)
        cursor_y += s(55)
    
    cursor_y += s(40)

    # 3. SEPARATOR LINE 1
    draw.line([(margin_x, cursor_y), (W - margin_x, cursor_y)], fill=separator_color, width=s(3))
    cursor_y += s(50)

    # 4. COLUMNS: Derivatives & Synonyms
    col1_x = margin_x
    col2_x = W // 2 + s(40)
    
    # Left Column: Derivatives
    draw.text((col1_x, cursor_y), "DERIVATIVES", font=header_font, fill=text_main)
    deriv_cursor_y = cursor_y + s(60)
    
    for item in data['derivatives']:
        word_text = item['word']
        pos_text = item['pos']
        
        draw.text((col1_x, deriv_cursor_y), word_text, font=body_font, fill=text_main)
        
        w_bbox = draw.textbbox((0,0), word_text, font=body_font)
        w_width = w_bbox[2] - w_bbox[0]
        draw.text((col1_x + w_width + s(15), deriv_cursor_y), pos_text, font=little_pos_font, fill=text_gray)
        
        deriv_cursor_y += s(55)

    # Right Column: Synonyms
    draw.text((col2_x, cursor_y), "SYNONYMS", font=header_font, fill=text_main)
    syn_cursor_y = cursor_y + s(60)
    
    for syn in data['synonyms']:
        draw.text((col2_x, syn_cursor_y), "•", font=bold_body_font, fill=bullet_blue)
        draw.text((col2_x + s(30), syn_cursor_y), syn, font=body_font, fill=text_main)
        syn_cursor_y += s(55)

    cursor_y = max(deriv_cursor_y, syn_cursor_y) + s(40)

    # 5. SEPARATOR LINE 2
    draw.line([(margin_x, cursor_y), (W - margin_x, cursor_y)], fill=separator_color, width=s(3))
    cursor_y += s(60)

    # --- CALCULATE CTA POSITION FIRST (To constrain Usage Box) ---
    cta_text = "Challenge: Write a sentence using one of the derivatives in the comments!"
    
    # 1. Wrap CTA Text (Dynamic)
    max_cta_width = W - (2 * margin_x)
    cta_lines = []
    words = cta_text.split()
    current_line = []
    
    for word in words:
        # Check width with next word
        test_line = ' '.join(current_line + [word])
        bbox = draw.textbbox((0, 0), test_line, font=cta_font)
        if (bbox[2] - bbox[0]) <= max_cta_width:
            current_line.append(word)
        else:
            cta_lines.append(' '.join(current_line))
            current_line = [word]
    if current_line:
        cta_lines.append(' '.join(current_line))
    
    # 2. Calculate CTA Block Height
    line_bbox = draw.textbbox((0, 0), "Aj", font=cta_font)
    line_height = line_bbox[3] - line_bbox[1] + s(15) 
    cta_block_height = len(cta_lines) * line_height
    
    # 3. Determine CTA Start Y
    # Position it above the Footer with some gap (e.g., s(60))
    cta_start_y = footer_y - cta_block_height - s(80)

    # 6. USAGE BOX
    box_top = cursor_y
    # Available height is distance from cursor to CTA top, minus gap
    available_height = cta_start_y - box_top - s(60)
    
    content_height = s(60)
    text_start_x = margin_x + s(70)
    usable_width = W - text_start_x - margin_x - s(40)
    
    target_word = data['term'].lower()
    
    # Calculate content height
    for sentence in data['examples']:
        words = sentence.split()
        curr_line_width = 0
        lines = 1
        for word in words:
            clean_word = "".join(char for char in word if char.isalnum()).lower()
            is_target = target_word in clean_word
            fnt = bold_body_font if is_target else body_font
            word_bbox = draw.textbbox((0,0), word + " ", font=fnt)
            word_w = word_bbox[2] - word_bbox[0]
            if curr_line_width + word_w > usable_width:
                lines += 1
                curr_line_width = word_w
            else:
                curr_line_width += word_w
        content_height += (lines * s(55)) + s(40)
    
    content_height += s(30)
    box_height = min(content_height, available_height)
    
    # Prevent negative height if content is too long
    if box_height < s(100): box_height = s(100)

    draw.rounded_rectangle(
        [margin_x, box_top, W - margin_x, box_top + box_height],
        radius=s(30),
        fill=box_fill
    )

    # Usage Examples Content
    content_y = box_top + s(30)
    draw.text((margin_x + s(30), content_y), "USAGE EXAMPLES", font=header_font, fill=text_main)
    content_y += s(60)

    for sentence in data['examples']:
        # Basic bounds check to stop drawing if we run out of box
        if content_y > box_top + box_height - s(50): break
        
        bullet_x = margin_x + s(30)
        draw.text((bullet_x, content_y), "•", font=bold_body_font, fill=bullet_blue)
        
        text_x = bullet_x + s(40)
        curr_line_x = text_x
        curr_line_y = content_y
        
        words = sentence.split()
        max_width = W - margin_x - s(40)
        
        for word in words:
            clean_word = "".join(char for char in word if char.isalnum()).lower()
            is_target = target_word in clean_word
            fnt = bold_body_font if is_target else body_font
            
            word_bbox = draw.textbbox((0,0), word + " ", font=fnt)
            word_w = word_bbox[2] - word_bbox[0]
            
            if curr_line_x + word_w > max_width:
                curr_line_x = text_x
                curr_line_y += s(55)
            
            # Check vertical overflow
            if curr_line_y > box_top + box_height - s(50): break

            draw.text((curr_line_x, curr_line_y), word, font=fnt, fill=text_main)
            curr_line_x += word_w
            
        content_y = curr_line_y + s(75)

    # 7. DRAW CTA (Left Aligned at Margin)
    curr_cta_y = cta_start_y
    for line in cta_lines:
        draw.text((margin_x, curr_cta_y), line, font=cta_font, fill=text_main)
        curr_cta_y += line_height

    # 8. FOOTER - UPDATED TEXT
    footer_text = "r/Vocabdaily"
    
    # Calculate footer layout
    footer_bbox = draw.textbbox((0,0), footer_text, font=small_font)
    footer_text_w = footer_bbox[2] - footer_bbox[0]
    
    icon_h = s(45) 
    gap = s(15)
    
    # Draw Logo (Image)
    try:
        logo_path = "reddit_logo.png" 
        logo_img = Image.open(logo_path).convert("RGBA")
        
        # Calculate aspect ratio to fix squishing
        aspect = logo_img.width / logo_img.height
        icon_w = int(icon_h * aspect)
        
        logo_img = logo_img.resize((icon_w, icon_h), Image.Resampling.LANCZOS)
        
        total_footer_w = icon_w + gap + footer_text_w
        
        # Position: Right-aligned with some margin
        block_end_x = W - s(80) 
        block_start_x = block_end_x - total_footer_w
        
        # Paste the logo
        img.paste(logo_img, (int(block_start_x), int(footer_y - s(5))), logo_img)
        
        # Draw Text relative to the calculated icon width
        draw.text((block_start_x + icon_w + gap, footer_y), footer_text, font=small_font, fill=text_gray)
        
    except Exception as e:
        print(f"Warning: Could not load 'reddit_logo.png'. Using fallback shape. Error: {e}")
        # Fallback
        icon_w = s(45)
        total_footer_w = icon_w + gap + footer_text_w
        block_end_x = W - s(80) 
        block_start_x = block_end_x - total_footer_w
        
        draw.ellipse([block_start_x, footer_y - s(5), block_start_x + icon_w, footer_y - s(5) + icon_h], fill="#FF4500")
        draw.text((block_start_x + icon_w + gap, footer_y), footer_text, font=small_font, fill=text_gray)
        # OUTPUT TO BYTES
    img_byte_arr = io.BytesIO()
    img.save(img_byte_arr, format='PNG')
    img_byte_arr.seek(0)
    return img_byte_arr

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            # 1. Generate Data
            source = fetch_source_data()
            final_data = get_groq_enrichment(source)
            
            # 2. Generate Image
            image_bytes = create_vocab_card_bytes(final_data)
            
            # 3. Serve Image directly to the browser/bot
            self.send_response(200)
            self.send_header('Content-type', 'image/png')
            self.end_headers()
            self.wfile.write(image_bytes.getvalue())
            
        except Exception as e:
            self.send_response(500)
            self.wfile.write(str(e).encode())
