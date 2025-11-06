# Remote Helper

## What is This?

This is a single page html read viewer for the posted.txt file.  It has it's own styling but if you place a copy of the /static/styles.css file into the same folder, it will apply that styling.

## How to Use

I made this so I could hve a remote version of the MicroBlog without all the over head.  I run the Flask app locally on my network, where it can access my RSS reader and is more secure.  I wanted to use the posts however on my website.

This index, the settings.md, and the style.css (Optional) where you want the posts to appear.  Then also add the posted.txt file fromt he main blog.

In my case, I have a cron job that automatically copies the posted and images folder.  This bash script can be modified to do that.

```Bash
#!/bin/bash

# Absolute paths for cron compatibility
SRC_FILE="[REPLACE ME PATH TO YOUR LOCAL BLOG]/posted.txt"
SRC_IMAGES="[REPLACE ME PATH TO YOUR LOCAL BLOG]images/"
REMOTE_ALIAS="[REPLACE ME YOUR SSH ALIAS FOR YOUR REMOTE SERVER]"
DEST_DIR="[REMODE DESTINATION FOR MICROBLOG]"
DEST_IMAGES="[REMODE DESTINATION FOR MICROBLOG]/images"

# Ensure remote directories exist
ssh $REMOTE_ALIAS "mkdir -p $DEST_DIR $DEST_IMAGES"

# Overwrite posted.txt every time
scp "$SRC_FILE" "$REMOTE_ALIAS:$DEST_DIR/posted.txt"

# Sync images: only copy files that do NOT exist remotely
rsync -av --ignore-existing "$SRC_IMAGES" "$REMOTE_ALIAS:$DEST_IMAGES"
```

Then add it to your crontab, below runs every 30 minutes on the half hour

``` Bash
crontab -e
```

```
*/30 * * * * [REPLACE ME PATH TO SCRIPT]/microblog_sync.sh >> [REPLACE ME PATH TO SCRIPT]/microblog_sync.log 2>&1
```


