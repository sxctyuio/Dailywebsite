# The Daily Spin

A daily learning page: 3 random topics + AI every day, each with a real, lesser-known article
found by Claude with a live web search, plus a summary, fun facts, starting questions and "go deeper" links.

## How it works
- `.github/workflows/daily-stories.yml` runs every night (06:00 UTC = 10 PM Pacific standard time).
- It runs `scripts/make_stories.py`, which calls the Claude API with your **`ANTHROPIC_API_KEY` repository secret**.
- The script writes `data/stories.json` (today), `data/archive/<date>.json` and `data/seen.json`
  (a hash map of every used article URL, so nothing repeats) and commits them.
- `index.html` (GitHub Pages) only reads `data/stories.json`. The key never reaches the browser.

## Setup
1. Upload these files to a new GitHub repo (keep the folder structure).
2. **Settings → Secrets and variables → Actions → New repository secret**:
   name `ANTHROPIC_API_KEY`, value = your Claude API key.
3. **Settings → Actions → General → Workflow permissions**: choose **Read and write permissions**.
4. **Settings → Pages**: Deploy from a branch → `main` → `/ (root)` → Save.
5. **Actions tab → Daily Spin stories → Run workflow** once to create the first day of stories.

Your page: `https://<username>.github.io/<repo>/`

Cost: each night is about 4 Claude calls with up to 6 web searches each, billed to your API account.
