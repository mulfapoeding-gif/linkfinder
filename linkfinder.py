#!/usr/bin/env python3
"""
linkfinder.py – Wide‑open search for download, torrent, audio and video links.

Features
--------
* Safe‑search OFF and the “download OR install …” clause OFF by default
  (you can turn them on with CLI flags).
* Huge built‑in whitelist that already contains:
  - normal software mirrors (GitHub, SourceForge, …)
  - popular crack / repack sites
  - **all major public torrent trackers**
  - media‑sharing platforms (YouTube, Vimeo, SoundCloud, …)
* Default extensions include audio, video and “.torrent”.
* Magnet links (magnet:…) are extracted as well.
* DuckDuckGo → Google fallback, with a **detect‑signature** wrapper that works
  for any current version of `googlesearch‑python`.
* Optional parallel page‑scraping for real download / magnet URLs.
* Simple relevance scoring – gives a higher score to magnet links, media
  domains and obvious keywords.
* Plain‑text / JSON / CSV output.
* **Interactive mode** – just run `python linkfinder.py` and the script will
  ask you for the query (and optional extensions) and then run with the
  “best‑results” defaults, so you never have to remember a long one‑liner.

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
    from ddgs import DDGS                     # preferred name (the lib was renamed)
    _HAS_DDGS = True
except Exception:   # pragma: no cover
    try:
        from duckduckgo_search import DDGS   # back‑compat fallback
        _HAS_DDGS = True
    except Exception:
        _HAS_DDGS = False

try:
    from googlesearch import search as google_search   # Google fallback (no API key)
    _HAS_GOOGLE = True
except Exception:   # pragma: no cover
    _HAS_GOOGLE = False

try:
    import requests
    _HAS_REQUESTS = True
except Exception:   # pragma: no cover
    _HAS_REQUESTS = False

try:
    from bs4 import BeautifulSoup
    _HAS_BS4 = True
except Exception:   # pragma: no cover
    _HAS_BS4 = False


# ----------------------------------------------------------------------
# Constants (feel free to edit)
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
    "crackdownload.com", "crackwise.com", "crackms.com", "crackpanda.com",

    # -------------------- torrent trackers --------------------
    "thepiratebay.org", "thepiratebay.se", "thepiratebay.unblocked.to",
    "1337x.to", "1337x.is", "1337x.st",
    "rarbg.to", "rarbg.unblocked.lol", "rarbg.unblocked.it",
    "yts.mx", "yts.lt", "yts.ag",
    "torrentgalaxy.to", "torrentgalaxy.se", "torrentgalaxy.unblocked.lol",
    "torrentfunk.com", "torrents.io", "zooqle.com", "torlock.com",
    "torrentdownloads.me", "torrentdownloads.net",
    "eztv.re", "eztv.unblocked.lol", "eztv.it",
    "nyaa.si", "btscene.com", "limetorrents.info",
    "torrentz2.eu", "magnetdl.com", "seedpeer.me",
    "torrentproject.com", "torrenthunt.com", "kickasstorrents.com",
    "btdb.org", "bitsnoop.com", "torrents.me",

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

# Magnet links are not a file‑type but a URI scheme – we’ll pick them up with a regex.
MAGNET_RE = re.compile(r"magnet:\?[^\"'<> ]+", re.IGNORECASE)

USER_AGENTS = [
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edge/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Safari/605.1.15",
]

DEFAULT_SAFESEARCH   = "off"          # safe‑search OFF by default (wide open)
DEFAULT_EXTRA_KEYWORDS = ""         # extra “download OR install …” clause OFF
DEFAULT_MAX_RESULTS   = 60          # default number of distinct URLs returned


# ----------------------------------------------------------------------
# Helper utilities
# ----------------------------------------------------------------------
def rand_ua() -> str:
    """Pick a random User‑Agent string."""
    return random.choice(USER_AGENTS)


def clean_url(url: str) -> str:
    """Normalise a URL – strip fragment/query and percent‑decode."""
    parsed = urlparse(url)
    cleaned = parsed._replace(fragment="", query="").geturl()
    return unquote(cleaned)


def is_download_url(url: str, extensions: set) -> bool:
    """True if the URL ends with a known extension **or** is a magnet link."""
    if url.lower().startswith("magnet:"):
        return True
    return any(urlparse(url).path.lower().endswith(ext) for ext in extensions)


def build_query(
    term: str,
    sites: list | None = None,
    extensions: list | None = None,
    extra_keywords: str = DEFAULT_EXTRA_KEYWORDS,
) -> str:
    """
    Assemble a DuckDuckGo / Google query.

    • ``term``           – the software / media name you typed.
    • ``sites``          – optional ``site:example.com`` constraints.
    • ``extensions``     – optional ``filetype:mp4`` constraints.
    • ``extra_keywords`` – free‑text words such as “download”.  Empty → omitted.
    """
    parts = [term]

    if extra_keywords:
        parts.append(extra_keywords)

    if sites:
        parts.append("(" + " OR ".join(f"site:{s}" for s in sites) + ")")

    if extensions:
        parts.append("(" + " OR ".join(f"filetype:{e.lstrip('.')}" for e in extensions) + ")")

    return " ".join(parts)


def dedupe_results(results: list[dict]) -> list[dict]:
    """Remove duplicate URLs while preserving the first occurrence."""
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
    """DuckDuckGo text search (backend can be “auto”, “html”, “lite”, “bing”)."""
    if not _HAS_DDGS:
        raise RuntimeError("DuckDuckGo search library not available")
    with DDGS() as ddgs:
        raw = ddgs.text(
            query,
            max_results=max_results,
            safesearch=safesearch,
            backend=backend,
        )
    return list(raw)


def google_search_wrapper(query: str, max_results: int = DEFAULT_MAX_RESULTS) -> list[dict]:
    """
    Google search via ``googlesearch‑python``.
    The wrapper automatically adapts to the version that is installed
    (some versions use ``num=``, newer ones use ``num_results=``).
    """
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
        raise RuntimeError("Google search wrapper cannot determine correct argument name")

    if "stop" in params:
        kwargs["stop"] = max_results

    urls = google_search(query, **kwargs)
    return [{"title": "", "href": u} for u in urls]


# ----------------------------------------------------------------------
# Optional landing‑page scraping (to pull real download / magnet URLs)
# ----------------------------------------------------------------------
if _HAS_REQUESTS and _HAS_BS4:
    _EXT_RE = re.compile(
        r"https?://[^\s'\"<>]+(?:{exts})".format(
            exts="|".join(map(re.escape, DEFAULT_EXTENSIONS))
        ),
        re.IGNORECASE,
    )

    def extract_download_links(page_url: str, extensions: set) -> set[str]:
        """
        Fetch *page_url* and return a set of direct‑download URLs **and**
        magnet: links.
        """
        try:
            resp = requests.get(
                page_url,
                headers={"User-Agent": rand_ua()},
                timeout=12,
                verify=False,                # many download pages have self‑signed certs
            )
            resp.raise_for_status()
        except Exception:
            return set()

        # Fast regex scan for known extensions
        found = {
            m.group(0)
            for m in _EXT_RE.finditer(resp.text)
            if is_download_url(m.group(0), extensions)
        }

        # Magnet links are not captured by the above regex – pull them explicitly.
        found.update(m.group(0) for m in MAGNET_RE.finditer(resp.text))

        # Fallback – parse <a href> links with BeautifulSoup
        soup = BeautifulSoup(resp.text, "html.parser")
        for a in soup.find_all("a", href=True):
            href = urljoin(page_url, a["href"])
            if is_download_url(href, extensions):
                found.add(href)

        return {clean_url(u) for u in found}
else:
    # Stub – returns empty set when we cannot scrape.
    def extract_download_links(page_url: str, extensions: set) -> set[str]:
        return set()


# ----------------------------------------------------------------------
# Scoring – tiny heuristic that pushes real download / torrent links up
# ----------------------------------------------------------------------
def score_result(item: dict, site_whitelist: set, ext_set: set) -> int:
    """
    Higher score = more likely to be the file you actually want.
    Magnet links get a small extra boost because they usually point
    directly to the torrent containing the media.
    """
    score = 0
    href = item.get("href", "")
    title = item.get("title", "").lower()
    domain = urlparse(href).netloc.lower()

    if any(domain.endswith(w) for w in site_whitelist):
        score += 8                     # we prefer site‑agnostic results, but still keep a boost

    if is_download_url(href, ext_set):
        # 5 for a proper extension, 8 for a magnet link (extra +3)
        score += 8 if href.lower().startswith("magnet:") else 5

    # Boost for obvious media‑related words in the title
    for kw in (
        "download", "torrent", "magnet", "mp3", "flac", "wav",
        "movie", "film", "episode", "season", "track", "album",
    ):
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
    """
    Try DuckDuckGo first, then Google (if installed). Stop when we have
    enough distinct results.
    """
    raw = []

    # ----- DuckDuckGo (always attempted) -----
    try:
        if verbose:
            print("🔎 DuckDuckGo …")
        duck = ddg_search(query, max_results=max_results,
                          safesearch=safesearch, backend=backend)
        raw.extend(duck)
        if len(dedupe_results(raw)) >= max_results:
            return dedupe_results(raw)[:max_results]
    except Exception as exc:
        if verbose:
            print(f"⚠️ DuckDuckGo failed: {exc}")

    # ----- Google fallback (optional) -----
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
    """
    Full workflow:

    1️⃣ Build (maybe restrictive) query.
    2️⃣ Run DuckDuckGo → Google.
    3️⃣ If *no* results and we were restrictive → retry a broader query.
    4️⃣ Optional parallel scraping for direct download / magnet URLs.
    5️⃣ Score, sort, and return the final list.
    """
    if extensions is None:
        extensions = DEFAULT_EXTENSIONS
    ext_set = {e.lower() for e in extensions}
    site_set = {s.lower() for s in sites} if sites else set()

    # --------------------------------------------------------------
    # 1️⃣ First (maybe restrictive) query
    # --------------------------------------------------------------
    query = build_query(
        term, sites=sites, extensions=extensions, extra_keywords=extra_keywords
    )
    if verbose:
        print(f"🛠️  Query → {query}")

    results = _run_engine_search(query, max_results, safesearch, backend, verbose)

    # --------------------------------------------------------------
    # 2️⃣ Fallback – drop whitelist / extra keywords if we got nothing
    # --------------------------------------------------------------
    if not results and (sites or extra_keywords):
        if verbose:
            print(
                "⚡ No hits – trying a broader query (no site filter, no extra keywords)…"
            )
        query = build_query(term, sites=None, extensions=extensions, extra_keywords="")
        results = _run_engine_search(query, max_results, safesearch, backend, verbose)

    if not results:
        return []      # still empty → give up

    # --------------------------------------------------------------
    # 3️⃣ Optional scraping for *real* download / magnet URLs
    # --------------------------------------------------------------
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
                        print(f"⚠️ Scrape error for {src.get('href')}: {exc}")
                    continue
                if links:
                    extra_links[src["href"]] = links

        # Turn every discovered direct URL into a synthetic result record
        for src_url, urls in extra_links.items():
            for dl in urls:
                pseudo = {
                    "title": f"Direct download from {urlparse(dl).netloc}",
                    "href": dl,
                    "source": src_url,
                }
                results.append(pseudo)

        results = dedupe_results(results)

    # --------------------------------------------------------------
    # 4️⃣ Score & sort (higher = more likely a real media / torrent link)
    # --------------------------------------------------------------
    scored = [(r, score_result(r, site_set, ext_set)) for r in results]
    scored.sort(key=lambda pair: pair[1], reverse=True)
    return [item for item, _ in scored]


# ----------------------------------------------------------------------
# Output formatters
# ----------------------------------------------------------------------
def format_as_text(results: list[dict]) -> str:
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
    return json.dumps(results, indent=2, ensure_ascii=False)


def format_as_csv(results: list[dict]) -> str:
    """CSV via the csv module – guarantees proper quoting."""
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
# CLI handling
# ----------------------------------------------------------------------
def parse_cli() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Wide‑open search for software, audio, video, torrent links."
    )
    # ``term`` is optional – if omitted we go into interactive mode.
    parser.add_argument(
        "term",
        nargs="*",
        help="Search term (e.g. 'Daft Punk Get Lucky'). "
             "If omitted the script will ask you interactively.",
    )
    parser.add_argument(
        "-s",
        "--sites",
        default=",".join(DEFAULT_SITES),
        help="Comma‑separated whitelist of sites (default = huge built‑in list).",
    )
    parser.add_argument(
        "-e",
        "--extensions",
        default=",".join(DEFAULT_EXTENSIONS),
        help="Comma‑separated list of file extensions (e.g. .mp3,.mp4,.torrent).",
    )
    parser.add_argument(
        "-n",
        "--max",
        type=int,
        default=DEFAULT_MAX_RESULTS,
        help="Maximum number of distinct results to return (default 60).",
    )
    parser.add_argument(
        "-c",
        "--no-scrape",
        action="store_true",
        help="Skip the extra page‑scraping step (much faster).",
    )
    parser.add_argument(
        "-t",
        "--threads",
        type=int,
        default=8,
        help="Number of worker threads for scraping (default 8).",
    )
    parser.add_argument(
        "-o",
        "--output",
        choices=["text", "json", "csv"],
        default="text",
        help="Output format (default plain text).",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Show progress messages and engine‑fallback information.",
    )
    parser.add_argument(
        "--enable-safe-search",
        action="store_true",
        help="Turn safe‑search ON (default OFF).",
    )
    parser.add_argument(
        "--extra-keywords",
        action="store_true",
        help="Add the default download/install keywords to the query.",
    )
    parser.add_argument(
        "--no-restrict",
        dest="no_restrict",
        action="store_true",
        help="Do NOT restrict the search to the built‑in site whitelist.",
    )
    parser.add_argument(
        "--backend",
        choices=["auto", "html", "lite", "bing"],
        default="auto",
        help="DuckDuckGo backend to use (default auto; html is most reliable).",
    )
    parser.add_argument(
        "--version",
        action="version",
        version="linkfinder 1.0",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_cli()

    # --------------------------------------------------------------
    # Interactive mode – ask for a query if none was supplied
    # --------------------------------------------------------------
    if not args.term:
        # Simple interactive prompt
        term = input("\n🔎 Enter search query (or press ENTER to quit): ").strip()
        if not term:
            print("❌ No query entered – exiting.")
            sys.exit(0)
        # Optionally ask for a custom list of extensions (press ENTER for defaults)
        ext_input = input(
            "🔧 Enter comma‑separated extensions (or press ENTER for defaults): "
        ).strip()
        if ext_input:
            extensions = [e.strip() for e in ext_input.split(",") if e.strip()]
        else:
            extensions = None   # keep script defaults
        # Ask whether the user wants to limit the search to the whitelist
        restrict = input("❓ Search the whole web (no whitelist) ? [Y/n]: ").strip().lower()
        no_restrict = (restrict == "" or restrict.startswith("y"))
        # Ask about the number of results (default 200)
        max_input = input("🔢 How many results (default 200): ").strip()
        max_results = int(max_input) if max_input.isdigit() else 200

        # Overwrite the parsed arguments with the interactive choices
        args.term = [term]
        if extensions is not None:
            args.extensions = ",".join(extensions)
        args.no_restrict = no_restrict
        args.max = max_results
        # Apply the “best‑results” defaults automatically
        args.backend = "html"
        args.extra_keywords = True
        args.verbose = True
        # No need for scraping in this quick demo – you can keep it on if you want
        # args.no_scrape = False   # keep default (scraping enabled)
        print("\n🚀 Running search with the following options:")
        print(f"   Query            : {term}")
        print(f"   Extensions       : {args.extensions}")
        print(f"   No‑restrict     : {args.no_restrict}")
        print(f"   Max results      : {args.max}")
        print(f"   Backend          : {args.backend}")
        print(f"   Extra keywords   : {args.extra_keywords}")
        print("")
    else:
        # If the user supplied a term on the command line we just join it.
        term = " ".join(args.term)

    # --------------------------------------------------------------
    # Normalise the arguments for the core search
    # --------------------------------------------------------------
    # Sites – either the massive whitelist or none (if --no-restrict)
    if args.no_restrict:
        sites = None
    else:
        sites = [s.strip() for s in args.sites.split(",") if s.strip()]

    # Extensions – already a comma‑separated string from CLI or interactive mode
    extensions = [e.strip() for e in args.extensions.split(",") if e.strip()]

    # Extra‑keyword clause – only added if you asked for it
    extra_kw = DEFAULT_EXTRA_KEYWORDS if args.extra_keywords else ""

    # Safe‑search mode
    safesearch = "moderate" if args.enable_safe_search else "off"

    if args.verbose:
        print(f"🔎 Term            : {term}")
        print(f"⚙️  Sites           : {'<none>' if sites is None else ', '.join(sites)}")
        print(f"📦 Extensions      : {', '.join(extensions)}")
        print(f"🔑 Extra keywords : {'<none>' if not extra_kw else extra_kw}")
        print(f"🛡️  Safe‑search    : {safesearch}")
        print(f"🔧 DuckDuckGo backend : {args.backend}")

    # --------------------------------------------------------------
    # Run the actual search
    # --------------------------------------------------------------
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

    # --------------------------------------------------------------
    # Print / export the results
    # --------------------------------------------------------------
    if args.output == "text":
        print(format_as_text(results))
    elif args.output == "json":
        print(format_as_json(results))
    else:   # csv
        print(format_as_csv(results))


if __name__ == "__main__":
    # Suppress noisy SSL warnings when ``verify=False`` is used in scraping.
    if _HAS_REQUESTS:
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    main()
