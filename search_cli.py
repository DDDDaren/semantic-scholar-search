import argparse
from datetime import datetime
import warnings
import logging
import os

from semantic_scholar_search.search import search_papers
from semantic_scholar_search.download import Downloader
from semantic_scholar_search.database import SearchDatabase

def setup_logging(session_id):
    # Create logs directory if it doesn't exist
    os.makedirs('logs', exist_ok=True)
    
    # Configure logging
    log_file = f'logs/search_{session_id}.log'
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()  # This will still show output in console
        ]
    )
    return logging.getLogger(__name__)

def main():
    parser = argparse.ArgumentParser(description='Search papers on Semantic Scholar')
    parser.add_argument('query', type=str, help='Search query')
    parser.add_argument('--bulk', action='store_true', help='Download up to 1000 papers (default: False). When bulk is True, the limit is ignored and the sorting is not based on relevance.')
    parser.add_argument('--max-pages', type=int, default=1, help='Maximum number of pages to download (default: 10). The max_pages parameter is used only when bulk is False.')
    parser.add_argument('--max-results-per-page', type=int, default=10, help='Number of results per page (default: 10). The limit parameter is used only when bulk is False.')
    parser.add_argument('--sort', type=str, default="citationCount:desc", help='Sort results by citation count (default: desc). The sort parameter is used only when bulk is True.')
    parser.add_argument('--min-citation-count', type=int, default=0, help='Minimum citation count (default: 0)')
    
    args = parser.parse_args()

    if args.max_results_per_page > 1000:
        raise ValueError("Error: The limit must be less than or equal to 100 EVEN WHEN bulk is True to be compatible with the Semantic Scholar search API.")

    session_id = datetime.now().strftime('%Y%m%d_%H%M%S')
    logger = setup_logging(session_id)

    if args.bulk:
        logger.warning("When bulk is True, the `limit` will be overridden to 1000 within the search_papers function and the provided max-results-per-page argument will be ignored.")
    else:
        if args.sort != "relevance:desc":
            logger.warning("When bulk is False, the sort will be overridden to relevance:desc within the search_papers function and the provided sort argument will be ignored.")
    
    db = SearchDatabase()
    search_id = db.record_search(args.query, args.max_pages, args.max_results_per_page, session_id, args.sort, args.min_citation_count)
    
    results = search_papers(args.query, bulk=args.bulk, max_pages=args.max_pages, max_results_per_page=args.max_results_per_page, sort=args.sort, min_citation_count=args.min_citation_count)
    
    if not results:
        logger.info("No results found")
        return

    downloader = Downloader(db, session_id, args.query, args.bulk, args.max_pages, args.max_results_per_page, args.sort, args.min_citation_count)
    downloader.create_directory()
    
    for paper in results:
        paper_info = []
        paper_info.append(f"Title: {paper.title}")
        if paper.authors:
            authors = [author.name for author in paper.authors]
            paper_info.append(f"Authors: {', '.join(authors)}")
        paper_info.append(f"Year: {paper.year or 'N/A'}")
        paper_info.append(f"Paper URL: {paper.url or 'N/A'}")
        
        logger.info("\n".join(paper_info))
        
        downloader.download_paper(paper, search_id)
        logger.info("-" * 80)

if __name__ == "__main__":
    main()