import pytest
from unittest.mock import Mock, patch, call
import logging
import os
from datetime import datetime

from semantic_scholar_search.search_cli import setup_logging, main

@pytest.fixture
def mock_paper():
    paper = Mock()
    paper.title = "Test Paper"
    # Create proper author mocks with name attributes
    author1 = Mock()
    author1.name = "John Doe"
    author2 = Mock()
    author2.name = "Jane Smith"
    paper.authors = [author1, author2]
    paper.year = 2023
    paper.url = "https://example.com/paper"
    return paper

@pytest.fixture
def mock_args():
    args = Mock()
    args.query = "test query"
    args.bulk = False
    args.max_pages = 1
    args.max_results_per_page = 10
    args.sort = "citationCount:desc"
    args.min_citation_count = 0
    args.fields_of_study = None
    args.publication_date_or_year = None
    return args

@pytest.fixture(autouse=True)
def reset_logging():
    """Reset logging before each test"""
    logging.root.handlers = []
    yield

def test_setup_logging():
    session_id = "20240118_123456"
    logger = setup_logging(session_id)
    
    assert isinstance(logger, logging.LoggerAdapter)
    assert logger.extra == {"session_id": session_id}
    assert os.path.exists("logs")
    
    # Find the FileHandler for our log file
    log_file = f"logs/search_{session_id}.log"
    assert os.path.exists(log_file)
    
    if os.path.exists("logs") and not os.listdir("logs"):
        os.rmdir("logs")

@patch('semantic_scholar_search.search_cli.argparse.ArgumentParser')
def test_main_with_no_results(mock_parser):
    # Create specific args for this test
    args = Mock()
    args.query = "machine learning basics"
    args.bulk = False
    args.max_pages = 2
    args.max_results_per_page = 20
    args.sort = "citationCount:desc"
    args.min_citation_count = 5
    args.fields_of_study = None
    args.publication_date_or_year = None
    
    mock_parser.return_value.parse_args.return_value = args
    
    with patch('semantic_scholar_search.search_cli.search_papers') as mock_search, \
         patch('semantic_scholar_search.search_cli.SearchDatabase') as mock_db, \
         patch('semantic_scholar_search.search_cli.setup_logging') as mock_logging:
        
        mock_search.return_value = []
        mock_logger = Mock()
        mock_logging.return_value = mock_logger
        
        main()
        
        mock_search.assert_called_once_with(
            args.query,
            bulk=args.bulk,
            max_pages=args.max_pages,
            max_results_per_page=args.max_results_per_page,
            sort=args.sort,
            min_citation_count=args.min_citation_count,
            fields_of_study=args.fields_of_study,
            publication_date_or_year=args.publication_date_or_year
        )

@patch('semantic_scholar_search.search_cli.argparse.ArgumentParser')
def test_main_with_results(mock_parser, mock_args, mock_paper):
    mock_parser.return_value.parse_args.return_value = mock_args
    
    with patch('semantic_scholar_search.search_cli.search_papers') as mock_search, \
         patch('semantic_scholar_search.search_cli.SearchDatabase') as mock_db, \
         patch('semantic_scholar_search.search_cli.setup_logging') as mock_logging, \
         patch('semantic_scholar_search.search_cli.Downloader') as mock_downloader:
        
        mock_search.return_value = [mock_paper]
        mock_logger = Mock()
        mock_logging.return_value = mock_logger
        mock_downloader_instance = Mock()
        mock_downloader.return_value = mock_downloader_instance
        
        main()
        
        # Verify search was performed
        mock_search.assert_called_once_with(
            mock_args.query,
            bulk=mock_args.bulk,
            max_pages=mock_args.max_pages,
            max_results_per_page=mock_args.max_results_per_page,
            sort=mock_args.sort,
            min_citation_count=mock_args.min_citation_count,
            fields_of_study=mock_args.fields_of_study,
            publication_date_or_year=mock_args.publication_date_or_year
        )
        
        # Verify paper information was logged
        assert mock_logger.info.call_count >= 4
        mock_logger.info.assert_any_call("Found 1 papers")
        mock_logger.info.assert_any_call("Title: Test Paper")
        mock_logger.info.assert_any_call("Authors: John Doe, Jane Smith")
        mock_logger.info.assert_any_call("Year: 2023")
        
        # Verify downloader was used
        mock_downloader_instance.create_directory.assert_called_once()
        mock_downloader_instance.download_paper.assert_called_once_with(mock_paper, mock_db().record_search())

def test_main_with_invalid_max_results(mock_args):
    mock_args.max_results_per_page = 1001
    
    with patch('semantic_scholar_search.search_cli.argparse.ArgumentParser') as mock_parser:
        mock_parser.return_value.parse_args.return_value = mock_args
        
        with pytest.raises(ValueError) as exc_info:
            main()
        
        assert "The limit must be less than or equal to 100" in str(exc_info.value)

@patch('semantic_scholar_search.search_cli.argparse.ArgumentParser')
def test_main_bulk_mode_warning(mock_parser, mock_args):
    mock_args.bulk = True
    mock_parser.return_value.parse_args.return_value = mock_args
    
    with patch('semantic_scholar_search.search_cli.search_papers') as mock_search, \
         patch('semantic_scholar_search.search_cli.SearchDatabase'), \
         patch('semantic_scholar_search.search_cli.setup_logging') as mock_logging:
        
        mock_search.return_value = []
        mock_logger = Mock()
        mock_logging.return_value = mock_logger
        
        main()
        
        mock_logger.warning.assert_called_with("Bulk mode enabled: limit will be overridden to 1000")

@patch('semantic_scholar_search.search_cli.argparse.ArgumentParser')
def test_main_non_bulk_sort_warning(mock_parser, mock_args):
    mock_args.bulk = False
    mock_args.sort = "something:else"
    mock_parser.return_value.parse_args.return_value = mock_args
    
    with patch('semantic_scholar_search.search_cli.search_papers') as mock_search, \
         patch('semantic_scholar_search.search_cli.SearchDatabase'), \
         patch('semantic_scholar_search.search_cli.setup_logging') as mock_logging:
        
        mock_search.return_value = []
        mock_logger = Mock()
        mock_logging.return_value = mock_logger
        
        main()
        
        mock_logger.warning.assert_called_with("Non-bulk mode: sort will be overridden to relevance:desc")

def test_setup_logging_file_creation():
    session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    logger = setup_logging(session_id)
    
    log_file = f"logs/search_{session_id}.log"
    assert os.path.exists("logs")
    assert os.path.exists(log_file)
    
    # Clean up test log file
    os.remove(log_file)
    if not os.listdir("logs"):
        os.rmdir("logs")

@patch('semantic_scholar_search.search_cli.argparse.ArgumentParser')
def test_main_with_date_range(mock_parser):
    # Create specific args for this test
    args = Mock()
    args.query = "deep learning advances"
    args.bulk = True
    args.max_pages = 3
    args.max_results_per_page = 30
    args.sort = "publicationDate:desc"
    args.min_citation_count = 10
    args.fields_of_study = ["Computer Science", "Artificial Intelligence"]
    args.publication_date_or_year = "2020:2023"
    
    mock_parser.return_value.parse_args.return_value = args
    
    with patch('semantic_scholar_search.search_cli.search_papers') as mock_search, \
         patch('semantic_scholar_search.search_cli.SearchDatabase'), \
         patch('semantic_scholar_search.search_cli.setup_logging') as mock_logging:
        
        mock_search.return_value = []
        mock_logger = Mock()
        mock_logging.return_value = mock_logger
        
        main()
        
        mock_search.assert_called_once_with(
            args.query,
            bulk=args.bulk,
            max_pages=args.max_pages,
            max_results_per_page=args.max_results_per_page,
            sort=args.sort,
            min_citation_count=args.min_citation_count,
            fields_of_study=args.fields_of_study,
            publication_date_or_year=args.publication_date_or_year
        )
