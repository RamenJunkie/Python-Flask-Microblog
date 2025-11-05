#!/usr/bin/env python3
"""
Migration script to convert old posted.txt format to new pipe-delimited format

Old format: [DATETIME] content
New format: [DATETIME]|url|headline|imageFilename|summary|commentary

Run this once to migrate your existing posts.
It will backup the old file to posted.txt.backup before converting.
"""

import os
import sys
import requests
import shutil
from datetime import datetime
from urllib.parse import urljoin
from io import BytesIO
from PIL import Image
from bs4 import BeautifulSoup

POSTED_FILE = 'posted.txt'
BACKUP_FILE = 'posted.txt.backup'
IMAGES_FOLDER = 'images'
USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'

# Ensure images folder exists
os.makedirs(IMAGES_FOLDER, exist_ok=True)

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
        print(f"  Warning: Could not fetch metadata for {url}: {e}")
        return {'title': url, 'description': '', 'image_url': None}

def download_and_crop_image(image_url, url_hash):
    """Download and crop image to 300x200"""
    try:
        headers = {'User-Agent': USER_AGENT}
        img_response = requests.get(image_url, headers=headers, timeout=10)
        img_response.raise_for_status()
        
        img = Image.open(BytesIO(img_response.content))
        if img.mode in ('RGBA', 'LA', 'P'):
            img = img.convert('RGB')
        
        # Calculate crop to 3:2 ratio (300x200)
        target_ratio = 300 / 200  # 1.5
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
        image_filename = f"link_{url_hash}.jpg"
        image_path = os.path.join(IMAGES_FOLDER, image_filename)
        img.save(image_path, format='JPEG', quality=85)
        
        return image_filename
    except Exception as e:
        print(f"  Warning: Could not download/process image: {e}")
        return None

def migrate_line(line):
    """Convert an old format line to new format"""
    if not line.strip():
        return None
    
    # Check if already in new format
    if line.startswith('[') and '|' in line[20:]:  # Check for pipe after timestamp
        bracket_end = line.find(']')
        rest = line[bracket_end+1:].strip()
        if rest.startswith('|'):
            print("  Already in new format, skipping")
            return line
    
    # Parse old format
    if not line.startswith('['):
        print(f"  Skipping malformed line: {line[:50]}...")
        return None
    
    bracket_end = line.find(']')
    if bracket_end == -1:
        print(f"  Skipping malformed line: {line[:50]}...")
        return None
    
    timestamp_str = line[1:bracket_end]
    content = line[bracket_end+1:].strip()
    
    # Parse content
    parsed = parse_content(content)
    
    # Initialize new format fields
    url = 'NULL'
    headline = 'NULL'
    image_filename = 'NULL'
    summary = 'NULL'
    commentary = 'NULL'
    
    if parsed['type'] == 'url':
        url = parsed['url']
        commentary = parsed['text'] if parsed['text'] else 'NULL'
        
        print(f"  Fetching metadata for: {url}")
        metadata = fetch_page_metadata(url)
        
        headline = metadata['title'].replace('|', '-')
        
        if metadata['description']:
            summary = metadata['description'][:200].replace('|', '-')
            if len(metadata['description']) > 200:
                summary += '...'
        
        if metadata['image_url']:
            import hashlib
            url_hash = hashlib.md5(url.encode()).hexdigest()[:12]
            print(f"  Downloading and cropping image...")
            image_filename_local = download_and_crop_image(metadata['image_url'], url_hash)
            if image_filename_local:
                image_filename = image_filename_local
                print(f"  ✓ Saved image: {image_filename}")
    
    elif parsed['type'] == 'image':
        image_filename = parsed['image']
        commentary = parsed['text'] if parsed['text'] else 'NULL'
    
    else:
        commentary = parsed['text'] if parsed['text'] else 'NULL'
    
    # Build new format line
    new_line = f"[{timestamp_str}]|{url}|{headline}|{image_filename}|{summary}|{commentary}\n"
    return new_line

def main():
    """Main migration function"""
    print("=" * 60)
    print("Posted.txt Migration Script")
    print("=" * 60)
    
    if not os.path.exists(POSTED_FILE):
        print(f"Error: {POSTED_FILE} not found!")
        sys.exit(1)
    
    # Backup original file
    print(f"\n1. Creating backup: {BACKUP_FILE}")
    shutil.copy2(POSTED_FILE, BACKUP_FILE)
    print("   ✓ Backup created")
    
    # Read all lines
    print(f"\n2. Reading {POSTED_FILE}")
    with open(POSTED_FILE, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    print(f"   Found {len(lines)} lines")
    
    # Migrate each line
    print("\n3. Migrating entries...")
    new_lines = []
    for i, line in enumerate(lines, 1):
        print(f"\n   Processing entry {i}/{len(lines)}:")
        new_line = migrate_line(line)
        if new_line:
            new_lines.append(new_line)
            print("   ✓ Migrated")
        else:
            print("   ✗ Skipped")
    
    # Write new format
    print(f"\n4. Writing migrated data to {POSTED_FILE}")
    with open(POSTED_FILE, 'w', encoding='utf-8') as f:
        f.writelines(new_lines)
    print(f"   ✓ Wrote {len(new_lines)} entries")
    
    print("\n" + "=" * 60)
    print("Migration complete!")
    print("=" * 60)
    print(f"\nOriginal file backed up to: {BACKUP_FILE}")
    print(f"Migrated {len(new_lines)} out of {len(lines)} entries")
    print("\nYou can now restart your Flask app.")

if __name__ == "__main__":
    main()