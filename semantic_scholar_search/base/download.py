"""
Download papers from Semantic Scholar
"""

import os
import requests
import logging
import re
import time
from bs4 import BeautifulSoup


class Downloader:
    def __init__(
        self,
        db,
        session_id,
        search_query,
        bulk,
        max_pages,
        max_results_per_page,
        sort,
        min_citation_count,
        fields_of_study=None,
        publication_date_or_year=None,
        output_dir="papers",
        logger=None,
    ):
        self.db = db
        self.search_query = search_query
        self.bulk = bulk
        self.max_pages = max_pages
        self.max_results_per_page = max_results_per_page
        if bulk:
            self.max_results_per_page = 1000
            self.sort = sort
        else:
            self.max_results_per_page = max_results_per_page
            self.sort = "relevance:desc"
        self.session_id = session_id
        self.min_citation_count = min_citation_count
        self.output_dir = output_dir
        self.fields_of_study = fields_of_study
        self.publication_date_or_year = publication_date_or_year

        # Use the passed logger or create a new one with session context
        if logger:
            self.logger = logger
        else:
            base_logger = logging.getLogger(__name__)
            self.logger = logging.LoggerAdapter(base_logger, {"session_id": session_id})

        self.download_stats = {
            "total": 0,
            "open_access_success": 0,
            "semantic_reader_success": 0,
            "arxiv_success": 0,
            "failed": 0,
        }

        self.last_arxiv_request_time = 0  # Track last arXiv request time
        self.ARXIV_RATE_LIMIT = 3  # Minimum seconds between requests

    def get_directory(self):
        safe_query = "".join(
            c for c in self.search_query if c.isalnum() or c in (" ", "-", "_")
        ).rstrip()
        safe_query = safe_query.replace(" ", "_")
        sort_by = "_".join(self.sort.split(":"))

        # Add fields of study to directory path if specified
        fos_path = ""
        if self.fields_of_study:
            fos_path = f"_fos_{'_'.join(self.fields_of_study)}"

        # Add publication date to directory path if specified
        date_path = ""
        if self.publication_date_or_year:
            date_path = f"_date_{self.publication_date_or_year.replace(':', '_to_')}"

        return os.path.join(
            self.output_dir,
            safe_query,
            f"top_{str(self.max_pages)}_pages_{str(self.max_results_per_page)}_per_page_sort_by_{sort_by}_min_citation_count_{str(self.min_citation_count)}{fos_path}{date_path}",
            self.session_id,
        )

    def create_directory(self):
        os.makedirs(self.get_directory(), exist_ok=True)

    def _respect_arxiv_rate_limit(self):
        """Ensure we respect arXiv's rate limit of 1 request per 3 seconds"""
        current_time = time.time()
        time_since_last_request = current_time - self.last_arxiv_request_time
        if time_since_last_request < self.ARXIV_RATE_LIMIT:
            sleep_time = self.ARXIV_RATE_LIMIT - time_since_last_request
            self.logger.info(
                f"Waiting {sleep_time:.2f} seconds to respect arXiv rate limit..."
            )
            time.sleep(sleep_time)
        self.last_arxiv_request_time = time.time()

    def download_paper(self, paper, search_id):
        """
        Download paper based on its source (Semantic Scholar PDF or ArXiv)
        Priority order:
        1. Open Access PDF
        2. Semantic Reader
        3. ArXiv (with rate limiting)
        """
        self.download_stats["total"] += 1

        if not os.path.exists(self.get_directory()):
            raise ValueError(
                f"Directory {self.get_directory()} does not exist. Please run the create_directory method first."
            )

        # Generate base filename from paper title
        safe_title = "".join(
            c for c in paper.title if c.isalnum() or c in (" ", "-", "_")
        ).rstrip()
        base_filename = os.path.join(self.get_directory(), safe_title + ".pdf")

        download_success = False
        download_method = None
        try:
            # First try: Open access papers
            if paper.isOpenAccess and paper.openAccessPdf:
                pdf_url = (
                    paper.openAccessPdf.url
                    if hasattr(paper.openAccessPdf, "url")
                    else paper.openAccessPdf.get("url")
                )
                if pdf_url:
                    self.logger.info(
                        f"Attempting to download open access PDF from: {pdf_url}"
                    )
                    response = requests.get(
                        pdf_url, headers=self._get_browser_headers()
                    )
                    if response.status_code == 200 and response.headers.get(
                        "content-type", ""
                    ).lower().startswith("application/pdf"):
                        with open(base_filename, "wb") as f:
                            f.write(response.content)
                        download_success = True
                        download_method = "open_access"
                        self.download_stats["open_access_success"] += 1
                        self.logger.info("Successfully downloaded open access PDF")
                    else:
                        self.logger.warning(
                            f"Failed to download open access PDF. Status code: {response.status_code}, Content-Type: {response.headers.get('content-type')}"
                        )
                else:
                    self.logger.warning("Open access paper has no PDF URL")
            else:
                self.logger.info("Paper is not open access or has no PDF link")

            # Second try: Semantic Reader
            if not download_success and hasattr(paper, "url"):
                self.logger.info("Attempting Semantic Reader download")
                download_success = self._try_semantic_reader(
                    paper.url, base_filename, paper
                )
                if download_success:
                    download_method = "semantic_reader"
                    self.download_stats["semantic_reader_success"] += 1
                    self.logger.info("Successfully downloaded via Semantic Reader")
                else:
                    self.logger.info("Semantic Reader download failed")

            # Third try: ArXiv papers (with rate limiting)
            if not download_success and hasattr(paper, "arxivId"):
                # Respect arXiv's rate limit
                self._respect_arxiv_rate_limit()

                # Instead of downloading directly, redirect to abstract page
                arxiv_id = paper.arxivId.strip()
                abstract_url = f"https://arxiv.org/abs/{arxiv_id}"
                pdf_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"

                self.logger.info("ArXiv paper found. Please access it via:")
                self.logger.info(f"Abstract page: {abstract_url}")
                self.logger.info(f"PDF download: {pdf_url}")

                # Record as success but don't download
                download_success = True
                download_method = "arxiv"
                self.download_stats["arxiv_success"] += 1

                # Create a text file with the arXiv links instead of downloading PDF
                txt_filename = base_filename.replace(".pdf", "_arxiv_links.txt")
                with open(txt_filename, "w") as f:
                    f.write(f"Title: {paper.title}\n")
                    f.write(f"ArXiv ID: {arxiv_id}\n")
                    f.write(f"Abstract page: {abstract_url}\n")
                    f.write(f"PDF download: {pdf_url}\n")

                base_filename = txt_filename  # Update filename for database recording
                self.logger.info("Created text file with arXiv links")
            else:
                self.logger.info("Paper is not from arXiv or missing arXiv ID")

            if not download_success:
                self.logger.warning(f"Could not download paper: {paper.title}")
                base_filename = None
                self.download_stats["failed"] += 1

        except Exception as e:
            self.logger.error(f"Error downloading paper: {str(e)}")
            base_filename = None
            download_success = False
            self.download_stats["failed"] += 1

        # Record the paper and its download status in the database
        self.db.record_paper(search_id, paper, base_filename, download_success)

        return base_filename, download_method

    def _handle_arxiv_download(self, arxiv_id, base_filename, paper):
        """Handle ArXiv paper downloads"""
        arxiv_id = arxiv_id.strip()
        if not arxiv_id.endswith(".pdf"):
            arxiv_id = arxiv_id + ".pdf"

        arxiv_url = f"https://arxiv.org/pdf/{arxiv_id}"
        self.logger.info(f"Downloading from ArXiv: {arxiv_url}")

        headers = self._get_browser_headers()

        try:
            with requests.Session() as session:
                response = session.get(
                    arxiv_url, headers=headers, allow_redirects=True, timeout=10
                )
                response.raise_for_status()

                if response.headers.get("Content-Type", "").startswith(
                    "application/pdf"
                ):
                    with open(base_filename, "wb") as f:
                        f.write(response.content)
                    return True
                else:
                    self.logger.warning(
                        f"ArXiv response was not a PDF for: {paper.title}"
                    )
                    return False

        except requests.exceptions.RequestException as e:
            self.logger.error(f"Failed to download from ArXiv: {str(e)}")
            return False

    def _handle_pdf_download(self, pdf_url, base_filename, paper):
        """Handle general PDF downloads"""
        # Clean and encode the URL properly
        pdf_url = requests.utils.requote_uri(pdf_url)
        self.logger.info(f"Attempting to download from: {pdf_url}")

        headers = self._get_browser_headers()

        # Create a session to handle cookies and redirects
        with requests.Session() as session:
            try:
                # First attempt: direct download
                response = session.get(
                    pdf_url, headers=headers, allow_redirects=True, timeout=10
                )
                response.raise_for_status()
                content_type = response.headers.get("Content-Type", "").lower()

                if "application/pdf" in content_type or response.content.startswith(
                    b"%PDF-"
                ):
                    content = response.content
                else:
                    # Second attempt: Try with .pdf extension if not already a PDF URL
                    if not pdf_url.lower().endswith(".pdf"):
                        pdf_url_alt = pdf_url.rstrip("/") + ".pdf"
                        self.logger.info(f"Trying alternative URL: {pdf_url_alt}")
                        response = session.get(
                            pdf_url_alt,
                            headers=headers,
                            allow_redirects=True,
                            timeout=10,
                        )
                        response.raise_for_status()
                        content = response.content
                    else:
                        content = response.content

                # Final verification of PDF content
                if content.startswith(b"%PDF-"):
                    with open(base_filename, "wb") as f:
                        f.write(content)
                    return True
                else:
                    self.logger.warning(
                        f"Response was not a valid PDF for: {paper.title}"
                    )
                    return False

            except requests.exceptions.Timeout:
                self.logger.error(f"Timeout while downloading from {pdf_url}")
                return False
            except requests.exceptions.HTTPError as e:
                if e.response.status_code == 404:
                    self.logger.error(f"PDF not found at {pdf_url}")
                elif e.response.status_code == 503:
                    self.logger.error(f"Service temporarily unavailable: {pdf_url}")
                elif e.response.status_code == 403:
                    self.logger.error(
                        "Access denied. This might require authentication"
                    )
                return False
            except Exception as e:
                self.logger.error(f"Error downloading paper: {str(e)}")
                return False

    def _try_semantic_reader(self, paper_url, base_filename, paper):
        """Try to download using Semantic Reader"""
        self.logger.info("Attempting to download via Semantic Reader...")

        headers = self._get_browser_headers()

        try:
            with requests.Session() as session:
                # Get the paper page
                response = session.get(paper_url, headers=headers, timeout=10)
                response.raise_for_status()

                # Parse the HTML
                soup = BeautifulSoup(response.text, "html.parser")

                # Look for Semantic Reader button/link
                reader_link = None

                # Try different possible selectors
                for link in soup.find_all("a"):
                    if "semantic reader" in link.text.lower():
                        reader_link = link.get("href")
                        break

                if not reader_link:
                    # Try to find it in script tags
                    for script in soup.find_all("script"):
                        if script.string and "semanticScholar" in script.string:
                            match = re.search(
                                r'https://[^"\']*reader[^"\']*', script.string
                            )
                            if match:
                                reader_link = match.group(0)
                                break

                if reader_link:
                    if not reader_link.startswith("http"):
                        reader_link = "https://www.semanticscholar.org" + reader_link

                    self.logger.info(f"Found Semantic Reader link: {reader_link}")

                    # Get the reader page
                    reader_response = session.get(
                        reader_link, headers=headers, timeout=10
                    )
                    reader_response.raise_for_status()

                    # Parse the reader page to find the PDF URL
                    reader_soup = BeautifulSoup(reader_response.text, "html.parser")

                    # Look for PDF URL in various places
                    pdf_url = None

                    # Try to find in meta tags
                    for meta in reader_soup.find_all("meta"):
                        if (
                            meta.get("property") == "og:pdf"
                            or meta.get("name") == "citation_pdf_url"
                        ):
                            pdf_url = meta.get("content")
                            break

                    # Try to find in script tags
                    if not pdf_url:
                        for script in reader_soup.find_all("script"):
                            if script.string and "pdfUrl" in script.string:
                                match = re.search(
                                    r'pdfUrl["\']?\s*:\s*["\']([^"\']+)', script.string
                                )
                                if match:
                                    pdf_url = match.group(1)
                                    break

                    if pdf_url:
                        self.logger.info(f"Found PDF URL in Semantic Reader: {pdf_url}")
                        return self._handle_pdf_download(pdf_url, base_filename, paper)

                    self.logger.warning("Could not find PDF URL in Semantic Reader")
                    return False

                self.logger.info("No Semantic Reader link found")
                return False

        except Exception as e:
            self.logger.error(f"Error trying Semantic Reader: {str(e)}")
            return False

    def _get_browser_headers(self):
        """Get common browser-like headers"""
        return {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Accept": "application/pdf,application/x-pdf,*/*",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
            "DNT": "1",
            "Upgrade-Insecure-Requests": "1",
        }

    def get_download_stats(self):
        """Return the current download statistics"""
        return self.download_stats
