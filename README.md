# Telegram Status Watcher Bot — Render Deployment

## What it does
- `/start` — refreshes your page right now and shows the current value (e.g. `ON:8928`)
- `/status` — same, on demand
- Every `CHECK_INTERVAL_SECONDS` (default 60s), it checks the page in the background
  and messages you automatically **only when the value changes**.

## 1. Get your bot token and chat ID
- Message **@BotFather** on Telegram -> `/newbot` -> copy the token it gives you.
- Message **@userinfobot** on Telegram -> it replies with your numeric chat ID.

## 2. Push this folder to a GitHub repo
Render deploys from a Git repo, so create one (public or private) containing:
```
bot.py
requirements.txt
Procfile
runtime.txt
```

## 3. Create the Render service
1. Go to https://dashboard.render.com -> **New** -> **Web Service**
2. Connect your GitHub repo.
3. Settings:
   - **Runtime**: Python 3
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `python bot.py` (Render will also detect this from the Procfile)
   - **Instance Type**: Free is fine to start
4. Under **Environment**, add these variables:

   | Key | Value |
   |---|---|
   | `BOT_TOKEN` | the token from BotFather |
   | `CHAT_ID` | your numeric chat id |
   | `WATCH_URL` | e.g. `https://FOREXAMPLE.com/helloworld` |
   | `KEYWORD` | `ON` (or whatever label precedes the number) |
   | `CHECK_INTERVAL_SECONDS` | `60` (optional, defaults to 60) |

   Render also auto-sets `PORT` for you — you don't need to add it.
5. Click **Create Web Service**. Watch the logs for `Bot is starting...`.

## 4. Test it
Open your bot in Telegram and send `/start`.

## Notes / things to know
- **Free tier sleep**: Render's free web services can spin down after periods of
  inactivity and take ~30-60s to wake on the next request. Since this bot doesn't
  receive inbound HTTP traffic (only outbound polling to Telegram), you may want a
  paid instance, or a Render **Background Worker** instead of a **Web Service** if
  you don't need the HTTP health-check endpoint at all. This project includes the
  built-in health server specifically so it *can* run as a Web Service if that's
  what you prefer.
- **State on redeploy**: the "last known value" is stored in a local file
  (`last_value.txt`), which resets whenever the service restarts or redeploys
  (Render's default disk isn't persistent). That just means after a redeploy, the
  first check won't trigger a false "changed" alert — it'll simply re-learn the
  current value silently.
- **Only run one instance**: don't run this bot locally and on Render at the same
  time with the same `BOT_TOKEN` — Telegram will throw a "Conflict" error since only
  one polling connection per bot token is allowed.
