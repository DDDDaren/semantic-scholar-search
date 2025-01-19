"""
Download papers from Semantic Scholar
"""

import os
import requests
import logging
import webbrowser
import time
from urllib.parse import urlparse
import re
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

    def download_paper(self, paper, search_id):
        """
        Download paper based on its source (Semantic Scholar PDF or ArXiv)
        """
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
        try:
            # First try to get PDF from Semantic Scholar's openAccessPdf
            if paper.isOpenAccess and paper.openAccessPdf is not None:
                pdf_url = (
                    paper.openAccessPdf.url
                    if hasattr(paper.openAccessPdf, "url")
                    else paper.openAccessPdf.get("url")
                )
                if pdf_url:
                    download_success = self._handle_pdf_download(pdf_url, base_filename, paper)
                    if download_success:
                        return base_filename

            # If direct PDF fails, try Semantic Reader
            if not download_success:
                download_success = self._try_semantic_reader(paper.url, base_filename, paper)
                if download_success:
                    return base_filename

            # If both above fail and it's an ArXiv paper, try ArXiv as last resort
            if not download_success and paper.journal and paper.journal.name == "ArXiv":
                arxiv_id = (
                    paper.journal.volume.replace("abs/", "")
                    if paper.journal.volume
                    else None
                )
                if arxiv_id:
                    download_success = self._handle_arxiv_download(arxiv_id, base_filename, paper)

            if not download_success:
                self.logger.info(f"No downloadable PDF available for: {paper.title}")
                base_filename = None

        except Exception as e:
            self.logger.error(f"Error downloading paper: {str(e)}")
            base_filename = None
            download_success = False

        # Record the paper and its download status in the database
        self.db.record_paper(search_id, paper, base_filename, download_success)

        return base_filename

    def _handle_arxiv_download(self, arxiv_id, base_filename, paper, max_retries=3):
        """Handle ArXiv paper downloads with CAPTCHA detection"""
        arxiv_id = arxiv_id.strip()
        if not arxiv_id.endswith('.pdf'):
            arxiv_id = arxiv_id + '.pdf'
        
        arxiv_url = f"https://arxiv.org/pdf/{arxiv_id}"
        abs_url = f"https://arxiv.org/abs/{arxiv_id.replace('.pdf', '')}"
        robots_url = "https://arxiv.org/human-verification"
        
        self.logger.info(f"Downloading from ArXiv: {arxiv_url}")
        
        headers = self._get_browser_headers()
        
        for attempt in range(max_retries):
            try:
                with requests.Session() as session:
                    # First try to get the PDF directly
                    pdf_response = session.get(arxiv_url, headers=headers, allow_redirects=True, timeout=10)
                    
                    # If we get HTML instead of PDF, we're probably being blocked
                    if 'text/html' in pdf_response.headers.get('Content-Type', ''):
                        self.logger.warning("Access blocked. Opening verification page...")
                        
                        # First try the direct verification URL
                        webbrowser.open(robots_url)
                        time.sleep(1)  # Short wait to see if the page loads
                        
                        # If that fails, try the abstract page as fallback
                        webbrowser.open(abs_url)
                        
                        # Prompt user to complete verification
                        input("Please complete the verification in your browser and press Enter to continue...")
                        
                        # Wait a bit before retrying
                        time.sleep(2)
                        continue
                    
                    # If we get here and response is OK, we should have a PDF
                    pdf_response.raise_for_status()
                    
                    if pdf_response.headers.get('Content-Type', '').startswith('application/pdf'):
                        with open(base_filename, "wb") as f:
                            f.write(pdf_response.content)
                        return True
                    else:
                        self.logger.warning(f"Received non-PDF response for: {paper.title}")
                        
                        # As a last resort, open the abstract page
                        self.logger.warning("Opening abstract page for manual download...")
                        webbrowser.open(abs_url)
                        input("Please try downloading the PDF manually from the abstract page. Press Enter when done...")
                        
                        # Check if the file was downloaded
                        if os.path.exists(base_filename):
                            return True
                        return False
                
            except requests.exceptions.RequestException as e:
                if attempt == max_retries - 1:
                    self.logger.error(f"Failed to download from ArXiv after {max_retries} attempts: {str(e)}")
                    return False
                time.sleep(2)  # Wait before retrying
        
        self.logger.warning(f"ArXiv download failed for: {paper.title}")
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
                response = session.get(pdf_url, headers=headers, allow_redirects=True, timeout=10)
                response.raise_for_status()
                content_type = response.headers.get('Content-Type', '').lower()

                if 'application/pdf' in content_type or response.content.startswith(b'%PDF-'):
                    content = response.content
                else:
                    # Second attempt: Try with .pdf extension if not already a PDF URL
                    if not pdf_url.lower().endswith('.pdf'):
                        pdf_url_alt = pdf_url.rstrip('/') + '.pdf'
                        self.logger.info(f"Trying alternative URL: {pdf_url_alt}")
                        response = session.get(pdf_url_alt, headers=headers, allow_redirects=True, timeout=10)
                        response.raise_for_status()
                        content = response.content
                    else:
                        content = response.content

                # Final verification of PDF content
                if content.startswith(b'%PDF-'):
                    with open(base_filename, "wb") as f:
                        f.write(content)
                    return True
                else:
                    # If automated download fails, try manual download
                    self.logger.warning(f"Automated download failed for: {paper.title}")
                    self.logger.info("Opening paper URL for manual download...")
                    webbrowser.open(paper.url)  # Open the Semantic Scholar page
                    input("Please try downloading the PDF manually. Once downloaded, press Enter to continue...")
                    
                    # Check if file exists in downloads directory
                    if os.path.exists(base_filename):
                        return True
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
                    self.logger.error(f"Access denied. This might require authentication")
                self.logger.error(f"Please try accessing the paper manually via: {paper.url}")
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
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Look for Semantic Reader button/link
                reader_link = None
                
                # Try different possible selectors
                for link in soup.find_all('a'):
                    if 'semantic reader' in link.text.lower():
                        reader_link = link.get('href')
                        break
                
                if not reader_link:
                    # Try to find it in script tags (might be in JavaScript data)
                    for script in soup.find_all('script'):
                        if script.string and 'semanticScholar' in script.string:
                            # Look for reader URL pattern
                            match = re.search(r'https://[^"\']*reader[^"\']*', script.string)
                            if match:
                                reader_link = match.group(0)
                                break

                if reader_link:
                    if not reader_link.startswith('http'):
                        reader_link = 'https://www.semanticscholar.org' + reader_link
                    
                    self.logger.info(f"Found Semantic Reader link: {reader_link}")
                    
                    # Get the reader page
                    reader_response = session.get(reader_link, headers=headers, timeout=10)
                    reader_response.raise_for_status()
                    
                    # Parse the reader page to find the PDF URL
                    reader_soup = BeautifulSoup(reader_response.text, 'html.parser')
                    
                    # Look for PDF URL in various places
                    pdf_url = None
                    
                    # Try to find in meta tags
                    for meta in reader_soup.find_all('meta'):
                        if meta.get('property') == 'og:pdf' or meta.get('name') == 'citation_pdf_url':
                            pdf_url = meta.get('content')
                            break
                    
                    # Try to find in script tags
                    if not pdf_url:
                        for script in reader_soup.find_all('script'):
                            if script.string and 'pdfUrl' in script.string:
                                match = re.search(r'pdfUrl["\']?\s*:\s*["\']([^"\']+)', script.string)
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
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Cache-Control': 'max-age=0',
        }
