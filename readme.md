# Flask Microblog - Social Media Auto-Poster

Created using Claude.ai by @RamenJunkie

A dark-mode microblog web application that automatically posts to Bluesky and Mastodon. Features a modern UI inspired by popular social media platforms with automatic scheduling and rich media support.

## Features

- Modern dark mode UI with centered interface
- Public timeline viewable without logging in
- Secure admin access with password protection
- Web-based settings configuration for API credentials
- RSS feed integration for sharing articles with commentary
- Multi-platform posting to both Bluesky and Mastodon
- Rich media support with inline images and automatic link metadata
- Automatic hourly posting from queue
- Searchable archive with full-text search and pagination
- Responsive design for mobile and desktop
- SQLite database for local settings and user management

## Quick Start

### 1. Clone the Repository

```bash
git clone https://github.com/ramenjunkie/flask-microblog.git
cd flask-microblog
```

### 2. Install Dependencies

```bash
# Create a virtual environment (recommended)
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install required packages
pip install -r requirements.txt
```

### 3. Initial Setup

Run the application:

```bash
python app.py
```

Visit `http://localhost:5000` in your browser. You'll be redirected to the setup page.

**Create Admin Account:**
1. Enter a username
2. Enter a password (minimum 8 characters)
3. Confirm your password
4. Click "Create Admin Account"

**Configure API Credentials:**
1. Log in with your admin account
2. Click "Settings" in the navigation
3. Enter your Bluesky credentials:
   - Bluesky Handle: your-handle.bsky.social
   - Bluesky App Password: Get from Bluesky Settings → App Passwords
4. Enter your Mastodon credentials:
   - Mastodon Instance URL: https://your-instance.social
   - Mastodon Access Token: Get from Settings → Development → New Application
5. Click "Save Settings"

**Getting Bluesky Credentials:**
1. Go to Bluesky Settings → App Passwords
2. Create a new app password
3. Use your handle and the generated password

**Getting Mastodon Credentials:**
1. Go to your Mastodon instance Settings → Development
2. Create a new application with `write:statuses` and `write:media` permissions
3. Copy the access token

### 4. Run the Application

```bash
python app.py
```

Visit `http://localhost:5000` in your browser.

## Project Structure

```
flask-microblog/
├── app.py                      # Main Flask application
├── requirements.txt            # Python dependencies
├── README.md                   # This file
├── microblog.db                # SQLite database (auto-created)
├── topost.txt                  # Queue (auto-created)
├── posted.txt                  # Archive (auto-created)
├── templates/
│   ├── base.html              # Base template with header/nav
│   ├── index.html             # Main page with post form (logged in)
│   ├── index_public.html      # Public timeline view (not logged in)
│   ├── queue.html             # Queue management page
│   ├── setup.html             # Initial setup page
│   ├── login.html             # Login page
│   ├── settings.html          # Settings/credentials page
│   ├── rss.html               # RSS feed management
│   └── rss_browse.html        # Browse RSS entries
├── static/
│   └── css/
│       └── style.css          # Dark mode stylesheet
├── images/                     # Uploaded images (auto-created)
└── uploads/                    # Additional uploads (auto-created)
```

## Usage Guide

### First Time Setup

1. **Create Admin Account** - On first run, you'll be prompted to create an admin account. Only one admin account can be created during initial setup. After setup is complete, the setup page is no longer accessible.
2. **Configure Credentials** - Go to Settings and enter your Bluesky and Mastodon API credentials.
3. **Start Posting** - You're ready to go.

### Public Access

- Anyone can view the timeline without logging in
- Visitors see all posts with images and links
- Search functionality available to all
- Only logged-in admin can create posts, manage queue, or change settings

### Managing Credentials

All API credentials are stored securely in the local SQLite database:
- Navigate to Settings in the top menu
- Update your Bluesky or Mastodon credentials anytime
- Passwords are stored securely using industry-standard hashing

### Creating Posts

**Text Post:**
- Enter your text in the main field
- Check "Post immediately" to post right away
- Uncheck to add to the hourly queue
- Check "Local only" to add to timeline without posting to social networks

**Link Post:**
- Enter text in the main field
- Add a URL in the "Link" field
- The app automatically fetches title, description, and featured image
- Creates rich link previews on both platforms (unless local only)

**Image Post:**
- Enter caption text
- Upload an image file (JPG, PNG, GIF, WebP)
- Image is stored locally and posted to both platforms (unless local only)
- Images are displayed inline in the timeline for all visitors

**Local-Only Posts:**
- Check the "Local only" checkbox
- Post appears in your timeline immediately
- Does not get posted to Bluesky or Mastodon
- Perfect for personal notes or drafts you want to keep locally

### Queue Management

- View queued posts at `/queue`
- Posts are automatically posted every hour (if nothing else has been posted)
- Delete items from queue as needed
- Manual posts reset the 1-hour timer

### Archive & Search

- All posts are archived with timestamps
- Full-text search across content
- Paginated view (20 posts per page)
- Click links to open original URLs

### RSS Feed Integration

**Add RSS Feeds:**
- Navigate to the RSS page
- Enter an RSS feed URL (e.g., `https://example.com/feed.xml`)
- Optionally give it a friendly name
- Click "Add Feed"

**Browse and Share Articles:**
- Click "Browse" on any saved feed
- View the 15 most recent entries
- See title, summary, author, and publication date
- Add optional commentary
- Click "Add to Queue" to schedule for posting
- Articles will be posted with your commentary and a link

**Manage Feeds:**
- View all saved RSS feeds
- Delete feeds you no longer need
- Feeds persist between sessions in the database

## Configuration Options

### Change Auto-Post Interval

Edit the `auto_poster_thread()` function in `app.py`:

```python
if time.time() - last_auto_post_time >= 3600:  # 3600 = 1 hour
```

Change `3600` to your desired interval in seconds (e.g., `7200` for 2 hours).

### Change Posts Per Page

Edit the `index()` route in `app.py`:

```python
result = get_posted_entries(page=page, per_page=20)  # Change 20
```

### Customize Styling

Edit `static/css/style.css` to modify:
- Colors (change `#5b7ec4` for primary accent)
- Layout width (change `.container max-width`)
- Dark mode shades
- Typography

## Production Deployment

### Using Gunicorn

```bash
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

### Systemd Service (Linux)

Create `/etc/systemd/system/microblog.service`:

```ini
[Unit]
Description=Flask Microblog
After=network.target

[Service]
User=yourusername
WorkingDirectory=/path/to/flask-microblog
Environment="PATH=/path/to/flask-microblog/venv/bin"
ExecStart=/path/to/flask-microblog/venv/bin/gunicorn -w 4 -b 0.0.0.0:5000 app:app
Restart=always

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl enable microblog
sudo systemctl start microblog
sudo systemctl status microblog
```

### Nginx Reverse Proxy

Add to your Nginx configuration:

```nginx
server {
    listen 80;
    server_name yourdomain.com;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /static {
        alias /path/to/flask-microblog/static;
        expires 30d;
    }

    location /images {
        alias /path/to/flask-microblog/images;
        expires 30d;
    }
}
```

### HTTPS with Let's Encrypt

```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d yourdomain.com
```

## Security Best Practices

### Use Environment Variables

Instead of hardcoding credentials in `app.py`, use environment variables:

```python
import os

BLUESKY_HANDLE = os.getenv('BLUESKY_HANDLE')
BLUESKY_PASSWORD = os.getenv('BLUESKY_PASSWORD')
MASTODON_INSTANCE_URL = os.getenv('MASTODON_INSTANCE_URL')
MASTODON_ACCESS_TOKEN = os.getenv('MASTODON_ACCESS_TOKEN')
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'fallback-dev-key')
```

Set them in your environment:

```bash
export BLUESKY_HANDLE='your-handle.bsky.social'
export BLUESKY_PASSWORD='your-app-password'
export MASTODON_INSTANCE_URL='https://your-instance.social'
export MASTODON_ACCESS_TOKEN='your-access-token'
export SECRET_KEY='your-random-secret-key'
```

### File Permissions

```bash
chmod 600 topost.txt posted.txt microblog.db
chmod 700 images/
```

### Firewall Configuration

```bash
sudo ufw allow 5000/tcp  # If exposing directly
# Or only allow nginx
sudo ufw allow 'Nginx Full'
```

### Regular Updates

```bash
pip install --upgrade -r requirements.txt
```

## Troubleshooting

### Cannot Access Application

**Issue:** Redirected to setup page when user already exists

**Solution:** Navigate directly to `/login` or delete `microblog.db` to start fresh

### Forgot Admin Password

**Issue:** Cannot log in to the application

**Solution:** Delete `microblog.db` to reset (Note: This will also delete your API credentials)

**Better Solution:** Add a password reset feature or create a new admin via Python:

```python
import sqlite3
from werkzeug.security import generate_password_hash

conn = sqlite3.connect('microblog.db')
c = conn.cursor()
c.execute('UPDATE users SET password_hash = ? WHERE username = ?', 
          (generate_password_hash('new-password'), 'admin'))
conn.commit()
conn.close()
```

### RSS Feeds Not Loading

**Issue:** Cannot fetch RSS feed entries

**Solution:**
- Verify the RSS feed URL is correct and accessible
- Check if the feed is valid RSS/Atom format
- Test the feed URL in an RSS reader first
- Check console for feedparser errors

### Cannot Add RSS Feed

**Issue:** "Invalid RSS feed" error

**Solution:**
- Ensure the URL points to an actual RSS/Atom feed (usually ends in .xml, .rss, or /feed)
- Some sites have RSS feeds at `/feed`, `/rss`, or `/atom`
- Check if the site blocks automated requests

### RSS Entries Show Wrong Date

**Issue:** Published dates appear incorrect

**Solution:** This is the date from the feed itself - contact the feed publisher if incorrect

### Posts Not Appearing on Social Media

- Verify credentials are correct in Settings page
- Check console output for error messages
- Test network connectivity to both platforms
- Ensure API permissions are correct (Mastodon needs `write:statuses` and `write:media`)

### Images Not Uploading

- Check `images/` folder exists and is writable
- Verify file size is under 16MB
- Ensure file format is supported (JPG, PNG, GIF, WebP)
- Check console for PIL/Pillow errors

### Auto-Posting Not Working

- Ensure Flask app is running continuously (not just for testing)
- Check `topost.txt` has content
- Verify background thread started (check console on startup)
- Ensure at least 1 hour has passed since last post

### Port Already in Use

```bash
# Find process using port 5000
lsof -i :5000

# Kill the process
kill -9 <PID>

# Or use a different port
python app.py --port 5001
```

## Dependencies

- Flask 3.0.0 - Web framework
- atproto 0.0.46 - Bluesky API client
- Mastodon.py 1.8.1 - Mastodon API client
- requests 2.31.0 - HTTP library
- beautifulsoup4 4.12.2 - HTML parsing for metadata
- Pillow 10.1.0 - Image processing
- feedparser 6.0.10 - RSS/Atom feed parsing

## Contributing

Contributions are welcome. Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## License

This project is open source and available under the MIT License.

## Acknowledgments

- UI design inspired by Bluesky and Mastodon
- Built with Flask and modern web technologies
- Thanks to the atproto and Mastodon.py library maintainers

## Support

For issues, questions, or suggestions:
- Open an issue on GitHub
- Check existing issues for solutions
- Review the troubleshooting section above
