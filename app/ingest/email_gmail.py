"""Stubbed Gmail job-alert email ingestion (Tier 3).

Intended flow once wired up:
  1. You subscribe to job alerts on LinkedIn/Naukri/Indeed/Glassdoor with
     your own account and filter them into a dedicated Gmail label
     (e.g. "job-alerts").
  2. This driver authenticates via OAuth (google-api-python-client) and
     pulls messages under that label.
  3. `parse_alert_email()` extracts title/company/location/link per
     platform's email HTML format.

To enable:
  1. Create a Google Cloud project, enable the Gmail API, create OAuth
     desktop-app credentials, and save the client secret JSON as
     `config/gmail_credentials.json` (gitignored).
  2. Set GMAIL_LABEL and GMAIL_TOKEN_PATH in your environment or a `.env`
     file (see README).
  3. Set `enabled: true` for the gmail-alerts entry in config/sources.yaml.
  4. Implement `_fetch_messages()` below using the Gmail API
     `users.messages.list`/`get` calls, and fill in the per-platform
     parsers in `PLATFORM_PARSERS`.

Until then, fetch() returns an empty list so the rest of the pipeline
works without Gmail credentials.
"""
from __future__ import annotations

import logging
import re

from app.ingest.base import IngestDriver, RawPosting

logger = logging.getLogger(__name__)


def parse_linkedin_alert(html: str) -> list[dict]:
    """Extract postings from a LinkedIn job-alert email body.

    LinkedIn alert emails list postings as repeated blocks with a title
    link, company name, and location. Exact markup changes over time --
    this is a starting point to adapt once you have real sample emails.
    """
    raise NotImplementedError("Fill in once you have a sample LinkedIn alert email.")


def parse_naukri_alert(html: str) -> list[dict]:
    raise NotImplementedError("Fill in once you have a sample Naukri alert email.")


def parse_indeed_alert(html: str) -> list[dict]:
    raise NotImplementedError("Fill in once you have a sample Indeed alert email.")


def parse_glassdoor_alert(html: str) -> list[dict]:
    raise NotImplementedError("Fill in once you have a sample Glassdoor alert email.")


PLATFORM_PARSERS = {
    "linkedin.com": parse_linkedin_alert,
    "naukri.com": parse_naukri_alert,
    "indeed.com": parse_indeed_alert,
    "glassdoor.com": parse_glassdoor_alert,
}


def detect_platform(sender_email: str) -> str | None:
    for domain in PLATFORM_PARSERS:
        if domain in sender_email:
            return domain
    return None


class GmailAlertDriver(IngestDriver):
    source_name = "gmail-alerts"

    def fetch(self) -> list[RawPosting]:
        logger.info(
            "gmail-alerts source is stubbed -- no OAuth credentials configured. "
            "See app/ingest/email_gmail.py docstring to enable."
        )
        return []

    def _fetch_messages(self) -> list[dict]:
        """Not implemented: would use google-api-python-client's Gmail API
        to list/get messages under the configured label."""
        raise NotImplementedError
