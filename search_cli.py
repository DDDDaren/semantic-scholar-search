import argparse
from datetime import datetime
import logging
import os

from semantic_scholar_search.search import search_papers
from semantic_scholar_search.download import Downloader
from semantic_scholar_search.database import SearchDatabase

def setup_logging(session_id):
    # Create logs directory if it doesn't exist
    os.makedirs('logs', exist_ok=True)
    
    # Configure logging with a more structured format
    log_file = f'logs/search_{session_id}.log'
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] [%(name)s] [session=%(session_id)s] %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )
    logger = logging.getLogger(__name__)
    # Add session_id to logger adapter for consistent correlation
    return logging.LoggerAdapter(logger, {'session_id': session_id})

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

    logger.info("=== Search Session Started ===")
    logger.info(f"Query: {args.query}")
    logger.info(f"Parameters: bulk={args.bulk}, max_pages={args.max_pages}, "
               f"max_results_per_page={args.max_results_per_page}, sort={args.sort}, "
               f"min_citation_count={args.min_citation_count}")

    if args.bulk:
        logger.warning("Bulk mode enabled: limit will be overridden to 1000")
    else:
        if args.sort != "relevance:desc":
            logger.warning("Non-bulk mode: sort will be overridden to relevance:desc")
    
    db = SearchDatabase()
    search_id = db.record_search(session_id, args.query, args.max_pages, args.max_results_per_page, args.sort, args.min_citation_count)
    
    logger.info("=== Starting Paper Search ===")
    results = search_papers(args.query, bulk=args.bulk, max_pages=args.max_pages, 
                          max_results_per_page=args.max_results_per_page, 
                          sort=args.sort, min_citation_count=args.min_citation_count)
    
    if not results:
        logger.info("No results found")
        return

    logger.info(f"Found {len(results)} papers")
    
    downloader = Downloader(db, session_id, args.query, args.bulk, args.max_pages, 
                          args.max_results_per_page, args.sort, args.min_citation_count)
    downloader.create_directory()
    
    logger.info("=" * 40 + "Starting Paper Downloads" + "=" * 40)
    for i, paper in enumerate(results, 1):
        logger.info("-" * 40 + f"Downloading Paper {i}/{len(results)}" + "-" * 40)
        logger.info(f"Title: {paper.title}")
        if paper.authors:
            authors = [author.name for author in paper.authors]
            logger.info(f"Authors: {', '.join(authors)}")
        logger.info(f"Year: {paper.year or 'N/A'}")
        logger.info(f"URL: {paper.url or 'N/A'}")
        
        downloader.download_paper(paper, search_id)
        logger.info("-" * 40 + f"Downloaded Paper {i}/{len(results)}" + "-" * 40)
        
    logger.info("=" * 40 + "Search Session Completed" + "=" * 40)

if __name__ == "__main__":
    main()