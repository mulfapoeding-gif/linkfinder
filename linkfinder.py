#!/usr/bin/env python3
"""
linkfinder.py – Wide‑open search for download, torrent, audio and video links.

Features
--------
* Safe‑search OFF and the "download OR install …" clause OFF by default
  (you can turn them on with CLI flags).
* Huge built‑in whitelist that now includes:
  - normal software repos (GitHub, SourceForge, …)
  - popular crack / repack sites
  - **all major public torrent trackers** (including movie-specific sites)
  - media‑sharing platforms (YouTube, Vimeo, SoundCloud, …)
* Enhanced torrent section with movie-specific sites like yts.bz, rarbg, etc.
* Default extensions include audio, video and ".torrent".
* Magnet links (magnet:…) are extracted as well.
* DuckDuckGo → Google fallback with adaptive signature detection.
* Optional parallel page‑scraping for real download / magnet URLs.
* Enhanced scoring favoring magnet links and media content.
* Interactive mode – run with no arguments for guided search.

Author : <your‑name>
License: MIT
"""

# ----------------------------------------------------------------------
# Imports
# ----------------------------------------------------------------------
import argparse
import sys
import random
import re
import json
import csv
from urllib.parse import urlparse, urljoin, unquote
from concurrent.futures import ThreadPoolExecutor, as_completed
from inspect import signature

# ---------- Optional third‑party imports ----------
try:
    from ddgs import DDGS
    _HAS_DDGS = True
except ImportError:
    try:
        from duckduckgo_search import DDGS
        _HAS_DDGS = True
    except ImportError:
        _HAS_DDGS = False

try:
    from googlesearch import search as google_search
    _HAS_GOOGLE = True
except ImportError:
    _HAS_GOOGLE = False

try:
    import requests
    _HAS_REQUESTS = True
except ImportError:
    _HAS_REQUESTS = False

try:
    from bs4 import BeautifulSoup
    _HAS_BS4 = True
except ImportError:
    _HAS_BS4 = False


# ----------------------------------------------------------------------
# Constants (enhanced with movie torrent sites)
# ----------------------------------------------------------------------
DEFAULT_SITES = [
    # -------------------- normal software repos --------------------
    "github.com", "gitlab.com", "sourceforge.net", "docker.com",
    "microsoft.com", "bitbucket.org", "npmjs.com", "pypi.org",
    "crates.io", "apache.org", "packages.debian.org",
    "rpmfind.net", "download.oracle.com",

    # -------------------- cracked / repack sites --------------------
    "uptodown.com", "mediafire.com", "softpedia.com", "filecr.com",
    "cracksoftdownload.com", "crackplanet.org", "crackberry.com",
    "crackhub.com", "cracksnow.com", "skidrowreloaded.com",
    "fitgirl-repacks.site", "steamunlocked.net", "gogunblocked.com",
    "gog.com", "mega.nz", "zippyshare.com", "rapidgator.net",
    "nitroflare.com", "uploadgig.com", "uploaddrive.com",
    "sgxshare.com", "fshare.vn", "4shared.com", "netload.in",
    "rapidshare.com", "dl.free", "steampowered.com",
    "crackdownload.com", "crackwise.com", "crackms.com",
    "crackpanda.com",

    # -------------------- enhanced torrent trackers (movie focused) --------------------
    "thepiratebay.org", "thepiratebay.se", "thepiratebay.unblocked.to",
    "1337x.to", "1337x.is", "1337x.st", "1337x.unblocked.lol",
    "rarbg.to", "rarbg.unblocked.lol", "rarbg.unblocked.it",
    "yts.mx", "yts.lt", "yts.ag", "yts.bz", "yts.unblocked.lol",
    "torrentgalaxy.to", "torrentgalaxy.se", "torrentgalaxy.unblocked.lol",
    "torrentfunk.com", "torrents.io", "zooqle.com", "torlock.com",
    "torrentdownloads.me", "torrentdownloads.net",
    "eztv.re", "eztv.unblocked.lol", "eztv.it",
    "nyaa.si", "btscene.com", "limetorrents.info", "limetorrents.cc",
    "torrentz2.eu", "magnetdl.com", "seedpeer.me",
    "torrentproject.com", "torrenthunt.com", "kickasstorrents.com",
    "btdb.org", "bitsnoop.com", "torrents.me",
    "ettv.to", "ettv.unblocked.lol",
    "rarbgmirror.org", "rarbgmirror.com",
    "yify-torrent.org", "yify-torrent.unblocked.lol",
    "torrentking.io", "torrentking.unblocked.lol",

    # -------------------- video / audio streaming sites --------------------
    "youtube.com", "youtu.be", "vimeo.com", "dailymotion.com",
    "soundcloud.com", "bandcamp.com", "archive.org",
    "openload.co", "streamango.com", "fembed.com",
]

DEFAULT_EXTENSIONS = [
    # ------- archives (kept for completeness) -------
    ".zip", ".tar.gz", ".tar.bz2", ".tgz", ".gz", ".bz2",
    ".exe", ".msi", ".dmg", ".pkg", ".deb", ".rpm",
    ".apk", ".aar", ".whl", ".torrent",

    # -------------------- audio --------------------
    ".mp3", ".flac", ".wav", ".aac", ".m4a", ".ogg", ".wma",
    ".alac", ".opus",

    # -------------------- video --------------------
    ".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm",
    ".mpeg", ".mpg", ".m4v", ".3gp", ".ts", ".vob",
]

MAGNET_RE = re.compile(r"magnet:\?[^\"'<> ]+", re.IGNORECASE)

USER_AGENTS = [
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edge/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Safari/605.1.15",
]

DEFAULT_SAFESEARCH = "off"
DEFAULT_EXTRA_KEYWORDS = ""
DEFAULT_MAX_RESULTS = 60


# ----------------------------------------------------------------------
# Helper utilities
# ----------------------------------------------------------------------
def rand_ua() -> str:
    """Return a random user agent string."""
    return random.choice(USER_AGENTS)


def clean_url(url: str) -> str:
    """Remove query parameters and fragments from URL."""
    parsed = urlparse(url)
    cleaned = parsed._replace(fragment="", query="").geturl()
    return unquote(cleaned)


def is_download_url(url: str, extensions: set) -> bool:
    """Check if URL is a download link."""
    if url.lower().startswith("magnet:"):
        return True
    return any(urlparse(url).path.lower().endswith(ext) for ext in extensions)


def build_query(
    term: str,
    sites: list | None = None,
    extensions: list | None = None,
    extra_keywords: str = DEFAULT_EXTRA_KEYWORDS,
) -> str:
    """Build a search query with filters."""
    parts = [term]
    if extra_keywords:
        parts.append(extra_keywords)
    if sites:
        parts.append("(" + " OR ".join(f"site:{s}" for s in sites) + ")")
    if extensions:
        parts.append(
            "(" + " OR ".join(f"filetype:{e.lstrip('.')}" for e in extensions) + ")"
        )
    return " ".join(parts)


def dedupe_results(results: list[dict]) -> list[dict]:
    """Remove duplicate URLs from results."""
    seen = set()
    uniq = []
    for r in results:
        href = clean_url(r.get("href", ""))
        if href and href not in seen:
            seen.add(href)
            uniq.append(r)
    return uniq


# ----------------------------------------------------------------------
# Search‑engine wrappers
# ----------------------------------------------------------------------
def ddg_search(
    query: str,
    max_results: int = DEFAULT_MAX_RESULTS,
    safesearch: str = DEFAULT_SAFESEARCH,
    backend: str = "auto",
) -> list[dict]:
    """Search using DuckDuckGo."""
    if not _HAS_DDGS:
        raise RuntimeError("DuckDuckGo search library not available")
    with DDGS() as ddgs:
        raw = ddgs.text(
            query, max_results=max_results, safesearch=safesearch, backend=backend
        )
    return list(raw)


def google_search_wrapper(
    query: str, max_results: int = DEFAULT_MAX_RESULTS
) -> list[dict]:
    """Search using Google."""
    if not _HAS_GOOGLE:
        raise RuntimeError("googlesearch‑python is not installed")
    sig = signature(google_search)
    params = sig.parameters
    kwargs: dict = {}
    if "num_results" in params:
        kwargs["num_results"] = max_results
    elif "num" in params:
        kwargs["num"] = max_results
    else:
        raise RuntimeError(
            "Google search wrapper cannot determine correct argument name"
        )
    if "stop" in params:
        kwargs["stop"] = max_results
    urls = google_search(query, **kwargs)
    return [{"title": "", "href": u} for u in urls]


# ----------------------------------------------------------------------
# Optional landing‑page scraping
# ----------------------------------------------------------------------
if _HAS_REQUESTS and _HAS_BS4:
    _EXT_RE = re.compile(
        # Line 243 - FIXED
_EXT_RE = re.compile(
    rf"https?://[^\s'\"<>]+(?:{"|".join(map(re.escape, DEFAULT_EXTENSIONS))})",
    re.IGNORECASE,
)
        re.IGNORECASE,
    )

    def extract_download_links(page_url: str, extensions: set) -> set[str]:
        """Extract download links from a landing page."""
        try:
            resp = requests.get(
                page_url,
                headers={"User-Agent": rand_ua()},
                timeout=12,
                verify=False,
            )
            resp.raise_for_status()
        except requests.RequestException:
            return set()
        found = {
            m.group(0)
            for m in _EXT_RE.finditer(resp.text)
            if is_download_url(m.group(0), extensions)
        }
        found.update(m.group(0) for m in MAGNET_RE.finditer(resp.text))
        soup = BeautifulSoup(resp.text, "html.parser")
        for a in soup.find_all("a", href=True):
            href = urljoin(page_url, a["href"])
            if is_download_url(href, extensions):
                found.add(href)
        return {clean_url(u) for u in found}
else:

    def extract_download_links(page_url: str, extensions: set) -> set[str]:
        """Placeholder when requests/bs4 unavailable."""
        return set()


# ----------------------------------------------------------------------
# Enhanced scoring favoring magnet links and media content
# ----------------------------------------------------------------------
def score_result(item: dict, site_whitelist: set, ext_set: set) -> int:
    """Score a search result."""
    score = 0
    href = item.get("href", "")
    title = item.get("title", "").lower()
    domain = urlparse(href).netloc.lower()

    if any(domain.endswith(w) for w in site_whitelist):
        score += 8

    if is_download_url(href, ext_set):
        score += 8 if href.lower().startswith("magnet:") else 5

    keywords = (
        "download",
        "torrent",
        "magnet",
        "mp3",
        "flac",
        "wav",
        "movie",
        "film",
        "episode",
        "season",
        "track",
        "album",
        "1080p",
        "720p",
        "4k",
        "bluray",
        "webrip",
    )
    for kw in keywords:
        if kw in title:
            score += 1
    return score


# ----------------------------------------------------------------------
# Core search orchestration
# ----------------------------------------------------------------------
def _run_engine_search(
    query: str,
    max_results: int,
    safesearch: str,
    backend: str,
    verbose: bool,
) -> list[dict]:
    """Run search engines with fallback."""
    raw = []
    # Try DuckDuckGo first
    try:
        if verbose:
            print("🔎 DuckDuckGo …")
        duck = ddg_search(
            query, max_results=max_results, safesearch=safesearch, backend=backend
        )
        raw.extend(duck)
        if len(dedupe_results(raw)) >= max_results:
            return dedupe_results(raw)[:max_results]
    except Exception as exc:
        if verbose:
            print(f"⚠️ DuckDuckGo failed: {exc}")

    # Google fallback
    if _HAS_GOOGLE:
        try:
            if verbose:
                print("🔎 Google …")
            google = google_search_wrapper(query, max_results=max_results)
            raw.extend(google)
        except Exception as exc:
            if verbose:
                print(f"⚠️ Google failed: {exc}")

    return dedupe_results(raw)[:max_results]


def run_search(
    term: str,
    sites: list | None = None,
    extensions: list | None = None,
    max_results: int = DEFAULT_MAX_RESULTS,
    extra_keywords: str = DEFAULT_EXTRA_KEYWORDS,
    safesearch: str = DEFAULT_SAFESEARCH,
    backend: str = "auto",
    scrape: bool = True,
    threads: int = 8,
    verbose: bool = False,
) -> list[dict]:
    """Run comprehensive search with optional scraping."""
    if extensions is None:
        extensions = DEFAULT_EXTENSIONS
    ext_set = {e.lower() for e in extensions}
    site_set = {s.lower() for s in sites} if sites else set()

    query = build_query(
        term,
        sites=sites,
        extensions=extensions,
        extra_keywords=extra_keywords,
    )
    if verbose:
        print(f"🛠️  Query → {query}")

    results = _run_engine_search(query, max_results, safesearch, backend, verbose)

    if not results and (sites or extra_keywords):
        if verbose:
            print(
                "⚡ No hits – trying a broader query "
                "(no site filter, no extra keywords)…"
            )
        query = build_query(term, sites=None, extensions=extensions, extra_keywords="")
        results = _run_engine_search(query, max_results, safesearch, backend, verbose)

    if not results:
        return []

    if scrape and _HAS_REQUESTS and _HAS_BS4:
        if verbose:
            print("🔎 Scraping landing pages for direct download / magnet links …")
        extra_links = {}
        with ThreadPoolExecutor(max_workers=threads) as exe:
            future_to_item = {
                exe.submit(extract_download_links, r["href"], ext_set): r
                for r in results
                if r.get("href")
            }
            for fut in as_completed(future_to_item):
                src = future_to_item[fut]
                try:
                    links = fut.result()
                except Exception as exc:
                    if verbose:
                        print(f"⚠��� Scrape error for {src.get('href')}: {exc}")
                    continue
                if links:
                    extra_links[src["href"]] = links

        for src_url, urls in extra_links.items():
            for dl in urls:
                pseudo = {
                    "title": f"Direct download from {urlparse(dl).netloc}",
                    "href": dl,
                    "source": src_url,
                }
                results.append(pseudo)
        results = dedupe_results(results)

    scored = [(r, score_result(r, site_set, ext_set)) for r in results]
    scored.sort(key=lambda pair: pair[1], reverse=True)
    return [item for item, _ in scored]


# ----------------------------------------------------------------------
# Output formatters
# ----------------------------------------------------------------------
def format_as_text(results: list[dict]) -> str:
    """Format results as plain text."""
    lines = [f"Found {len(results)} result(s):", ""]
    for i, r in enumerate(results, start=1):
        title = r.get("title") or "(no title)"
        url = r.get("href") or "(no URL)"
        source = r.get("source")
        lines.append(f"{i}. {title}")
        lines.append(f"   {url}")
        if source:
            lines.append(f"   (scraped from {source})")
        lines.append("")
    return "\n".join(lines)


def format_as_json(results: list[dict]) -> str:
    """Format results as JSON."""
    return json.dumps(results, indent=2, ensure_ascii=False)


def format_as_csv(results: list[dict]) -> str:
    """Format results as CSV."""
    from io import StringIO

    out = StringIO()
    writer = csv.writer(out, quoting=csv.QUOTE_ALL)
    writer.writerow(["title", "href", "source"])
    for r in results:
        writer.writerow(
            [r.get("title", ""), r.get("href", ""), r.get("source", "")]
        )
    return out.getvalue().strip()


# ----------------------------------------------------------------------
# Interactive CLI handling
# ----------------------------------------------------------------------
def parse_cli() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Wide‑open search for software, audio, video, torrent links."
    )
    parser.add_argument(
        "term", nargs="*", help="Search term. If omitted, interactive mode starts."
    )
    parser.add_argument(
        "-s",
        "--sites",
        default=",".join(DEFAULT_SITES),
        help="Comma‑separated whitelist of sites.",
    )
    parser.add_argument(
        "-e",
        "--extensions",
        default=",".join(DEFAULT_EXTENSIONS),
        help="Comma‑separated file extensions.",
    )
    parser.add_argument(
        "-n", "--max", type=int, default=DEFAULT_MAX_RESULTS, help="Max results (default 60)."
    )
    parser.add_argument(
        "-c", "--no-scrape", action="store_true", help="Skip page‑scraping (faster)."
    )
    parser.add_argument(
        "-t", "--threads", type=int, default=8, help="Scraping threads (default 8)."
    )
    parser.add_argument(
        "-o",
        "--output",
        choices=["text", "json", "csv"],
        default="text",
        help="Output format.",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Show progress messages."
    )
    parser.add_argument(
        "--enable-safe-search",
        action="store_true",
        help="Turn safe‑search ON (default OFF).",
    )
    parser.add_argument(
        "--extra-keywords", action="store_true", help="Add download/install keywords."
    )
    parser.add_argument(
        "--no-restrict",
        dest="no_restrict",
        action="store_true",
        help="No site whitelist.",
    )
    parser.add_argument(
        "--backend",
        choices=["auto", "html", "lite", "bing"],
        default="auto",
        help="DuckDuckGo backend.",
    )
    parser.add_argument(
        "--version", action="version", version="linkfinder 1.0"
    )
    return parser.parse_args()


def main() -> None:
    """Main entry point."""
    args = parse_cli()

    # Interactive mode
    if not args.term:
        term = input(
            "\n🔎 Enter search query (or press ENTER to quit): "
        ).strip()
        if not term:
            print("❌ No query entered – exiting.")
            sys.exit(0)

        ext_input = input(
            "🔧 Enter comma‑separated extensions (or press ENTER for defaults): "
        ).strip()
        extensions = (
            [e.strip() for e in ext_input.split(",") if e.strip()]
            if ext_input
            else None
        )

        restrict = input(
            "❓ Search the whole web (no whitelist) ? [Y/n]: "
        ).strip().lower()
        no_restrict = restrict == "" or restrict.startswith("y")

        max_input = input("🔢 How many results (default 200): ").strip()
        max_results = int(max_input) if max_input.isdigit() else 200

        # Apply best-results defaults
        args.term = [term]
        if extensions:
            args.extensions = ",".join(extensions)
        args.no_restrict = no_restrict
        args.max = max_results
        args.backend = "html"
        args.extra_keywords = True
        args.verbose = True

        print("\n🚀 Running search with optimized settings:")
        print(f"   Query: {term}")
        print(f"   Extensions: {args.extensions}")
        print(f"   No‑restrict: {args.no_restrict}")
        print(f"   Max results: {args.max}")
        print(f"   Backend: {args.backend}")
        print(f"   Extra keywords: {args.extra_keywords}")
        print()
    else:
        term = " ".join(args.term)

    # Normalize arguments
    sites = (
        None
        if args.no_restrict
        else [s.strip() for s in args.sites.split(",") if s.strip()]
    )
    extensions = [e.strip() for e in args.extensions.split(",") if e.strip()]
    extra_kw = DEFAULT_EXTRA_KEYWORDS if args.extra_keywords else ""
    safesearch = "moderate" if args.enable_safe_search else "off"

    if args.verbose:
        print(f"🔎 Term: {term}")
        print(f"⚙️  Sites: {'<none>' if sites is None else ', '.join(sites)}")
        print(f"📦 Extensions: {', '.join(extensions)}")
        print(f"🔑 Extra keywords: {'<none>' if not extra_kw else extra_kw}")
        print(f"🛡️  Safe‑search: {safesearch}")
        print(f"🔧 DuckDuckGo backend: {args.backend}")

    results = run_search(
        term,
        sites=sites,
        extensions=extensions,
        max_results=args.max,
        extra_keywords=extra_kw,
        safesearch=safesearch,
        backend=args.backend,
        scrape=not args.no_scrape,
        threads=args.threads,
        verbose=args.verbose,
    )

    if not results:
        print("❌ No results found – try a broader query or adjust the flags.")
        sys.exit(1)

    if args.output == "text":
        print(format_as_text(results))
    elif args.output == "json":
        print(format_as_json(results))
    else:
        print(format_as_csv(results))


if __name__ == "__main__":
    if _HAS_REQUESTS:
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    main()
