#!/usr/bin/env python3
"""Gmail feed scanner for the COS Command Center CRM (Phase 2 prep).

Read-only Gmail scan: pulls recent unread/inbox messages, extracts
sender/subject/snippet, flags awaiting-her-reply candidates into
iter/crm/data/captures.json.

Config (until OAuth is set up it runs NOAUTH-safe):
  private/crm/gmail_credentials.json  - Google OAuth client (Desktop app)
  private/crm/gmail_token.json        - stored refresh token (auto-created on first run)

Run: python3 tools/gmail_scan.py
Safety: gmail.readonly scope only. Never sends, deletes, or modifies mail.
"""
import json, os

DESCRIPTION = "Scan Gmail (read-only, gmail.readonly scope) for messages needing the COS's eyes; writes candidates into crm/data/captures.json for the morning Briefing. Configure private/crm/gmail_credentials.json (Google OAuth Desktop client). Never sends or modifies mail."
BASE = os.path.join(os.path.dirname(__file__), '..')
CFG = os.path.join(BASE, 'private', 'crm')
CAP = os.path.join(BASE, 'crm', 'data', 'captures.json')

def run(*_a, **_k):
    if not os.path.exists(os.path.join(CFG, 'gmail_credentials.json')):
        return 'NOAUTH: private/crm/gmail_credentials.json not configured yet'
    # Full implementation lands once OAuth credentials are provided:
    #   google-auth + google-api-python-client (installed via pip), gmail.readonly scope,
    #   list recent inbox messages, extract From/Subject/Snippet/InternalDate,
    #   dedupe by gmail message id, append to captures.json.
    return 'gmail_scan: credentials present, scanner pending activation'
