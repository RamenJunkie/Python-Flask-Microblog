#!/usr/bin/env python3
"""
Flask-based Microblog with Bluesky & Mastodon Auto-Posting

A web interface for managing and posting to social media with:
- Blog-like archive of posts with pagination and search
- Post creation with optional images, links, and commentary
- Automatic posting to Bluesky and Mastodon
- Scheduled hourly posting from queue
"""

import os
import sys
import requests
import threading
import time
import sqlite3
import feedparser
from datetime import datetime
from urllib.parse import urljoin, urlparse
from io import BytesIO
from PIL import Image
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps

from atproto import Client, models
from mastodon import Mastodon
from bs4 import BeautifulSoup

# Configuration
TOPOST_FILE = 'topost.txt'
POSTED_FILE = 'posted.txt'
IMAGES_FOLDER = 'images'
UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
DATABASE = 'microblog.db'

USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'

# Flask app setup
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'change-this-secret-key-in-production')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Ensure directories exist
os.makedirs(IMAGES_FOLDER, exist_ok=True)
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Database functions
def init_db():
    """Initialize the database with required tables"""
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    
    # Settings table
    c.execute('''CREATE TABLE IF NOT EXISTS settings
                 (key TEXT PRIMARY KEY, value TEXT)''')
    
    # Users table
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  username TEXT UNIQUE NOT NULL,
                  password_hash TEXT NOT NULL,
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    
    # RSS feeds table
    c.execute('''CREATE TABLE IF NOT EXISTS rss_feeds
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  url TEXT UNIQUE NOT NULL,
                  name TEXT,
                  added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    
    conn.commit()
    conn.close()

def get_setting(key, default=None):
    """Get a setting from the database"""
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('SELECT value FROM settings WHERE key = ?', (key,))
    result = c.fetchone()
    conn.close()
    return result[0] if result else default

def set_setting(key, value):
    """Set a setting in the database"""
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)', (key, value))
    conn.commit()
    conn.close()

def get_user(username):
    """Get a user from the database"""
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('SELECT id, username, password_hash FROM users WHERE username = ?', (username,))
    result = c.fetchone()
    conn.close()
    return {'id': result[0], 'username': result[1], 'password_hash': result[2]} if result else None

def create_user(username, password):
    """Create a new user"""
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    password_hash = generate_password_hash(password)
    try:
        c.execute('INSERT INTO users (username, password_hash) VALUES (?, ?)', (username, password_hash))
        conn.commit()
        conn.close()
        return True
    except sqlite3.IntegrityError:
        conn.close()
        return False

def user_exists():
    """Check if any user exists in the database"""
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('SELECT COUNT(*) FROM users')
    count = c.fetchone()[0]
    conn.close()
    return count > 0

# RSS feed functions
def add_rss_feed(url, name=None):
    """Add an RSS feed to the database"""
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    try:
        c.execute('INSERT INTO rss_feeds (url, name) VALUES (?, ?)', (url, name))
        conn.commit()
        conn.close()
        return True
    except sqlite3.IntegrityError:
        conn.close()
        return False

def get_rss_feeds():
    """Get all RSS feeds from the database"""
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('SELECT id, url, name FROM rss_feeds ORDER BY added_at DESC')
    feeds = [{'id': row[0], 'url': row[1], 'name': row[2]} for row in c.fetchall()]
    conn.close()
    return feeds

def delete_rss_feed(feed_id):
    """Delete an RSS feed from the database"""
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('DELETE FROM rss_feeds WHERE id = ?', (feed_id,))
    conn.commit()
    conn.close()

def fetch_rss_entries(feed_url, limit=15):
    """Fetch recent entries from an RSS feed"""
    try:
        feed = feedparser.parse(feed_url)
        
        if feed.bozo and not feed.entries:
            return None, "Failed to parse RSS feed"
        
        entries = []
        for entry in feed.entries[:limit]:
            entries.append({
                'title': entry.get('title', 'No title'),
                'link': entry.get('link', ''),
                'published': entry.get('published', ''),
                'summary': entry.get('summary', ''),
                'author': entry.get('author', '')
            })
        
        return entries, None
    except Exception as e:
        return None, str(e)

# Login decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page.', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# Initialize database on startup
init_db()

# Add custom Jinja2 filter for parsing content
@app.template_filter('parse_content')
def parse_content_filter(content):
    return parse_content(content)

# Context processor to make site settings available to all templates
@app.context_processor
def inject_site_settings():
    """Make site_name and social_links available to all templates"""
    return {
        'site_name': get_setting('site_name', 'Microblog'),
        'social_links': get_setting('social_links', '')
    }

# Global variable to track last auto-post time
last_auto_post_time = time.time()

# Utility functions
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def parse_posted_line(line):
    """Parse a line from posted.txt - new pipe-delimited format only"""
    if not line.strip():
        return None
    
    # New format: [DATETIME]|url|headline|imageFilename|summary|commentary
    if not line.startswith('['):
        return None
    
    bracket_end = line.find(']')
    if bracket_end == -1:
        return None
    
    timestamp_str = line[1:bracket_end]
    try:
        timestamp = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
    except:
        return None
    
    # Check for pipe-delimited format
    rest = line[bracket_end+1:].strip()
    if not rest.startswith('|'):
        return None
    
    rest = rest[1:]  # Remove leading pipe
    parts = rest.split('|')
    
    if len(parts) < 5:
        return None
    
    return {
        'timestamp': timestamp,
        'url': parts[0].strip() if parts[0].strip() and parts[0].strip() != 'NULL' else None,
        'headline': parts[1].strip() if parts[1].strip() and parts[1].strip() != 'NULL' else None,
        'image': parts[2].strip() if parts[2].strip() and parts[2].strip() != 'NULL' else None,
        'summary': parts[3].strip() if parts[3].strip() and parts[3].strip() != 'NULL' else None,
        'commentary': parts[4].strip() if parts[4].strip() and parts[4].strip() != 'NULL' else None,
        'raw': line
    }

def parse_content(content):
    """Parse content to extract URL, image, and text"""
    if '|' not in content:
        return {'type': 'text', 'text': content}
    
    parts = content.split('|', 1)
    first_part = parts[0].strip()
    second_part = parts[1].strip()
    
    # Check if URL
    if first_part.startswith(('http://', 'https://', 'www.')):
        return {'type': 'url', 'url': first_part, 'text': second_part}
    
    # Check if image
    image_extensions = ('.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.tiff')
    if any(first_part.lower().endswith(ext) for ext in image_extensions):
        return {'type': 'image', 'image': first_part, 'text': second_part}
    
    return {'type': 'text', 'text': content}

def get_posted_entries(page=1, per_page=20, search_query=None):
    """Get paginated posted entries with optional search"""
    try:
        with open(POSTED_FILE, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        # Parse all lines
        entries = []
        for line in reversed(lines):
            if line.strip():
                parsed = parse_posted_line(line)
                if parsed:  # Only add if parsing succeeded
                    entries.append(parsed)
        
        # Filter by search query if provided
        if search_query:
            filtered = []
            for e in entries:
                search_text = ' '.join(filter(None, [
                    e.get('headline', ''),
                    e.get('summary', ''),
                    e.get('commentary', ''),
                    e.get('content', '')
                ])).lower()
                if search_query.lower() in search_text:
                    filtered.append(e)
            entries = filtered
        
        # Paginate
        total = len(entries)
        start = (page - 1) * per_page
        end = start + per_page
        
        return {
            'entries': entries[start:end],
            'total': total,
            'page': page,
            'per_page': per_page,
            'total_pages': (total + per_page - 1) // per_page if total > 0 else 0
        }
    except FileNotFoundError:
        return {'entries': [], 'total': 0, 'page': 1, 'per_page': per_page, 'total_pages': 0}

def get_all_posted_entries():
    """Get all posted entries without pagination"""
    try:
        with open(POSTED_FILE, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        # Parse all lines (reversed so newest first)
        entries = []
        for line in reversed(lines):
            if line.strip():
                parsed = parse_posted_line(line)
                if parsed:  # Only add if parsing succeeded
                    entries.append(parsed)
        return entries
    except FileNotFoundError:
        return []

def get_queue_entries():
    """Get entries waiting in topost.txt"""
    try:
        with open(TOPOST_FILE, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        return [line.strip() for line in lines if line.strip()]
    except FileNotFoundError:
        return []

# Social media posting functions (from original script)
def fetch_page_metadata(url):
    """Fetch page title, description, and featured image from URL"""
    try:
        headers = {'User-Agent': USER_AGENT}
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        title = None
        title_tag = soup.find('title')
        if title_tag:
            title = title_tag.get_text().strip()
        
        og_title = soup.find('meta', property='og:title')
        if og_title and og_title.get('content'):
            title = og_title.get('content').strip()
        
        description = None
        og_desc = soup.find('meta', property='og:description')
        if og_desc and og_desc.get('content'):
            description = og_desc.get('content').strip()
        else:
            meta_desc = soup.find('meta', attrs={'name': 'description'})
            if meta_desc and meta_desc.get('content'):
                description = meta_desc.get('content').strip()
        
        image_url = None
        og_image = soup.find('meta', property='og:image')
        if og_image and og_image.get('content'):
            image_url = og_image.get('content').strip()
            image_url = urljoin(url, image_url)
        
        if not image_url:
            twitter_image = soup.find('meta', attrs={'name': 'twitter:image'})
            if twitter_image and twitter_image.get('content'):
                image_url = twitter_image.get('content').strip()
                image_url = urljoin(url, image_url)
        
        return {
            'title': title or url,
            'description': description or '',
            'image_url': image_url
        }
    except Exception as e:
        print(f"Error fetching metadata for {url}: {e}")
        return {
            'title': url,
            'description': '',
            'image_url': None
        }

def load_local_image(filename):
    """Load and process a local image file"""
    try:
        image_path = os.path.join(IMAGES_FOLDER, filename)
        
        if not os.path.exists(image_path):
            print(f"Error: Image file not found: {image_path}")
            return None
        
        with open(image_path, 'rb') as f:
            image_data = f.read()
        
        img = Image.open(BytesIO(image_data))
        
        if img.mode in ('RGBA', 'LA', 'P'):
            img = img.convert('RGB')
        
        max_size = (1200, 1200)
        if img.size[0] > max_size[0] or img.size[1] > max_size[1]:
            img.thumbnail(max_size, Image.Resampling.LANCZOS)
        
        img_bytes = BytesIO()
        img.save(img_bytes, format='JPEG', quality=85)
        img_bytes.seek(0)
        
        return img_bytes.getvalue()
    except Exception as e:
        print(f"Error loading local image {filename}: {e}")
        return None

def download_and_process_image(image_url):
    """Download and process image"""
    try:
        headers = {'User-Agent': USER_AGENT}
        response = requests.get(image_url, headers=headers, timeout=15)
        response.raise_for_status()
        
        img = Image.open(BytesIO(response.content))
        
        if img.mode in ('RGBA', 'LA', 'P'):
            img = img.convert('RGB')
        
        max_size = (1200, 1200)
        if img.size[0] > max_size[0] or img.size[1] > max_size[1]:
            img.thumbnail(max_size, Image.Resampling.LANCZOS)
        
        img_bytes = BytesIO()
        img.save(img_bytes, format='JPEG', quality=85)
        img_bytes.seek(0)
        
        return img_bytes.getvalue()
    except Exception as e:
        print(f"Error processing image {image_url}: {e}")
        return None

def upload_image_to_bluesky(client, image_data):
    """Upload image to Bluesky"""
    try:
        blob = client.upload_blob(image_data)
        return blob
    except Exception as e:
        print(f"Error uploading image to Bluesky: {e}")
        return None

def create_bluesky_image_post(client, image_data, caption):
    """Create a Bluesky post with an image"""
    try:
        print("Uploading image to Bluesky...")
        blob = upload_image_to_bluesky(client, image_data)
        
        if not blob:
            print("Failed to upload image to Bluesky")
            return None
        
        image_embed = models.AppBskyEmbedImages.Image(
            alt="",
            image=blob.blob
        )
        
        embed = models.AppBskyEmbedImages.Main(images=[image_embed])
        
        response = client.send_post(text=caption, embed=embed)
        print("✓ Image uploaded to Bluesky successfully")
        return response
    
    except Exception as e:
        print(f"Error creating Bluesky image post: {e}")
        return None

def create_simple_bluesky_post(client, text):
    """Create a simple text-only Bluesky post"""
    try:
        response = client.send_post(text=text)
        return response
    except Exception as e:
        print(f"Error creating simple Bluesky post: {e}")
        return None

def create_mastodon_image_post(mastodon_client, image_data, caption):
    """Create a Mastodon post with an image"""
    try:
        print("Uploading image to Mastodon...")
        media_dict = mastodon_client.media_post(image_data, mime_type='image/jpeg')
        media_id = media_dict['id']
        
        response = mastodon_client.status_post(caption, media_ids=[media_id])
        print("✓ Image uploaded to Mastodon successfully")
        return response
    
    except Exception as e:
        print(f"Error creating Mastodon image post: {e}")
        return None

def create_bluesky_post_with_embed(client, url, comment, metadata):
    """Create a Bluesky post with embedded link card"""
    try:
        external_embed = models.AppBskyEmbedExternal.External(
            uri=url,
            title=metadata['title'][:300],
            description=metadata['description'][:1000] if metadata['description'] else ''
        )
        
        if metadata['image_url']:
            print(f"Downloading featured image: {metadata['image_url']}")
            image_data = download_and_process_image(metadata['image_url'])
            
            if image_data:
                print("Uploading image to Bluesky...")
                blob = upload_image_to_bluesky(client, image_data)
                if blob:
                    external_embed.thumb = blob.blob
                    print("✓ Image uploaded successfully")
                else:
                    print("⚠️  Failed to upload image, posting without it")
            else:
                print("⚠️  Failed to download image, posting without it")
        
        embed = models.AppBskyEmbedExternal.Main(external=external_embed)
        
        response = client.send_post(text=comment, embed=embed)
        return response
    
    except Exception as e:
        print(f"Error creating post with embed: {e}")
        return None

def create_mastodon_post(mastodon_client, text, url=None, image_data=None):
    """Create a Mastodon post with optional image and URL"""
    try:
        media_id = None
        
        if image_data:
            print("Uploading image to Mastodon...")
            media_dict = mastodon_client.media_post(image_data, mime_type='image/jpeg')
            media_id = media_dict['id']
            print("✓ Image uploaded to Mastodon successfully")
        
        if url:
            post_text = f"{text}\n\n{url}"
        else:
            post_text = text
        
        if media_id:
            response = mastodon_client.status_post(post_text, media_ids=[media_id])
        else:
            response = mastodon_client.status_post(post_text)
        
        return response
    
    except Exception as e:
        print(f"Error creating Mastodon post: {e}")
        return None

def create_simple_mastodon_post(mastodon_client, text):
    """Create a simple text-only Mastodon post"""
    try:
        response = mastodon_client.status_post(text)
        return response
    except Exception as e:
        print(f"Error creating simple Mastodon post: {e}")
        return None

def post_to_social_media(content):
    """Post content to Bluesky and Mastodon"""
    try:
        # Get credentials from database
        bluesky_handle = get_setting('bluesky_handle')
        bluesky_password = get_setting('bluesky_password')
        mastodon_url = get_setting('mastodon_url')
        mastodon_token = get_setting('mastodon_token')
        
        if not all([bluesky_handle, bluesky_password, mastodon_url, mastodon_token]):
            print("Error: Social media credentials not configured")
            return False
        
        parsed = parse_content(content)
        
        bluesky_client = Client()
        bluesky_client.login(bluesky_handle, bluesky_password)
        
        mastodon_client = Mastodon(
            access_token=mastodon_token,
            api_base_url=mastodon_url
        )
        
        image_data = None
        metadata = None
        
        if parsed['type'] == 'url':
            url = parsed['url']
            text_content = parsed['text']
            metadata = fetch_page_metadata(url)
            
            # Download image for thumbnail
            if metadata['image_url']:
                image_data = download_and_process_image(metadata['image_url'])
            
            # Post to Bluesky with embed
            external_embed = models.AppBskyEmbedExternal.External(
                uri=url,
                title=metadata['title'][:300],
                description=metadata['description'][:1000] if metadata['description'] else ''
            )
            
            # Add thumbnail if available
            if image_data:
                blob = upload_image_to_bluesky(bluesky_client, image_data)
                if blob:
                    external_embed.thumb = blob.blob
            
            embed = models.AppBskyEmbedExternal.Main(external=external_embed)
            bluesky_client.send_post(text=text_content, embed=embed)
            
            # Post to Mastodon
            post_text = f"{text_content}\n\n{url}"
            if image_data:
                media_dict = mastodon_client.media_post(image_data, mime_type='image/jpeg')
                mastodon_client.status_post(post_text, media_ids=[media_dict['id']])
            else:
                mastodon_client.status_post(post_text)
        
        elif parsed['type'] == 'image':
            image_filename = parsed['image']
            text_content = parsed['text']
            image_data = load_local_image(image_filename)
            
            if image_data:
                # Post to Bluesky
                blob = upload_image_to_bluesky(bluesky_client, image_data)
                if blob:
                    image_embed = models.AppBskyEmbedImages.Image(alt="", image=blob.blob)
                    embed = models.AppBskyEmbedImages.Main(images=[image_embed])
                    bluesky_client.send_post(text=text_content, embed=embed)
                
                # Post to Mastodon
                media_dict = mastodon_client.media_post(image_data, mime_type='image/jpeg')
                mastodon_client.status_post(text_content, media_ids=[media_dict['id']])
        
        else:
            # Text only
            text_content = parsed['text']
            bluesky_client.send_post(text=text_content)
            mastodon_client.status_post(text_content)
        
        return True
    
    except Exception as e:
        print(f"Error posting to social media: {e}")
        import traceback
        traceback.print_exc()
        return False

def add_to_posted(content):
    """Add entry to posted.txt with timestamp and metadata"""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    # Parse the content
    parsed = parse_content(content)
    
    # Initialize metadata fields
    url = 'NULL'
    headline = 'NULL'
    image_filename = 'NULL'
    summary = 'NULL'
    commentary = 'NULL'
    
    if parsed['type'] == 'url':
        url = parsed['url']
        commentary = parsed['text'].replace('|', '-') if parsed['text'] else 'NULL'
        
        # Fetch metadata
        try:
            metadata = fetch_page_metadata(url)
            headline = metadata.get('title', 'NULL').replace('|', '-')  # Remove pipes to avoid conflicts
            
            # Get description/summary
            description = metadata.get('description', '')
            if description:
                summary = description[:200].replace('|', '-')
                if len(description) > 200:
                    summary += '...'
            
            # Download and save image
            image_url = metadata.get('image_url')
            if image_url:
                try:
                    import hashlib
                    # Create unique filename from URL hash
                    url_hash = hashlib.md5(url.encode()).hexdigest()[:12]
                    image_filename_local = f"link_{url_hash}.jpg"
                    image_path = os.path.join(IMAGES_FOLDER, image_filename_local)
                    
                    # Download image
                    headers = {'User-Agent': USER_AGENT}
                    img_response = requests.get(image_url, headers=headers, timeout=10)
                    img_response.raise_for_status()
                    
                    # Process and crop image to 300x200
                    img = Image.open(BytesIO(img_response.content))
                    if img.mode in ('RGBA', 'LA', 'P'):
                        img = img.convert('RGB')
                    
                    # Calculate crop to 3:2 ratio (300x200)
                    target_ratio = 600 / 400  # 1.5
                    img_ratio = img.width / img.height
                    
                    if img_ratio > target_ratio:
                        # Image is wider, crop width
                        new_width = int(img.height * target_ratio)
                        left = (img.width - new_width) // 2
                        img = img.crop((left, 0, left + new_width, img.height))
                    else:
                        # Image is taller, crop height
                        new_height = int(img.width / target_ratio)
                        top = (img.height - new_height) // 2
                        img = img.crop((0, top, img.width, top + new_height))
                    
                    # Resize to exactly 300x200
                    img = img.resize((300, 200), Image.Resampling.LANCZOS)
                    
                    # Save
                    img.save(image_path, format='JPEG', quality=85)
                    image_filename = image_filename_local
                    print(f"✓ Saved link image: {image_filename}")
                except Exception as e:
                    print(f"Error downloading/processing link image: {e}")
        except Exception as e:
            print(f"Error fetching metadata: {e}")
    
    elif parsed['type'] == 'image':
        image_filename = parsed['image']
        commentary = parsed['text'].replace('|', '-') if parsed['text'] else 'NULL'
    
    else:
        # Text only
        commentary = parsed['text'].replace('|', '-') if parsed['text'] else 'NULL'
    
    # Build the pipe-delimited line
    # Format: [DATETIME]|url|headline|imageFilename|summary|commentary
    line = f"[{timestamp}]|{url}|{headline}|{image_filename}|{summary}|{commentary}\n"
    
    with open(POSTED_FILE, 'a', encoding='utf-8') as f:
        f.write(line)

# Scheduled posting thread
def auto_poster_thread():
    """Background thread that posts from queue hourly"""
    global last_auto_post_time
    
    while True:
        time.sleep(60)
        
        if time.time() - last_auto_post_time >= 3600:
            try:
                with open(TOPOST_FILE, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                
                if lines:
                    line_to_post = lines[0].strip()
                    
                    if not line_to_post:
                        remaining_lines = lines[1:]
                        with open(TOPOST_FILE, 'w', encoding='utf-8') as f:
                            f.writelines(remaining_lines)
                        continue
                    
                    remaining_lines = lines[1:]
                    
                    if post_to_social_media(line_to_post):
                        with open(TOPOST_FILE, 'w', encoding='utf-8') as f:
                            f.writelines(remaining_lines)
                        
                        add_to_posted(line_to_post)
                        print(f"Auto-posted: {line_to_post}")
                        last_auto_post_time = time.time()
                    else:
                        print(f"Failed to auto-post: {line_to_post}")
            
            except FileNotFoundError:
                pass
            except Exception as e:
                print(f"Error in auto-poster: {e}")

# Flask routes
@app.route('/setup', methods=['GET', 'POST'])
def setup():
    """Initial setup page for creating admin user - only available if no users exist"""
    if user_exists():
        flash('Setup already completed', 'error')
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        confirm_password = request.form.get('confirm_password', '').strip()
        
        if not username or not password:
            flash('Username and password are required', 'error')
            return render_template('setup.html')
        
        if password != confirm_password:
            flash('Passwords do not match', 'error')
            return render_template('setup.html')
        
        if len(password) < 8:
            flash('Password must be at least 8 characters', 'error')
            return render_template('setup.html')
        
        if create_user(username, password):
            flash('Admin account created successfully! Please log in.', 'success')
            return redirect(url_for('login'))
        else:
            flash('Failed to create user', 'error')
    
    return render_template('setup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Login page"""
    if not user_exists():
        return redirect(url_for('setup'))
    
    if 'user_id' in session:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        
        user = get_user(username)
        
        if user and check_password_hash(user['password_hash'], password):
            session['user_id'] = user['id']
            session['username'] = user['username']
            flash('Logged in successfully!', 'success')
            return redirect(url_for('index'))
        else:
            flash('Invalid username or password', 'error')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    """Logout current user"""
    session.clear()
    flash('Logged out successfully', 'success')
    return redirect(url_for('login'))

@app.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    """Settings page for API credentials and site configuration"""
    if request.method == 'POST':
        # API credentials
        set_setting('bluesky_handle', request.form.get('bluesky_handle', '').strip())
        set_setting('bluesky_password', request.form.get('bluesky_password', '').strip())
        set_setting('mastodon_url', request.form.get('mastodon_url', '').strip())
        set_setting('mastodon_token', request.form.get('mastodon_token', '').strip())
        
        # Site configuration
        site_name = request.form.get('site_name', '').strip()
        social_links = request.form.get('social_links', '').strip()
        
        set_setting('site_name', site_name if site_name else 'Microblog')
        set_setting('social_links', social_links)
        
        flash('Settings updated successfully!', 'success')
        return redirect(url_for('settings'))
    
    settings_data = {
        'bluesky_handle': get_setting('bluesky_handle', ''),
        'bluesky_password': get_setting('bluesky_password', ''),
        'mastodon_url': get_setting('mastodon_url', ''),
        'mastodon_token': get_setting('mastodon_token', ''),
        'site_name': get_setting('site_name', 'Microblog'),
        'social_links': get_setting('social_links', '')
    }
    
    return render_template('settings.html', settings=settings_data)

@app.route('/')
def index():
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '')
    
    result = get_posted_entries(page=page, per_page=20, search_query=search if search else None)
    queue = get_queue_entries()
    
    # Debug output
    print(f"DEBUG: Found {len(result['entries'])} entries for page {page}")
    if result['entries']:
        print(f"DEBUG: First entry: {result['entries'][0]}")
    
    if 'user_id' in session:
        return render_template('index.html', 
                             entries=result['entries'],
                             pagination=result,
                             search=search,
                             queue_count=len(queue))
    else:
        return render_template('index_public.html',
                             entries=result['entries'],
                             pagination=result,
                             search=search)

@app.route('/queue')
@login_required
def queue():
    queue_entries = get_queue_entries()
    return render_template('queue.html', queue=queue_entries)

@app.route('/post', methods=['POST'])
@login_required
def create_post():
    try:
        text = request.form.get('text', '').strip()
        url = request.form.get('url', '').strip()
        post_now = request.form.get('post_now') == 'on'
        local_only = request.form.get('local_only') == 'on'
        
        image_filename = None
        if 'image' in request.files:
            file = request.files['image']
            if file and file.filename and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                filename = f"{timestamp}_{filename}"
                filepath = os.path.join(IMAGES_FOLDER, filename)
                file.save(filepath)
                image_filename = filename
        
        if url and text:
            content = f"{url}|{text}"
        elif image_filename and text:
            content = f"{image_filename}|{text}"
        elif text:
            content = text
        else:
            flash('Post must contain at least some text', 'error')
            return redirect(url_for('index'))
        
        if local_only:
            add_to_posted(content)
            flash('Posted locally!', 'success')
        elif post_now:
            if post_to_social_media(content):
                add_to_posted(content)
                flash('Posted successfully!', 'success')
                global last_auto_post_time
                last_auto_post_time = time.time()
            else:
                flash('Failed to post to social media', 'error')
        else:
            with open(TOPOST_FILE, 'a', encoding='utf-8') as f:
                f.write(f"{content}\n")
            flash('Added to queue', 'success')
        
        return redirect(url_for('index'))
    
    except Exception as e:
        flash(f'Error creating post: {str(e)}', 'error')
        return redirect(url_for('index'))

@app.route('/delete_queue/<int:index>', methods=['POST'])
@login_required
def delete_queue_item(index):
    try:
        with open(TOPOST_FILE, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        if 0 <= index < len(lines):
            del lines[index]
            
            with open(TOPOST_FILE, 'w', encoding='utf-8') as f:
                f.writelines(lines)
            
            flash('Queue item deleted', 'success')
        else:
            flash('Invalid queue index', 'error')
    
    except Exception as e:
        flash(f'Error deleting queue item: {str(e)}', 'error')
    
    return redirect(url_for('queue'))

@app.route('/rss')
@login_required
def rss():
    """RSS feed management and browser page"""
    feeds = get_rss_feeds()
    return render_template('rss.html', feeds=feeds)

@app.route('/rss/add', methods=['POST'])
@login_required
def add_rss():
    """Add a new RSS feed"""
    url = request.form.get('url', '').strip()
    name = request.form.get('name', '').strip()
    
    if not url:
        flash('RSS feed URL is required', 'error')
        return redirect(url_for('rss'))
    
    entries, error = fetch_rss_entries(url, limit=1)
    if error:
        flash(f'Invalid RSS feed: {error}', 'error')
        return redirect(url_for('rss'))
    
    if add_rss_feed(url, name):
        flash('RSS feed added successfully!', 'success')
    else:
        flash('RSS feed already exists', 'error')
    
    return redirect(url_for('rss'))

@app.route('/rss/delete/<int:feed_id>', methods=['POST'])
@login_required
def delete_rss(feed_id):
    """Delete an RSS feed"""
    delete_rss_feed(feed_id)
    flash('RSS feed deleted', 'success')
    return redirect(url_for('rss'))

@app.route('/rss/browse/<int:feed_id>')
@login_required
def browse_rss(feed_id):
    """Browse entries from a specific RSS feed"""
    feeds = get_rss_feeds()
    feed = next((f for f in feeds if f['id'] == feed_id), None)
    
    if not feed:
        flash('RSS feed not found', 'error')
        return redirect(url_for('rss'))
    
    entries, error = fetch_rss_entries(feed['url'])
    
    if error:
        flash(f'Error fetching RSS feed: {error}', 'error')
        return redirect(url_for('rss'))
    
    return render_template('rss_browse.html', feed=feed, entries=entries)

@app.route('/rss/add_to_queue', methods=['POST'])
@login_required
def add_rss_to_queue():
    """Add an RSS entry to the posting queue"""
    link = request.form.get('link', '').strip()
    title = request.form.get('title', '').strip()
    commentary = request.form.get('commentary', '').strip()
    post_now = request.form.get('post_now') == 'on'
    local_only = request.form.get('local_only') == 'on'
    
    if not link:
        flash('Link is required', 'error')
        return redirect(request.referrer or url_for('rss'))
    
    if commentary:
        content = f"{link}|{commentary}"
    else:
        content = f"{link}|{title}"
    
    if local_only:
        add_to_posted(content)
        flash('Posted locally!', 'success')
    elif post_now:
        if post_to_social_media(content):
            add_to_posted(content)
            flash('Posted successfully!', 'success')
            global last_auto_post_time
            last_auto_post_time = time.time()
        else:
            flash('Failed to post to social media', 'error')
    else:
        with open(TOPOST_FILE, 'a', encoding='utf-8') as f:
            f.write(f"{content}\n")
        flash('Added to queue!', 'success')
    
    return redirect(request.referrer or url_for('rss'))

@app.route('/digest')
@login_required
def generate_digest():
    """Generate an HTML digest of posts since last digest"""
    from flask import make_response
    
    # Get last digest date
    last_digest_str = get_setting('last_digest_date')
    if last_digest_str:
        try:
            last_digest = datetime.strptime(last_digest_str, '%Y-%m-%d %H:%M:%S')
        except:
            last_digest = None
    else:
        last_digest = None
    
    # Get all entries
    all_entries = get_all_posted_entries()
    
    # Filter entries since last digest
    if last_digest:
        new_entries = [e for e in all_entries if e['timestamp'] and e['timestamp'] > last_digest]
    else:
        new_entries = all_entries
    
    if not new_entries:
        flash('No new posts since last digest', 'error')
        return redirect(url_for('index'))
    
    # Generate digest HTML
    site_name = get_setting('site_name', 'Microblog')
    today = datetime.now()
    digest_title = f"{site_name} Link List for {today.strftime('%A %Y-%m-%d')}"
    
    html_parts = [f'<p>{digest_title}</p>\n']
    
    for entry in reversed(new_entries):  # Oldest first
        # Only include URL posts in digest
        if entry.get('url'):
            # Format date
            date_str = entry['timestamp'].strftime('%d-%b-%Y') if entry['timestamp'] else 'Unknown'
            
            # Build card HTML
            card_html = '<div class="link_list_card">'
            
            # Image - use saved image or fallback to RSS icon
            if entry.get('image'):
                card_html += f'<div class="link_card_image"><img src="/images/{entry["image"]}" class="link_card_image_thumb" height="150" alt="link image"></div>'
            else:
                card_html += '<div class="link_card_image"><img src="/images/rss.png" class="link_card_image_thumb" height="150" alt="link image"></div>'
            
            # Date and link with headline
            card_html += f'<span class="link_list_date">{date_str}</span> - '
            headline = entry.get('headline') or entry['url']
            card_html += f'<a class="link_list_link" href="{entry["url"]}">{headline}</a></p>'
            
            # Brief Summary (if available)
            if entry.get('summary'):
                card_html += f'<p><span class="link_list_summary_title">Brief Summary:</span> <span class="link_list_summary">"{entry["summary"]}"</span></p>'
            
            # Personal commentary (if available)
            if entry.get('commentary'):
                card_html += f'<p><span class="link_list_summary_title">Personal Notes and Commentary:</span> <span class="link_list_summary">"{entry["commentary"]}"</span></p>'
            
            card_html += '</div>\n'
            html_parts.append(card_html)
    
    digest_html = '\n'.join(html_parts)
    
    # Update last digest date
    set_setting('last_digest_date', today.strftime('%Y-%m-%d %H:%M:%S'))
    
    # Create response with file download
    filename = f"{today.strftime('%Y-%m-%d')}-Digest.txt"
    response = make_response(digest_html)
    response.headers['Content-Type'] = 'text/plain; charset=utf-8'
    response.headers['Content-Disposition'] = f'attachment; filename="{filename}"'
    
    return response

@app.route('/images/<path:filename>')
def serve_image(filename):
    """Serve images from the images folder"""
    from flask import send_from_directory
    return send_from_directory(IMAGES_FOLDER, filename)

if __name__ == "__main__":
    # Start auto-poster thread
    poster_thread = threading.Thread(target=auto_poster_thread, daemon=True)
    poster_thread.start()
    
    # Run Flask app
    app.run(debug=True, host='0.0.0.0', port=5000)
