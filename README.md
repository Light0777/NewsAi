# Morning News Intelligence

A Python-based tool for fetching, processing, and delivering morning news digests.

## Features

- RSS/Atom feed fetching via `feedparser`
- HTML content extraction via `requests` + `beautifulsoup4`
- Templated output via `Jinja2`
- Environment-based configuration via `python-dotenv`
- History tracking with local storage

## Project Structure

```
news_ai/
├── fetchers/          # Feed fetching modules
├── processors/        # Content processing and summarization
├── templates/         # Jinja2 templates for output
├── storage/           # Local persistence layer
│   └── history/       # Fetch history records
├── config/            # Application configuration
├── tests/             # Test suite
├── main.py            # Entry point
├── requirements.txt   # Python dependencies
└── README.md          # This file
```

## Setup

### Prerequisites

- Python 3.12 or later
- `venv` (included with Python 3.12+)

### Installation

```powershell
# Clone or navigate to the project root
cd news_ai

# Create a virtual environment
python -m venv .venv

# Activate it
# Windows:
.venv\Scripts\Activate.ps1
# Linux / macOS:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Configuration

Copy `.env.example` to `.env` and set your preferences:

```ini
# News sources (comma-separated RSS/Atom URLs)
NEWS_SOURCES=https://feeds.bbci.co.uk/news/rss.xml,https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml

# Output format (html / text / json)
OUTPUT_FORMAT=html

# Max articles per source
MAX_ARTICLES=10
```

## Usage

```powershell
python main.py
```

Run tests:

```powershell
python -m pytest tests/
```

## Dependencies

| Package          | Purpose                    |
|------------------|----------------------------|
| `requests`       | HTTP requests              |
| `feedparser`     | RSS / Atom feed parsing    |
| `beautifulsoup4` | HTML content extraction    |
| `Jinja2`         | Template rendering         |
| `python-dotenv`  | Environment variable load  |

## License

MIT
