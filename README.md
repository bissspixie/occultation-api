# Occultation Ledger API

A tiny backend that stores your logged occultation events in one place, so
your website, your Telegram bot, and any other device can all read and
write the same list. Automatically works out each event's brightness drop
and magnitude tier (bright 4–6 / faint 9–12).

No terminal or command-line experience required to get this running online
— follow the steps below in order.

---

## Part 1 — Put this on GitHub (no coding, just uploading)

1. Go to [github.com](https://github.com) and make a free account if you
   don't have one.
2. Click the **+** icon (top right) → **New repository**.
3. Name it something like `occultation-api`. Keep it **Public**. Don't
   tick any of the extra checkboxes. Click **Create repository**.
4. On the new (empty) repo page, click **uploading an existing file**.
5. Drag in all three files from this folder: `main.py`,
   `requirements.txt`, and this `README.md`.
6. Scroll down, click **Commit changes**. Done — your code is now on
   GitHub.

---

## Part 2 — Make it live on the internet (free)

We'll use [Render](https://render.com) — it can run a Python program
continuously for free and gives you a public web address.

1. Go to [render.com](https://render.com) and **sign up using your GitHub
   account** (this lets it see your repos without any extra passwords).
2. Click **New +** → **Web Service**.
3. Pick the `occultation-api` repo you just created.
4. Render will ask a few settings — fill in exactly:
   - **Runtime**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn main:app --host 0.0.0.0 --port $PORT`
   - **Instance Type**: `Free`
5. Click **Create Web Service**. Render will install everything and start
   it — takes a couple of minutes the first time. Watch the log; when it
   says something like `Application startup complete`, it's live.
6. You'll get a public URL that looks like
   `https://occultation-api.onrender.com`. That's your API's address —
   save it, you'll need it below.

**One quirk of the free tier:** if nobody's used it in a while, it goes to
sleep and takes ~30–50 seconds to wake up on the next request. Fine for a
hobby project; just don't expect instant replies after idle periods.

---

## Part 3 — Try it without writing any code

Visit `https://your-url.onrender.com/docs` in a browser (swap in your
actual URL). This opens an interactive page (built into the API
automatically) where you can:

- Expand **POST /events**, click "Try it out," edit the example event,
  and click **Execute** to add a real event.
- Expand **GET /events** and click **Execute** to see everything stored
  so far.

This is genuinely the fastest way to test whether it works — no coding,
just clicking buttons on that page.

---

## Part 4 — Connect it to your other tools

**From the website (JavaScript):**
```javascript
// Add an event
await fetch("https://your-url.onrender.com/events", {
  method: "POST",
  headers: {"Content-Type": "application/json"},
  body: JSON.stringify({
    name: "TYC 1234-567",
    type: "asteroid",
    starmag: 9.5,
    objmag: 13.2,
    datetime: "2026-09-14T21:30"
  })
});

// List all events
const events = await fetch("https://your-url.onrender.com/events").then(r => r.json());
```

**From the Telegram alert bot (Python):**
Instead of reading a local `events.json` file, have it call:
```python
import requests
events = requests.get("https://your-url.onrender.com/events").json()
```
Everything else in the bot script stays the same — it just gets its event
list from the API instead of a file on disk.

---

## What's actually happening, in plain terms

- `main.py` is a small program that, when running, listens for requests
  (like "add this event" or "give me all events") and answers them.
- It stores everything in a small file-based database (`events.db`) that
  lives alongside the program.
- GitHub is just where the *code* lives, like a shared drive. Render is
  what actually *runs* that code continuously so it can answer requests
  any time of day, from any device.

If you want to poke around and understand `main.py` line by line later,
each section is commented — but you don't need to understand it to use it.
