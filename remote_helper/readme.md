# Remote Helper

A tiny, read-only web viewer for your microblog's `posted.txt`. It's one static HTML page, with no Flask, no database, and no server-side code, so you can put your posts on a regular website while the real microblog stays safely on your home network.

## What is this?

The main microblog app runs locally (on my network, where it can reach my RSS reader). I still wanted my posts on my public website, without exposing the app itself. This page reads a copy of `posted.txt` in the browser and shows it as a paginated, dark-themed feed.

## Files

| File | Required | What it does |
|---|---|---|
| `index.html` | yes | The viewer. All CSS and JS are inline. |
| `settings.md` | yes | Your site title, link list, and footer (format below). |
| `posted.txt` | yes | Copied from the main microblog (see "Keeping it in sync"). |
| `images/` | yes, if you post images | Copied from the main microblog. |
| `style.css` | no | If present in the same folder, it's loaded after the built-in styles, so it can override them. |

Put all of these in the same folder on your web server, wherever you want the feed to appear.

## settings.md

```
Your Blog Title
Mastodon | https://example.social/@you
Bluesky | https://bsky.app/profile/you.example
Footer | Anything you want in the footer. HTML is fine.
```

- **Line 1** is the page title and heading.
- **Every other `Name | URL` line** becomes a link in the header.
- **A line starting with `Footer |`** (any capitalization) becomes the footer text. HTML is allowed there, so you can include a link.

## Keeping it in sync

The viewer is only as fresh as its copy of `posted.txt`, so something needs to copy the file (and any new images) to the web server. I use a small script on the machine that runs the microblog, triggered by cron. Fill in the placeholders:

```bash
#!/bin/bash
set -e

# Use absolute paths so cron can find everything
SRC_FILE="/path/to/your/microblog/posted.txt"
SRC_IMAGES="/path/to/your/microblog/images/"        # keep the trailing slash
REMOTE_ALIAS="your-ssh-alias"                      # a Host entry in ~/.ssh/config
DEST_DIR="/path/on/server/to/remote-helper"
DEST_IMAGES="$DEST_DIR/images"

# Make sure the remote folders exist
ssh "$REMOTE_ALIAS" "mkdir -p '$DEST_DIR' '$DEST_IMAGES'"

# Overwrite posted.txt every time
scp "$SRC_FILE" "$REMOTE_ALIAS:$DEST_DIR/posted.txt"

# Images: only copy files that don't already exist on the server
rsync -av --ignore-existing "$SRC_IMAGES" "$REMOTE_ALIAS:$DEST_IMAGES/"
```

Save it as `microblog_sync.sh`, make it executable, and test it by hand first:

```bash
chmod +x microblog_sync.sh
./microblog_sync.sh
```

Then schedule it:

```bash
crontab -e
```

```
*/30 * * * * /path/to/microblog_sync.sh >> /path/to/microblog_sync.log 2>&1
```

That runs at :00 and :30 every hour. Cron can't type a passphrase, so the SSH key it uses needs to be one that doesn't prompt for one (ideally a dedicated key that only has access to the web server).

The viewer files themselves (`index.html`, `settings.md`, `style.css`) don't change often, so you can copy or deploy them to the server however you normally do. The sync script only handles the data.

## Good to know

- **Everything in `posted.txt` becomes public**, including entries you saved as "local only" in the main app. Only sync a `posted.txt` you're happy to have readable by anyone. Never sync `topost.txt`, `microblog.db`, or anything else.
- The server just needs to serve `.txt` files as plain text, which is the default almost everywhere.
- Posts show newest first, 10 per page. Change `POSTS_PER_PAGE` near the top of the script in `index.html` if you want a different number.
- If you see "Error loading posts", `posted.txt` isn't in the same folder as `index.html` (or isn't readable by the web server). If images are broken, check that `images/` was copied next to it.
