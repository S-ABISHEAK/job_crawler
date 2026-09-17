# AI/LLM Job Crawler

A personal, local-only crawler + dashboard that finds fresh AI/LLM
internship/fresher job postings, scores them against your profile, and
tracks your application pipeline. No auth, no cloud deployment — one
process, one SQLite file.

## Stack

- **Backend:** FastAPI + Uvicorn (single process, no build step)
- **DB:** SQLite via SQLAlchemy (file: `job_crawler.db`, created automatically)
- **Scheduler:** APScheduler, running in-process, one job per enabled source
- **Frontend:** Server-rendered Jinja2 templates + vanilla JS (no React, no bundler)
- **Config:** Plain YAML in `config/` — no code changes needed to add a company, source, or tune scoring

## Setup

Requires Python 3.11+.

```bash
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e .
uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000. On first startup the app creates
`job_crawler.db`, runs one ingestion pass across every enabled source, and
starts the background scheduler (each source then polls on its own
`poll_interval` from `config/sources.yaml`).

## What you get

- **Feed** (`/`) — all postings sorted by relevance score, filterable by
  level / location / source, with red-flagged postings hidden by default
  (checkbox to show them) and a "NEW" badge for postings seen since your
  last visit.
- **Pipeline** (`/pipeline`) — kanban-style board across New → Reviewed →
  Applied → Outreach Sent → Replied → Interview → Offer/Rejected. Change a
  posting's stage from its status dropdown on any page.
- **Outreach** (`/outreach`) — log who you messaged, when, and whether they
  replied. Anyone unreplied after 7+ days gets a "follow up" flag.
- **Analytics** (`/analytics`) — applied/replied/interview/offer counts,
  broken down by source and by outreach vs. no-outreach, so you can see
  which channels actually convert.

Click **Refresh now** in the top nav to trigger an ingestion pass on demand
instead of waiting for the scheduler.

## Adding a company (Tier 1: Greenhouse/Lever/Ashby)

Edit `config/companies.yaml` and add one entry:

```yaml
  - name: Some AI Startup
    board: greenhouse   # or lever, or ashby
    slug: someaistartup
    notes: optional
```

Find the slug from the company's careers page URL (it's usually embedded
directly, e.g. `jobs.lever.co/{slug}`, `boards.greenhouse.io/{slug}`,
`jobs.ashbyhq.com/{slug}`), or just try the API URL pattern with your guess:

- Greenhouse: `https://boards-api.greenhouse.io/v1/boards/{slug}/jobs`
- Lever: `https://api.lever.co/v0/postings/{slug}`
- Ashby: `https://api.ashbyhq.com/posting-api/job-board/{slug}`

If it returns JSON instead of a 404, the slug is right. **The seed list in
`config/companies.yaml` is best-effort** (I don't have your real target list)
— verify slugs before relying on them, some will be wrong or stale.

## Discovering new companies (don't hand-guess slugs one at a time)

Hand-guessing board slugs doesn't scale, and a lot of companies — especially
India/France-based ones — don't use Greenhouse/Lever/Ashby at all (Workday,
SmartRecruiters, Welcome to the Jungle, or a custom careers page are common
instead). Guessing the wrong board/slug just adds silent 404s, so there's a
two-step workflow instead:

1. **Add company names** (no slug/board guessing needed) to
   `config/candidate_companies.yaml`. It's pre-seeded with ~30 India and
   France AI/LLM/SLM startups as a starting point — add more as you find
   them (YC's public company directory, Tracxn/Crunchbase lists, LinkedIn
   company search, VC portfolio pages, news coverage, etc.).

2. **Run the verifier**:

   ```bash
   python scripts/verify_companies.py            # dry run, prints matches
   python scripts/verify_companies.py --append    # also writes confirmed
                                                    # matches into
                                                    # config/companies.yaml
   ```

   It tries several slug variants (lowercased, hyphenated, with common
   suffixes like "AI"/"Technologies" stripped) against all three board
   APIs for every candidate, and only reports/appends companies that
   actually return real, live job data. Everything it can't confirm is
   printed as "no match" — that's expected for companies not on these
   three platforms, not a bug.

This keeps `config/companies.yaml` free of unverified guesses going
forward — new entries added via `--append` are only ones the script
actually confirmed are live. Companies that don't verify here are
candidates for a dedicated RSS/scrape source instead (see "Adding a new
source" below) rather than Tier 1.

## Adding a new source

Edit `config/sources.yaml`:

```yaml
  - name: some-new-board
    type: rss              # api | rss | email-parse | scrape
    driver: app.ingest.rss
    url: https://example.com/feed
    poll_interval: 480     # minutes
    risk_level: low
    enabled: true
```

- `type: api` sources are matched by `name` to a built-in driver
  (`greenhouse`, `lever`, `ashby`) in `app/scheduler.py::build_driver`.
- `type: rss` uses `app/ingest/rss.py` against any feed URL.
- `type: scrape` is a stub (`app/ingest/scrape_generic.py`) — **check
  `{site}/robots.txt` yourself before implementing a real scraper**, then
  add a site-specific parser (markup varies too much for one generic
  scraper).
- `type: email-parse` is the Gmail-alert tier — see below.

Sources default to `enabled: true`; several Tier 2/3 sources ship
`enabled: false` because their feed URLs/robots.txt haven't been verified
yet — flip the flag once you've checked.

## Tuning relevance scoring

Everything in `config/keywords.yaml` (keyword groups + weights) and
`config/scoring.yaml` (level/location weights, red-flag patterns) is
config, not code. Edit either file and restart the app (or wait — config is
cached but reloadable via `app.config.reload_config()`), no code changes
needed. Suggested workflow: run it for a week or two, look at what's
scoring too high/low in the feed, and adjust weights.

## Enabling Gmail ingestion (Tier 3: LinkedIn/Naukri/Indeed/Glassdoor alerts)

This tier is stubbed out (`app/ingest/email_gmail.py`) — parser scaffolding
is in place but returns no results until you wire it up:

1. Set up job-alert email subscriptions on LinkedIn/Naukri/Indeed/Glassdoor
   yourself, and filter them into a dedicated Gmail label (e.g. `job-alerts`).
2. Create a Google Cloud project, enable the Gmail API, create OAuth
   desktop-app credentials, and save the client secret JSON as
   `config/gmail_credentials.json` (already gitignored).
3. Implement `_fetch_messages()` in `app/ingest/email_gmail.py` using
   `google-api-python-client`'s `users.messages.list`/`get`, and fill in
   `parse_linkedin_alert` / `parse_naukri_alert` / etc. once you have real
   sample emails to match against (each platform's alert HTML format is
   different).
4. Set `enabled: true` for the `gmail-alerts` entry in `config/sources.yaml`.

## Debugging ingestion

Every raw payload fetched (before normalization/scoring) is stored in the
`raw_ingest_log` table, so you can inspect exactly what a source returned
if a posting looks wrong or missing.

## Notes on scope / restraint

- LinkedIn and Naukri are never scraped directly — only via the Gmail-alert
  path, per their ToS.
- Tier 2/3 scrape sources (Wellfound, Cutshort, Instahyre, Hirist,
  Internshala, Unstop) ship disabled by default. Check each site's
  `robots.txt` before enabling and implementing a real parser.
- All scheduled polling respects the `poll_interval` set per source in
  `config/sources.yaml` — increase intervals if you want to be more
  conservative.
