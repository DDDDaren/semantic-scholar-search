# Semantic Scholar Search

A Python-based command-line tool for searching and downloading academic papers from Semantic Scholar.

## Features

- Search papers using Semantic Scholar's API and download PDFs automatically from ArXiv and open access sources
    - Configurable search parameters (pages, results per page, minimum citations, sort by citation count or relevance)
- Track search history and paper downloads in SQLite database

## Installation

### Prerequisites
- Python 3.10 or higher

### For Users
1. Install directly from GitHub:
   ```bash
   pip install git+https://github.com/DDDDaren/semantic-scholar-searchh.git
   ```

   Or install from source:
   ```bash
   git clone https://github.com/DDDDaren/semantic-scholar-searchh.git
   cd semantic-scholar-searchh
   pip install .
   ```

### For Developers

#### Option 1: Using direnv (recommended)
1. Install direnv:
   ```bash
   # On macOS
   brew install direnv

   # On Ubuntu/Debian
   sudo apt-get install direnv

   # On Windows (using Chocolatey)
   choco install direnv
   ```

2. Add direnv hook to your shell:
   ```bash
   # For zsh (add to ~/.zshrc):
   eval "$(direnv hook zsh)"

   # For bash (add to ~/.bashrc):
   eval "$(direnv hook bash)"
   ```

3. Clone and enter the repository:
   ```bash
   git clone https://github.com/DDDDaren/semantic-scholar-searchh.git
   cd semantic-scholar-searchh
   direnv allow
   ```

#### Option 2: Manual Setup
1. Create and activate virtual environment:
   ```bash
   python -m venv .venv
   
   # On Unix/macOS
   source .venv/bin/activate
   
   # On Windows
   .venv\Scripts\activate
   ```

2. Install dependencies:
   ```bash
   pip install poetry
   poetry install
   ```

## Usage

### Basic Search

```bash
poetry run semantic-search "machine learning"
```

### Advanced Search Options

```bash
# Search with minimum citation count
poetry run semantic-search "deep learning" --min-citation-count 100

# Bulk download (up to 100,00 papers)
poetry run semantic-search "neural networks" --bulk

# Customize number of pages and results per page
poetry run semantic-search "reinforcement learning" --max-pages 5 --max-results-per-page 20

# Sort by citation count (descending)
poetry run semantic-search "transformer models" --sort "citationCount:desc"
```

### Output

The tool will:
1. Create a directory structure based on your search query
2. Download available PDFs from ArXiv or open access sources
3. Display paper information including:
   - Title
   - Authors
   - Year
   - Paper URL
4. Track all searches and downloads in a local SQLite database

## Directory Structure

```
papers/
└── your_search_query/
    └── top_N_pages_M_per_page_sort_by_X_min_citation_count_Y/
        └── session_timestamp/
            └── paper_title.pdf
```

## Database

All searches and paper information are stored in `search_history.db` with the following schema:

- `searches`: Records search queries and parameters
- `papers`: Stores paper metadata and download status

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.
