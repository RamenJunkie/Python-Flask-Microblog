# Microblog

A small self-hosted Flask microblog. Post links, text, and images from a web page (or a simple API), and it auto-posts them to **Bluesky** and **Mastodon**, while keeping its own searchable archive.

## Features

- Blog-style archive with pagination and search (public view for visitors, full view when logged in)
- Create posts with a link, an image, and/or commentary
- Queue that auto-posts one item per hour
- RSS feeds you can browse, queue from, or auto-queue / auto-post
- Duplicate protection: a link that's already posted or queued is never posted again
- Digest export (HTML link list of everything posted since the last digest)
- Simple API for scripts (`/api/post`) protected by an API key

## Requirements

- Linux or macOS (the app uses `fcntl` file locking, so it won't run on native Windows; use WSL or Docker)
- Python 3.9+
- A Bluesky account (use an **app password**, not your main password)
- A Mastodon account and an access token (Preferences > Development > New application, with `write` scope)

## Setup

```bash
git clone <your-repo-url> microblog
cd microblog

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

python app.py
```

Then open `http://localhost:5000`:

1. You'll land on `/setup`. Create your admin username and password (this page only works while no user exists).
2. Log in and open **Settings**. Enter your Bluesky handle + app password, your Mastodon instance URL + access token, and your site name.
3. Start posting.

On first run the app creates its own files: `microblog.db`, `posted.txt`, `topost.txt`, `images/`, and `static/uploads/`.

## Folder layout

```
microblog/
├── app.py
├── requirements.txt
├── templates/          # index.html, index_public.html, login.html, setup.html,
│                       # settings.html, queue.html, rss.html, rss_browse.html
├── images/
│   └── rss.png         # fallback thumbnail used in digests
├── static/             # CSS / JS if your templates use any
├── tools/              # maintenance scripts (check settings, sort/dedupe or repair posted.txt)
├── remote-helper/      # optional static viewer for posted.txt (see below)
│
│   Created at runtime (not in git):
├── microblog.db        # users, settings, RSS feeds
├── posted.txt          # archive of everything posted (one post per line)
├── topost.txt          # the posting queue
└── .post.lock
```

## Configuration

Most settings live in the web UI (Settings page). Optional environment variables:

| Variable | What it does |
|---|---|
| `MICROBLOG_SECRET_KEY` | Flask session secret. **Set this** to a long random string. |
| `MICROBLOG_API_KEY` | API key for `/api/post`. If unset, one is generated on first run and stored in the DB (view it at `/api/key` while logged in). |
| `MICROBLOG_HOST` | Address to listen on. Default `127.0.0.1` (this machine only). Set to `0.0.0.0` to reach it from other devices on your network. |
| `MICROBLOG_PORT` | Port to listen on. Default `5000`. |
| `MICROBLOG_DEBUG` | Set to `1` for Flask debug mode. For local development only; never turn this on while the app is reachable from a network. |

Example:

```bash
export MICROBLOG_SECRET_KEY="$(python3 -c 'import secrets; print(secrets.token_hex(32))')"
python app.py
```

### Reaching it from other devices

By default the app only listens on `127.0.0.1`, so it can be opened only from the machine it runs on. That's the safe default. If you run it on a home server and want to use it from your phone or another computer on your network, set:

```bash
export MICROBLOG_HOST=0.0.0.0
```

Then browse to `http://<server-ip>:5000`. This makes it reachable by **everything on that network**, so only do it on a network you trust, keep `MICROBLOG_DEBUG` off, and don't forward the port to the internet. If you want it public, put a reverse proxy with HTTPS in front of it.

## Using the API

```bash
# Queue a link (posted by the hourly auto-poster)
curl -X POST http://localhost:5000/api/post \
  -H "X-API-Key: YOUR_KEY" -H "Content-Type: application/json" \
  -d '{"url": "https://example.com/article", "text": "Worth a read"}'

# Add a dated entry straight to the archive (local only, nothing gets posted to socials)
curl -X POST http://localhost:5000/api/post \
  -H "X-API-Key: YOUR_KEY" -H "Content-Type: application/json" \
  -d '{"text": "Backfilled note", "date": "2024-05-01"}'

# Text + image (multipart)
curl -X POST http://localhost:5000/api/post \
  -H "X-API-Key: YOUR_KEY" -F "text=Look at this" -F "image=@photo.jpg"
```

Fields: `text`, `url`, `image`, `date` (`YYYY-MM-DD`), `time` (optional `HH:MM[:SS]`). You need at least one of text/url/image, and url + image can't be combined. No date means queued; a date means archived locally.

## Running as a service (systemd)

To keep it running in the background and start on boot, no Docker needed. This assumes the app lives in `/opt/microblog` with a venv inside it; adjust the paths and user to match yours.

1. Put your secrets in an environment file (keeps them out of the service file and out of git):

```bash
sudo nano /etc/microblog.env
```

```
MICROBLOG_SECRET_KEY=paste-a-long-random-string-here
# MICROBLOG_API_KEY=optional-set-your-own
# Uncomment to reach the app from other devices on your network (see "Reaching it from other devices"):
# MICROBLOG_HOST=0.0.0.0
```

```bash
sudo chmod 600 /etc/microblog.env
```

2. Create the service file:

```bash
sudo nano /etc/systemd/system/microblog.service
```

```ini
[Unit]
Description=Microblog (Flask)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=youruser
WorkingDirectory=/opt/microblog
EnvironmentFile=/etc/microblog.env
ExecStart=/opt/microblog/venv/bin/python app.py
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

`WorkingDirectory` matters: the app uses relative paths, so `microblog.db`, `posted.txt`, `topost.txt` and `images/` are all created and read from there.

3. Enable and start it:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now microblog
```

Everyday commands:

```bash
sudo systemctl status microblog        # is it running?
sudo systemctl restart microblog       # after updating files
journalctl -u microblog -f             # live logs
```

After pulling new code or updating `requirements.txt`:

```bash
cd /opt/microblog
source venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart microblog
```

## Remote Helper (optional)

The `remote-helper/` folder is a tiny read-only viewer for your posts. It's a single static HTML page that reads a copy of `posted.txt`, so you can show your feed on a regular website without exposing the microblog itself. The app keeps running locally, and a small sync script copies `posted.txt` and your images to your web server. See [`remote-helper/README.md`](remote-helper/README.md) for setup.

## Notes

- The background threads (hourly poster and RSS checker) start from `python app.py`. If you run the app under gunicorn/uwsgi instead, those threads won't start.
- The Bluesky password and Mastodon token are stored in plain text in `microblog.db`. Keep that file out of git (the included `.gitignore` does) and use a Bluesky app password.
- Don't expose this directly to the internet without a reverse proxy (nginx, Caddy, etc.) with HTTPS in front of it.
