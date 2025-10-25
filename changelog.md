# Changelog

All notable changes to Flask Microblog will be documented in this file.

## [1.0.0] - 2025-10-23

### Added
- **User Authentication System**
  - Initial setup wizard for creating admin account
  - Login/logout functionality
  - Password hashing with Werkzeug security
  - Session-based authentication
  - Login required for posting and management features

- **Site Configuration**
  - Customizable site name (appears in header and title)
  - Social media links display (format: Name|URL, comma-separated)
  - All settings stored in SQLite database
  - Settings accessible via web interface

- **Post Management**
  - Create text, link, and image posts
  - Upload images with automatic processing and resizing
  - Link posts with automatic metadata fetching (title, description, image)
  - "Post immediately" or add to queue for scheduled posting
  - "Local only" option to post without sharing to social networks
  - Inline image display in timeline
  - Search functionality across all posts
  - Pagination (20 posts per page)

- **RSS Feed Integration**
  - Add and manage multiple RSS feeds
  - Browse recent entries (15 most recent) from each feed
  - Add RSS articles to posting queue with optional commentary
  - Support for immediate or scheduled posting from RSS
  - Persistent feed storage in database

- **Queue Management**
  - View all queued posts
  - Delete items from queue
  - Automatic hourly posting from queue
  - Manual posting with timer reset

- **Social Media Integration**
  - Automatic posting to Bluesky and Mastodon
  - Support for text, images, and link previews
  - Configurable API credentials via settings page
  - Rich link embeds with metadata

- **Digest Generator**
  - Generate HTML digest of posts since last digest
  - Pulls article descriptions and featured images from Open Graph metadata
  - Includes personal commentary
  - Downloads as dated text file (YYYY-MM-DD-Digest.txt)
  - Tracks last digest generation date
  - Ready for WordPress copy/paste

- **Public Timeline**
  - Non-authenticated users can view all posts
  - Search functionality available to public
  - Displays site name and social links
  - No posting capabilities for public users

- **Dark Mode UI**
  - Modern dark theme inspired by Bluesky/Mastodon
  - Responsive design for mobile and desktop
  - Card-based post layout with hover effects
  - Consistent styling across all pages

### Technical Details
- Flask 3.0.0 web framework
- SQLite database for settings, users, and RSS feeds
- Background thread for automatic posting
- Image processing with Pillow
- RSS parsing with feedparser
- BeautifulSoup for metadata extraction
- Separate CSS and template files for maintainability

### File Structure
- `app.py` - Main Flask application
- `templates/` - HTML templates (base, index, index_public, queue, rss, settings, login, setup)
- `static/css/` - Stylesheet with dark mode theme
- `images/` - Uploaded and processed images
- `posted.txt` - Archive of all posted content
- `topost.txt` - Queue of scheduled posts
- `microblog.db` - SQLite database

### Configuration
- Maximum upload size: 16MB
- Image resize: 1200x1200 max
- Auto-post interval: 1 hour
- Posts per page: 20
- RSS entries shown: 15

---

## Future Considerations
- Delete button for individual posts
- Rich link preview cards in timeline
- Multiple user accounts
- Post editing functionality
- Export/backup features
- Analytics and statistics