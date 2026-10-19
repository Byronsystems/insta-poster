# Instagram poster

When the user asks for a post (e.g. "post about X"):

1. Write a new HTML design in `posts/<date>-<slug>.html`, sized 1080x1350, using `posts/example.html` as the style reference. Keep text large and readable on a phone.
2. Run `python post.py render posts/<file>.html` and show the user the resulting `.jpg` plus a draft caption (with a few relevant hashtags). Wait for their OK before posting.
3. Commit and push the `.jpg` so it has a public URL:
   `https://raw.githubusercontent.com/<owner>/<repo>/main/posts/<file>.jpg`
4. Run `python post.py publish <url> "<caption>"` and give the user the post link.

`IG_ACCESS_TOKEN` comes from the environment. Never print it or commit it.
Check the connection with `python post.py check`.
