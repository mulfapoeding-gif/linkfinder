<<<<<<< HEAD
﻿# LinkFinder 🔍
=======
# Create a comprehensive README.md
@"
# LinkFinder 🔍
>>>>>>> cbc6706262efa81f85e95a389d3fcd8feeb31f06

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)

**LinkFinder** is a powerful tool for searching and discovering download links, torrents, and media files across the web.

## ✨ Features

- **Multi-engine search**: DuckDuckGo with Google fallback
- **Async scraping**: Extract direct download links and magnet URIs
- **Intelligent scoring**: Relevance-based ranking of results
- **Multiple output formats**: Text, JSON, CSV
- **Interactive mode**: User-friendly guided search experience
- **File extension filtering**: Search for specific file types
- **Site whitelist**: Configurable site filtering
- **Page scraping**: Extract real download URLs from landing pages

## 🚀 Installation

### Quick Install
<<<<<<< HEAD
\\\ash
pip install linkfinder
\\\

### From Source
\\\ash
git clone https://github.com/mulfapoeding-gif/linkfinder.git
cd linkfinder
pip install -e .
\\\
=======
\`\`\`bash
pip install linkfinder
\`\`\`

### From Source
\`\`\`bash
git clone https://github.com/mulfapoeding-gif/linkfinder.git
cd linkfinder
pip install -e .
\`\`\`
>>>>>>> cbc6706262efa81f85e95a389d3fcd8feeb31f06

## 📖 Usage

### Command Line

#### Basic Search
<<<<<<< HEAD
\\\ash
=======
\`\`\`bash
>>>>>>> cbc6706262efa81f85e95a389d3fcd8feeb31f06
# Search for software
linkfinder \"Ubuntu 22.04\"

# Search for media files
linkfinder \"Daftpunk Get Lucky\" -e .mp3,.flac

# Interactive mode (recommended for beginners)
linkfinder
<<<<<<< HEAD
\\\

#### Advanced Options
\\\ash
=======
\`\`\`

#### Advanced Options
\`\`\`bash
>>>>>>> cbc6706262efa81f85e95a389d3fcd8feeb31f06
# Custom extensions
linkfinder \"Movie Name\" -e .mp4,.mkv,.avi

# Disable site restrictions (search entire web)
linkfinder \"Game Name\" --no-restrict

# Skip page scraping (faster results)
linkfinder \"Music\" --no-scrape

# JSON output
linkfinder \"Software\" --output json

# More results
linkfinder \"Ubuntu\" -n 100
<<<<<<< HEAD
\\\

### Python API
\\\python
=======
\`\`\`

### Python API
\`\`\`python
>>>>>>> cbc6706262efa81f85e95a389d3fcd8feeb31f06
from linkfinder import run_search

# Search for Ubuntu ISOs
results = run_search(
    term=\"Ubuntu 22.04\",
    extensions=[\".iso\", \".torrent\"],
    max_results=50
)

for result in results[:10]:
    print(f\"{result['title']}: {result['href']}\")
<<<<<<< HEAD
\\\

## 📋 Command Line Options

- 	erms: Search terms (multiple words supported)
- -e, --extensions: File extensions to search for (.mp3, .mp4, .torrent, etc.)
- -s, --sites: Comma-separated list of sites to search
- -n, --max: Maximum number of results (default: 60)
- -o, --output: Output format (text/json/csv)
- --no-restrict: Search entire web without site restrictions
- --no-scrape: Skip page scraping for direct links
- -v, --verbose: Enable verbose logging
- --enable-safe-search: Turn on safe search
- --extra-keywords: Add download/install keywords
- --backend: DuckDuckGo backend (auto/html/lite/bing)
- --threads: Number of worker threads for scraping
- --version: Show version information
=======
\`\`\`

## 📋 Command Line Options

- `terms`: Search terms (multiple words supported)
- `-e, --extensions`: File extensions to search for (.mp3, .mp4, .torrent, etc.)
- `-s, --sites`: Comma-separated list of sites to search
- `-n, --max`: Maximum number of results (default: 60)
- `-o, --output`: Output format (text/json/csv)
- `--no-restrict`: Search entire web without site restrictions
- `--no-scrape`: Skip page scraping for direct links
- `-v, --verbose`: Enable verbose logging
- `--enable-safe-search`: Turn on safe search
- `--extra-keywords`: Add download/install keywords
- `--backend`: DuckDuckGo backend (auto/html/lite/bing)
- `--threads`: Number of worker threads for scraping
- `--version`: Show version information
>>>>>>> cbc6706262efa81f85e95a389d3fcd8feeb31f06

## 🏗️ Supported File Types

### Archives
.zip, .tar.gz, .tar.bz2, .tgz, .gz, .bz2, .exe, .msi, .dmg, .pkg, .deb, .rpm, .apk, .aar, .whl, .torrent

### Audio
.mp3, .flac, .wav, .aac, .m4a, .ogg, .wma, .alac, .opus

### Video
.mp4, .mkv, .avi, .mov, .wmv, .flv, .webm, .mpeg, .mpg, .m4v, .3gp, .ts, .vob

## 🔧 Configuration

The tool includes a built-in whitelist of popular sites by default:
- **Software Repositories**: GitHub, GitLab, SourceForge, PyPI, npm
- **Media Platforms**: YouTube, Vimeo, SoundCloud, Bandcamp
- **File Hosts**: MediaFire, Mega.nz, Zippyshare, RapidGator
- **Torrent Trackers**: The Pirate Bay, 1337x, RARBG, YTS

<<<<<<< HEAD
You can customize this list using the --sites parameter or disable restrictions with --no-restrict.
=======
You can customize this list using the `--sites` parameter or disable restrictions with `--no-restrict`.
>>>>>>> cbc6706262efa81f85e95a389d3fcd8feeb31f06

## ⚖️ Legal & Ethical Use

**Important**: This tool includes optional access to sites that may host copyrighted content. Users are **solely responsible** for:

1. **Legal compliance**: Ensuring usage complies with local laws
2. **Site terms**: Respecting each site's terms of service
3. **Ethical behavior**: Using the tool responsibly

**Recommended Usage**:
- Use for legitimate software downloads
- Respect copyright and intellectual property
- Follow website terms of service
- Implement reasonable rate limiting

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- DuckDuckGo Search API
- Google Search (fallback)
- BeautifulSoup4
- aiohttp for async operations
- Open source community

---

**⚖️ Disclaimer**: This software is provided for educational and research purposes. Users are responsible for ensuring their usage complies with all applicable laws and regulations.
<<<<<<< HEAD
=======
"@ | Out-File -FilePath "README.md" -Encoding UTF8
>>>>>>> cbc6706262efa81f85e95a389d3fcd8feeb31f06
