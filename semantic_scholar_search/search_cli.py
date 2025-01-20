import argparse
from datetime import datetime
import logging
import os

from semantic_scholar_search.base.search import search_papers
from semantic_scholar_search.base.download import Downloader
from semantic_scholar_search.base.database import SearchDatabase


def setup_logging(session_id):
    # Create logs directory if it doesn't exist
    os.makedirs("logs", exist_ok=True)

    # Configure logging with a more structured format
    log_file = f"logs/search_{session_id}.log"

    # Get the root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    # Clear any existing handlers
    root_logger.handlers.clear()

    # Create and configure handlers
    file_handler = logging.FileHandler(log_file)
    stream_handler = logging.StreamHandler()

    # Create formatter with aligned and colored output
    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)-8s] [%(name)-30s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # Add formatter to handlers
    file_handler.setFormatter(formatter)
    stream_handler.setFormatter(formatter)

    # Add handlers to root logger
    root_logger.addHandler(file_handler)
    root_logger.addHandler(stream_handler)

    # Create and return logger for this module
    logger = logging.getLogger(__name__)
    return logging.LoggerAdapter(logger, {"session_id": session_id})


def log_section(logger, title: str, width: int = 100):
    """Helper function to create consistent section headers"""
    padding = (width - len(title) - 2) // 2  # -2 for the spaces around title
    return logger.info("=" * padding + f" {title} " + "=" * padding)


def log_subsection(logger, title: str, width: int = 100):
    """Helper function to create consistent subsection headers"""
    padding = (width - len(title) - 2) // 2
    return logger.info("-" * padding + f" {title} " + "-" * padding)


def main():
    parser = argparse.ArgumentParser(description="Search papers on Semantic Scholar")
    parser.add_argument("query", type=str, help="Search query")
    parser.add_argument(
        "--bulk",
        action="store_true",
        help="Download up to 1000 papers (default: False). When bulk is True, the limit is ignored and the sorting is not based on relevance.",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=1,
        help="Maximum number of pages to download (default: 10). The max_pages parameter is used only when bulk is False.",
    )
    parser.add_argument(
        "--max-results-per-page",
        type=int,
        default=10,
        help="Number of results per page (default: 10). The limit parameter is used only when bulk is False.",
    )
    parser.add_argument(
        "--sort",
        type=str,
        default="citationCount:desc",
        help="Sort results by criteria (default: citationCount:desc). The sort parameter is used only when bulk is True.",
        choices=[
            "citationCount:desc",
            "relevance:desc",
            "publicationDate:desc",
            "publicationDate:asc",
        ],
    )
    parser.add_argument(
        "--min-citation-count",
        type=int,
        default=0,
        help="Minimum citation count (default: 0)",
    )
    parser.add_argument(
        "--fields-of-study",
        type=str,
        nargs="+",
        help="Restrict results to specific fields of study (e.g., 'Computer Science' 'Medicine')",
    )
    parser.add_argument(
        "--publication-date-or-year",
        type=str,
        help="Restrict results to papers published within a date range (format: YYYY-MM-DD:YYYY-MM-DD, YYYY-MM:YYYY-MM, or YYYY:YYYY)",
    )

    args = parser.parse_args()

    if args.max_results_per_page > 1000:
        raise ValueError(
            "Error: The limit must be less than or equal to 100 EVEN WHEN bulk is True to be compatible with the Semantic Scholar search API."
        )

    session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    logger = setup_logging(session_id)

    log_section(logger, "Search Session Started")
    logger.info("Query Parameters:")
    logger.info(f"├── Query: {args.query}")
    logger.info(f"├── Bulk Mode: {args.bulk}")
    logger.info(f"├── Max Pages: {args.max_pages}")
    logger.info(f"├── Results Per Page: {args.max_results_per_page}")
    logger.info(f"├── Sort: {args.sort}")
    logger.info(f"├── Min Citation Count: {args.min_citation_count}")
    logger.info(f"├── Fields of Study: {args.fields_of_study or 'None'}")
    logger.info(f"└── Publication Date/Year: {args.publication_date_or_year or 'None'}")

    if args.bulk:
        logger.warning("Bulk mode enabled: limit will be overridden to 1000")
    else:
        if args.sort != "relevance:desc":
            logger.warning("Non-bulk mode: sort will be overridden to relevance:desc")

    db = SearchDatabase()
    search_id = db.record_search(
        session_id,
        args.query,
        args.max_pages,
        args.max_results_per_page,
        args.sort,
        args.min_citation_count,
        args.fields_of_study,
        args.publication_date_or_year,
    )

    log_section(logger, "Starting Paper Search")
    results = search_papers(
        args.query,
        bulk=args.bulk,
        max_pages=args.max_pages,
        max_results_per_page=args.max_results_per_page,
        sort=args.sort,
        min_citation_count=args.min_citation_count,
        fields_of_study=args.fields_of_study,
        publication_date_or_year=args.publication_date_or_year,
    )

    if not results:
        logger.info("No results found")
        return

    logger.info(f"Found {len(results)} papers")
    log_section(logger, "Finished Paper Search")

    downloader = Downloader(
        db,
        session_id,
        args.query,
        args.bulk,
        args.max_pages,
        args.max_results_per_page,
        args.sort,
        args.min_citation_count,
        args.fields_of_study,
        args.publication_date_or_year,
    )
    downloader.create_directory()

    log_section(logger, "Starting Paper Downloads")

    for i, paper in enumerate(results, 1):
        log_subsection(logger, f"Paper {i}/{len(results)}")
        logger.info("Paper Details:")
        logger.info(f"├── Title: {paper.title}")
        if paper.authors:
            authors = [author.name for author in paper.authors]
            logger.info(f"├── Authors: {', '.join(authors)}")
        logger.info(f"├── Year: {paper.year or 'N/A'}")
        logger.info(f"└── URL: {paper.url or 'N/A'}")

        downloader.download_paper(paper, search_id)
        log_subsection(logger, f"Completed Paper {i}/{len(results)}")

    # Get final statistics
    stats = downloader.get_download_stats()

    log_section(logger, "Download Summary")
    
    # Print summary statistics with tree structure
    logger.info("Download Statistics:")
    logger.info(f"├── Total Papers Found: {stats['total']}")
    success_count = stats['open_access_success'] + stats['arxiv_success']
    logger.info(f"├── Successfully Downloaded: {success_count}")
    logger.info(f"│   ├── Via Open Access: {stats['open_access_success']}")
    logger.info(f"│   └── Via ArXiv: {stats['arxiv_success']}")
    logger.info(f"├── Failed Downloads: {stats['failed']}")
    
    success_rate = (success_count / stats["total"] * 100) if stats["total"] > 0 else 0
    logger.info(f"└── Success Rate: {success_rate:.1f}%")

    log_section(logger, "Search Session Completed")


if __name__ == "__main__":
    main()
