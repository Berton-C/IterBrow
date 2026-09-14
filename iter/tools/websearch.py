"""Ported from the browser/MicroPython build's tools/websearch.py.

Original used `js.fetch(...)` (browser-native, CORS-exempt via origin=*).
This native port uses urllib.request directly against the same public
APIs — no CORS concern exists outside a browser sandbox, so the request
logic is unchanged; only the transport call is swapped.
"""
import json
import re
import urllib.request
import urllib.parse

DESCRIPTION = "Search the web. Returns JSON array of results with title, url, snippet."

_UA = "Mozilla/5.0 (IterBrowserElectron)"


def _get(url, timeout=10):
    req = urllib.request.Request(url, headers={"User-Agent": _UA})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.status, resp.read().decode("utf-8", errors="replace")


def _flatten_ddg_topics(related_topics, max_count=20):
    """Flatten DDG RelatedTopics, including nested topic groups."""
    out = []
    for topic in related_topics:
        if len(out) >= max_count:
            break
        if not isinstance(topic, dict):
            continue
        if topic.get("FirstURL") and topic.get("Text"):
            out.append({
                "title": topic.get("Text", "")[:80],
                "url": topic.get("FirstURL", ""),
                "snippet": topic.get("Text", "")[:200],
            })
        elif "Topics" in topic:
            for sub in topic["Topics"]:
                if len(out) >= max_count:
                    break
                if isinstance(sub, dict) and sub.get("FirstURL") and sub.get("Text"):
                    out.append({
                        "title": sub.get("Text", "")[:80],
                        "url": sub.get("FirstURL", ""),
                        "snippet": sub.get("Text", "")[:200],
                    })
    return out


def _try_ddg_ia(query, qe, max_results):
    """Backend 1: DuckDuckGo Instant Answer API."""
    results = []
    try:
        status, body = _get("https://api.duckduckgo.com/?q=" + qe + "&format=json&no_html=1")
        if status == 200:
            data = json.loads(body)
            abstract = data.get("AbstractText", "")
            abstract_url = data.get("AbstractURL", "")
            if abstract:
                results.append({
                    "title": data.get("Heading", query),
                    "url": abstract_url or ("https://duckduckgo.com/" + qe),
                    "snippet": abstract[:200],
                })
            for r in _flatten_ddg_topics(data.get("RelatedTopics", []), max_results):
                if len(results) >= max_results:
                    break
                results.append(r)
            for item in data.get("Results", []):
                if len(results) >= max_results:
                    break
                if isinstance(item, dict) and item.get("FirstURL"):
                    results.append({
                        "title": item.get("Text", query)[:80],
                        "url": item.get("FirstURL", ""),
                        "snippet": item.get("Text", "")[:200],
                    })
    except Exception:
        pass
    return results


def _try_wikipedia(query, qe, max_results):
    """Backend 2: Wikipedia Search API."""
    results = []
    try:
        wiki_url = ("https://en.wikipedia.org/w/api.php?action=query&list=search&srsearch="
                    + qe + "&format=json&origin=*&srlimit=" + str(max_results))
        status, body = _get(wiki_url)
        if status == 200:
            data = json.loads(body)
            for item in data.get("query", {}).get("search", []):
                if len(results) >= max_results:
                    break
                title = item.get("title", "")
                results.append({
                    "title": title,
                    "url": "https://en.wikipedia.org/wiki/" + str(title.replace(" ", "_")),
                    "snippet": re.sub(r"<[^>]+>", "", item.get("snippet", "")).strip()[:200],
                })
    except Exception:
        pass
    return results


def _try_hn(query, qe, max_results):
    """Backend 3: HN Algolia (tech/news)."""
    results = []
    try:
        status, body = _get("https://hn.algolia.com/api/v1/search?query=" + qe + "&tags=story")
        if status == 200:
            data = json.loads(body)
            for hit in data.get("hits", []):
                if len(results) >= max_results:
                    break
                title = hit.get("title") or hit.get("story_title") or ""
                url = hit.get("url") or hit.get("story_url") or ("https://news.ycombinator.com/item?id=" + str(hit.get("objectID", "")))
                if title and url:
                    results.append({"title": title[:80], "url": url, "snippet": "HN: " + str(hit.get("points", 0)) + " points"})
    except Exception:
        pass
    return results


def _try_opensearch(query, qe, max_results):
    """Backend 4: Wikipedia OpenSearch (titles+urls+snippets)."""
    results = []
    try:
        os_url = ("https://en.wikipedia.org/w/api.php?action=opensearch&search="
                  + qe + "&limit=" + str(max_results) + "&format=json&origin=*")
        status, body = _get(os_url)
        if status == 200:
            data = json.loads(body)
            if len(data) >= 4:
                titles = data[1] if isinstance(data[1], list) else []
                descs = data[2] if isinstance(data[2], list) else []
                urls = data[3] if isinstance(data[3], list) else []
                for i in range(min(len(titles), len(urls))):
                    if len(results) >= max_results:
                        break
                    results.append({
                        "title": str(titles[i])[:80],
                        "url": str(urls[i]),
                        "snippet": str(descs[i])[:200] if i < len(descs) else "",
                    })
    except Exception:
        pass
    return results


def _try_github(query, qe, max_results):
    """Backend 5: GitHub Search API (code repos)."""
    results = []
    try:
        status, body = _get("https://api.github.com/search/repositories?q=" + qe + "&per_page=" + str(min(max_results, 10)))
        if status == 200:
            data = json.loads(body)
            for item in data.get("items", []):
                if len(results) >= max_results:
                    break
                results.append({
                    "title": item.get("full_name", "")[:80],
                    "url": item.get("html_url", ""),
                    "snippet": (item.get("description", "") or "")[:200],
                })
    except Exception:
        pass
    return results


def _try_crossref(query, qe, max_results):
    """Backend 6: Crossref API (academic papers)."""
    results = []
    try:
        status, body = _get("https://api.crossref.org/works?query=" + qe + "&rows=" + str(min(max_results, 10)))
        if status == 200:
            data = json.loads(body)
            for item in data.get("message", {}).get("items", []):
                if len(results) >= max_results:
                    break
                title = ""
                if item.get("title"):
                    title = item["title"][0]
                doi = item.get("DOI", "")
                results.append({
                    "title": title[:80],
                    "url": "https://doi.org/" + doi if doi else "",
                    "snippet": (item.get("abstract", "") or "")[:200] if item.get("abstract") else ("Academic paper by " + ", ".join(item.get("author", [{}])[:3] and [a.get("family", "") for a in item.get("author", [])[:3]] or ["Unknown"])),
                })
    except Exception:
        pass
    return results


def _try_openlibrary(query, qe, max_results):
    """Backend 7: OpenLibrary API (books)."""
    results = []
    try:
        status, body = _get("https://openlibrary.org/search.json?q=" + qe + "&limit=" + str(min(max_results, 10)))
        if status == 200:
            data = json.loads(body)
            for doc in data.get("docs", []):
                if len(results) >= max_results:
                    break
                title = doc.get("title", "")
                olid = doc.get("cover_edition_key") or doc.get("key", "")
                results.append({
                    "title": title[:80],
                    "url": "https://openlibrary.org" + str(olid) if olid else "",
                    "snippet": "Book by " + ", ".join(doc.get("author_name", [])[:3]) if doc.get("author_name") else "Book",
                })
    except Exception:
        pass
    return results


def run(query, max_results=10):
    query = str(query).strip()
    if not query:
        raise ValueError("query must not be empty")
    max_results = max(1, min(20, int(max_results)))
    qe = urllib.parse.quote(query)

    seen_urls = set()

    def dedup(items):
        out = []
        for item in items:
            url = item.get("url", "")
            if url and url not in seen_urls:
                seen_urls.add(url)
                out.append(item)
        return out

    ddg_results = _try_ddg_ia(query, qe, max_results)
    wiki_results = _try_wikipedia(query, qe, max_results)
    all_results = dedup(ddg_results + wiki_results)

    if len(all_results) < max_results:
        os_results = _try_opensearch(query, qe, max_results)
        all_results = dedup(all_results + os_results)

    if len(all_results) < max_results:
        hn_results = _try_hn(query, qe, max_results)
        all_results = dedup(all_results + hn_results)

    if len(all_results) < max_results:
        gh_results = _try_github(query, qe, max_results)
        all_results = dedup(all_results + gh_results)

    if len(all_results) < max_results:
        cr_results = _try_crossref(query, qe, max_results)
        all_results = dedup(all_results + cr_results)

    if len(all_results) < max_results:
        ol_results = _try_openlibrary(query, qe, max_results)
        all_results = dedup(all_results + ol_results)

    if all_results:
        return json.dumps(all_results[:max_results])

    raise RuntimeError("web search failed: all backends returned no results")
