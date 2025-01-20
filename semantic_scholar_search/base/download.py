"""
Download papers from Semantic Scholar
"""

import os
import logging
import time
from typing import Optional, Tuple, Dict, Any

import arxiv  # type: ignore
import re
import requests


class Downloader:
    def __init__(
        self,
        db: Any,
        session_id: str,
        search_query: str,
        bulk: bool,
        max_pages: int,
        max_results_per_page: int,
        sort: str,
        min_citation_count: int,
        fields_of_study: Optional[list] = None,
        publication_date_or_year: Optional[str] = None,
        output_dir: str = "papers",
        logger: Optional[logging.Logger] = None,
    ):
        self.db = db
        self.search_query = search_query
        self.bulk = bulk
        self.max_pages = max_pages
        self.max_results_per_page = 1000 if bulk else max_results_per_page
        self.sort = sort if bulk else "relevance:desc"
        self.session_id = session_id
        self.min_citation_count = min_citation_count
        self.output_dir = output_dir
        self.fields_of_study = fields_of_study
        self.publication_date_or_year = publication_date_or_year
        self.logger = logger or logging.LoggerAdapter(
            logging.getLogger(__name__), {"session_id": session_id}
        )

        # Initialize download tracking
        self.download_stats = {
            "total": 0,
            "open_access_success": 0,
            "arxiv_success": 0,
            "direct_url_success": 0,
            "failed": 0,
        }

        # Initialize clients
        self.last_arxiv_request_time = 0
        self.ARXIV_RATE_LIMIT = 3
        self.arxiv_client = arxiv.Client()
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            }
        )

    def download_paper(
        self, paper: Any, search_id: str
    ) -> Tuple[Optional[str], Optional[str]]:
        """Download paper using available methods."""
        self.download_stats["total"] += 1

        if not os.path.exists(self.get_directory()):
            raise ValueError(f"Directory {self.get_directory()} does not exist.")

        initial_filename = self._get_safe_filename(paper.title)
        base_filename: Optional[str] = initial_filename
        download_success = False
        download_method: Optional[str] = None

        try:
            # Try ArXiv download
            if arxiv_id := self._extract_arxiv_id(paper):
                download_success, filename = self._try_arxiv_download(
                    arxiv_id, initial_filename
                )
                if download_success and filename:
                    self.download_stats["arxiv_success"] += 1
                    download_method = "arxiv"
                    base_filename = filename

            # Try open access download
            if not download_success and base_filename:
                download_success, filename = self._try_open_access_download(
                    paper, initial_filename
                )
                if download_success and filename:
                    self.download_stats["open_access_success"] += 1
                    download_method = "open_access"
                    base_filename = filename

            # Try direct URL download
            if not download_success and base_filename:
                download_success, filename = self._try_direct_download(
                    paper, initial_filename
                )
                if download_success and filename:
                    self.download_stats["direct_url_success"] += 1
                    download_method = "direct_url"
                    base_filename = filename

            if not download_success:
                self.logger.info(
                    f"No download sources available for paper: {paper.title}"
                )
                base_filename = None
                self.download_stats["failed"] += 1

        except Exception as e:
            self.logger.error(f"Error processing paper: {str(e)}")
            base_filename = None
            download_success = False
            self.download_stats["failed"] += 1

        self.db.record_paper(search_id, paper, base_filename, download_success)
        return base_filename, download_method

    def get_directory(self) -> str:
        """Get the output directory path."""
        safe_query = (
            "".join(c for c in self.search_query if c.isalnum() or c in (" ", "-", "_"))
            .rstrip()
            .replace(" ", "_")
        )

        sort_by = "_".join(self.sort.split(":"))
        fos_path = (
            f"_fos_{'_'.join(self.fields_of_study)}" if self.fields_of_study else ""
        )
        date_path = (
            f"_date_{self.publication_date_or_year.replace(':', '_to_')}"
            if self.publication_date_or_year
            else ""
        )

        return os.path.join(
            self.output_dir,
            safe_query,
            f"top_{self.max_pages}_pages_{self.max_results_per_page}_per_page_sort_by_{sort_by}_min_citation_count_{self.min_citation_count}{fos_path}{date_path}",
            self.session_id,
        )

    def create_directory(self):
        """Create the output directory."""
        os.makedirs(self.get_directory(), exist_ok=True)

    def get_download_stats(self) -> Dict[str, int]:
        """Return the current download statistics."""
        return self.download_stats

    def _try_arxiv_download(
        self, arxiv_id: str, base_filename: str
    ) -> Tuple[bool, Optional[str]]:
        """Try to download paper from ArXiv."""
        try:
            self._respect_arxiv_rate_limit()
            arxiv_paper = next(
                self.arxiv_client.results(arxiv.Search(id_list=[arxiv_id]))
            )
            pdf_filename = f"{base_filename}.pdf"
            arxiv_paper.download_pdf(filename=pdf_filename)
            self.logger.info(f"Successfully downloaded ArXiv PDF: {pdf_filename}")
            return True, pdf_filename
        except Exception as e:
            self.logger.warning(f"Failed to download ArXiv paper: {str(e)}")
            return False, None

    def _try_open_access_download(
        self, paper: Any, base_filename: str
    ) -> Tuple[bool, Optional[str]]:
        """Try to download open access paper."""
        if not (paper.isOpenAccess and paper.openAccessPdf):
            return False, None

        pdf_url = (
            paper.openAccessPdf.url
            if hasattr(paper.openAccessPdf, "url")
            else paper.openAccessPdf.get("url")
        )
        if not pdf_url:
            self.logger.warning("Open access paper has no PDF URL")
            return False, None

        pdf_filename = f"{base_filename}.pdf"
        self.logger.info(f"Attempting to download open access PDF from: {pdf_url}")
        if self._download_file(pdf_url, pdf_filename):
            self.logger.info(f"Successfully downloaded open access PDF: {pdf_filename}")
            return True, pdf_filename
        return False, None

    def _try_direct_download(
        self, paper: Any, base_filename: str
    ) -> Tuple[bool, Optional[str]]:
        """Try to download paper from direct URL."""
        if not paper.url:
            return False, None

        pdf_filename = f"{base_filename}.pdf"
        self.logger.info(f"Attempting direct download from: {paper.url}")
        if self._download_file(paper.url, pdf_filename):
            self.logger.info(
                f"Successfully downloaded PDF from direct URL: {pdf_filename}"
            )
            return True, pdf_filename
        return False, None

    def _extract_arxiv_id(self, paper: Any) -> Optional[str]:
        """Extract ArXiv ID from paper metadata."""
        # Check if it's a direct ArXiv paper
        if (
            hasattr(paper, "journal")
            and paper.journal
            and paper.journal.name == "ArXiv"
        ):
            return (
                paper.journal.volume.replace("abs/", "")
                if paper.journal.volume
                else None
            )

        def extract_from_url(url: str) -> Optional[str]:
            if not url:
                return None
            patterns = [
                r"arxiv\.org/(?:abs|pdf)/([0-9]+\.[0-9]+(?:v[0-9]+)?)",
                r"arxiv\.org/(?:abs|pdf)/([a-z\-]+/[0-9]+(?:v[0-9]+)?)",
            ]
            for pattern in patterns:
                if match := re.search(pattern, url):
                    return match.group(1)
            return None

        # Check various sources for ArXiv ID
        sources = [
            lambda: extract_from_url(paper.url),
            lambda: paper.externalIds.get("ArXiv")
            if hasattr(paper, "externalIds") and paper.externalIds
            else None,
            lambda: next(
                (
                    extract_from_url(v.url)
                    for v in paper.alternateVersions
                    if hasattr(v, "url")
                ),
                None,
            )
            if hasattr(paper, "alternateVersions")
            else None,
        ]

        for source in sources:
            if arxiv_id := source():
                return arxiv_id
        return None

    def _download_file(self, url: str, filename: str) -> bool:
        """Download a file from URL and save it."""
        try:
            response = self.session.get(url)
            if response.status_code == 200 and response.headers.get(
                "content-type", ""
            ).lower().startswith("application/pdf"):
                with open(filename, "wb") as f:
                    f.write(response.content)
                return True
            return False
        except Exception as e:
            self.logger.warning(f"Error downloading file: {str(e)}")
            return False

    def _get_safe_filename(self, title: str) -> str:
        """Generate a safe filename from paper title."""
        safe_title = "".join(
            c for c in title if c.isalnum() or c in (" ", "-", "_")
        ).rstrip()
        return os.path.join(self.get_directory(), safe_title)

    def _respect_arxiv_rate_limit(self):
        """Ensure we respect arXiv's rate limit."""
        current_time = time.time()
        time_since_last_request = current_time - self.last_arxiv_request_time
        if time_since_last_request < self.ARXIV_RATE_LIMIT:
            sleep_time = self.ARXIV_RATE_LIMIT - time_since_last_request
            self.logger.info(
                f"Waiting {sleep_time:.2f} seconds for ArXiv rate limit..."
            )
            time.sleep(sleep_time)
        self.last_arxiv_request_time = time.time()
