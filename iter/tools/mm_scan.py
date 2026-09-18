#!/usr/bin/env python3
"""Mattermost feed scanner for the COS Command Center CRM.

Reads a Mattermost server (REST API v4) for the COS's unreads/mentions/awaiting-reply
threads and writes candidates into iter/crm/data/captures.json.

Config (all optional until token provided):
  private/crm/mm_token.txt   - personal access token (contents = token)
  private/crm/mm_server.txt  - e.g. https://yourteam.mattermost.cloud
  private/crm/mm_user.txt    - username (auto-resolved to user id)

Run: python3 tools/mm_scan.py   (also usable via shell tool each morning)
Safety: read-only API calls only (GET). Never posts, reacts, or marks read.
"""
DESCRIPTION = "Scan Mattermost (mattermost.cloud) for mentions/replies-to-her and CEO/COO posts; write candidates into crm/data/captures.json for the morning Briefing. Read-only. Configure private/crm/mm_token.txt + mm_server.txt (+ optional mm_watchers.txt: one username per line, default CEO/COO placeholders)."

import json, os, re, sys, urllib.request

BASE = os.path.join(os.path.dirname(__file__), '..')
CFG = os.path.join(BASE, 'private', 'crm')
CAP = os.path.join(BASE, 'crm', 'data', 'captures.json')

def rd(f):
    p = os.path.join(CFG, f)
    if os.path.exists(p):
        v = open(p).read().strip()
        return v or None
    return None

def get(server, token, path):
    req = urllib.request.Request(server.rstrip('/') + '/api/v4' + path,
                                 headers={'Authorization': 'Bearer ' + token})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.load(r)

WATCHERS = [w.strip() for w in (open(os.path.join(CFG,'mm_watchers.txt')).read().splitlines() if os.path.exists(os.path.join(CFG,'mm_watchers.txt')) else []) if w.strip()]

def main():
    token, server, username = rd('mm_token.txt'), rd('mm_server.txt'), rd('mm_user.txt')
    if not (token and server):
        print('NOAUTH: token/server not configured yet (private/crm/mm_token.txt + mm_server.txt)')
        return
    me = get(server, token, '/users/me')
    uid = me['id']
    print('Auth OK as', me.get('username'), '| channels:')
    teams = get(server, token, '/users/' + uid + '/teams')
    caps = []
    for t in teams:
        for m in get(server, token, '/users/' + uid + '/teams/' + t['id'] + '/channels'):
            if m.get('mention_count', 0) > 0 or m.get('unread_count', 0) > 0:
                print(' -', m['name'], 'unreads:', m.get('unread_count'), 'mentions:', m.get('mention_count'))
                entry = {
                    'id': 'mm-' + m['id'] + '-' + str(m.get('last_post_at', 0)),
                    'source': 'mattermost',
                    'channel': m['name'],
                    'unreads': m.get('unread_count', 0),
                    'mentions': m.get('mention_count', 0),
                    'priority': 'high' if ((WATCHERS and any(w in (m.get('name') or '') for w in WATCHERS)) or m.get('mention_count', 0) > 0) else 'normal',
                    'captured_at': __import__('datetime').datetime.now().isoformat(timespec='seconds')
                }
                caps.append(entry)
    data = []
    if os.path.exists(CAP):
        try: data = json.load(open(CAP))
        except Exception: data = []
    ids = {c['id'] for c in data}
    for c in caps:
        if c['id'] not in ids: data.append(c)
    json.dump(data, open(CAP, 'w'), indent=2)
    print('Captures file:', CAP, '| total captures:', len(data))

if __name__ == '__main__':
    main()

# Iter tool-wrapper entry point
def run(*_a, **_k):
    main()
    return 'mm_scan complete'
