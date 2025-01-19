"""
Download papers from Semantic Scholar
"""

import os
import requests
import logging


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
        Download paper based on its source (ArXiv or openAccessPdf)

        Args:
            paper: Paper object from semanticscholar
            search_id: ID of the current search session

        Returns:
            str: Path to the downloaded file or None if download failed
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
            # Case 1: ArXiv paper
            if paper.journal and paper.journal.name == "ArXiv":
                arxiv_id = (
                    paper.journal.volume.replace("abs/", "")
                    if paper.journal.volume
                    else None
                )
                if arxiv_id:
                    arxiv_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"
                    self.logger.info(f"Downloading from ArXiv: {arxiv_url}")
                    response = requests.get(arxiv_url)
                    response.raise_for_status()

                    with open(base_filename, "wb") as f:
                        f.write(response.content)
                    download_success = True

            # Case 2: Open Access PDF
            elif paper.isOpenAccess and paper.openAccessPdf is not None:
                pdf_url = (
                    paper.openAccessPdf.url
                    if hasattr(paper.openAccessPdf, "url")
                    else paper.openAccessPdf.get("url")
                )
                self.logger.info(f"Downloading from: {pdf_url}")
                response = requests.get(pdf_url)
                response.raise_for_status()

                with open(base_filename, "wb") as f:
                    f.write(response.content)
                download_success = True

            else:
                self.logger.info(f"No downloadable PDF available for: {paper.title}")
                base_filename = None

        except Exception as e:
            self.logger.error(f"Error downloading paper: {str(e)}")
            base_filename = None
            download_success = False

        # Record the paper and its download status in the database
        self.db.record_paper(search_id, paper, base_filename, download_success)

        return base_filename
