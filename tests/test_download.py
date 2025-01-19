import pytest
from unittest.mock import Mock, patch, mock_open
import os
from semantic_scholar_search.download import Downloader

@pytest.fixture
def mock_db():
    return Mock()

@pytest.fixture
def downloader(mock_db):
    return Downloader(
        db=mock_db,
        session_id="test_session",
        search_query="machine learning",
        bulk=False,
        max_pages=5,
        max_results_per_page=10,
        sort="relevance",
        min_citation_count=0,
        output_dir="test_papers"
    )

def test_init(downloader):
    assert downloader.session_id == "test_session"
    assert downloader.search_query == "machine learning"
    assert downloader.bulk is False
    assert downloader.max_pages == 5
    assert downloader.max_results_per_page == 10
    assert downloader.sort == "relevance:desc"
    assert downloader.min_citation_count == 0
    assert downloader.output_dir == "test_papers"

def test_init_bulk():
    mock_db = Mock()
    downloader = Downloader(
        db=mock_db,
        session_id="test_session",
        search_query="machine learning",
        bulk=True,
        max_pages=5,
        max_results_per_page=10,
        sort="citationCount:desc",
        min_citation_count=0
    )
    assert downloader.max_results_per_page == 1000
    assert downloader.sort == "citationCount:desc"

def test_get_directory(downloader):
    expected_path = os.path.join(
        "test_papers",
        "machine_learning",
        "top_5_pages_10_per_page_sort_by_relevance_desc_min_citation_count_0",
        "test_session"
    )
    assert downloader.get_directory() == expected_path

@patch('os.makedirs')
def test_create_directory(mock_makedirs, downloader):
    downloader.create_directory()
    mock_makedirs.assert_called_once_with(downloader.get_directory(), exist_ok=True)

@patch('os.path.exists')
@patch('requests.get')
def test_download_paper_arxiv(mock_get, mock_exists, downloader):
    # Setup
    mock_exists.return_value = True
    mock_response = Mock()
    mock_response.content = b"fake pdf content"
    mock_get.return_value = mock_response
    
    # Create a more complete mock paper
    mock_paper = Mock(spec=[
        'title', 'externalIds', 'arxivId', 'url', 
        'isOpenAccess', 'openAccessPdf', 'journal'
    ])
    
    # Set all possible properties that might identify an ArXiv paper
    mock_paper.title = "Test Paper"
    mock_paper.externalIds = {
        'ArXiv': '1234.5678',
        'DOI': '10.1234/example'
    }
    mock_paper.arxivId = '1234.5678'
    mock_paper.url = 'https://arxiv.org/abs/1234.5678'
    mock_paper.isOpenAccess = True
    mock_paper.openAccessPdf = {'url': 'https://arxiv.org/pdf/1234.5678.pdf'}
    
    # Set up journal
    mock_journal = Mock()
    mock_journal.name = 'arXiv'
    mock_journal.volume = 'abs/1234.5678'
    mock_paper.journal = mock_journal
    
    # Test with mocked file operations
    with patch('builtins.open', mock_open()) as mock_file:
        result = downloader.download_paper(mock_paper, "test_search")
    
    expected_path = os.path.join(downloader.get_directory(), "Test Paper.pdf")
    assert result == expected_path
    mock_get.assert_called_once_with("https://arxiv.org/pdf/1234.5678.pdf")
    downloader.db.record_paper.assert_called_once_with("test_search", mock_paper, expected_path, True)

@patch('os.path.exists')
@patch('requests.get')
def test_download_paper_open_access(mock_get, mock_exists, downloader):
    # Setup
    mock_exists.return_value = True
    mock_response = Mock()
    mock_response.content = b"fake pdf content"
    mock_get.return_value = mock_response
    
    mock_paper = Mock()
    mock_paper.title = "Test Paper"
    mock_paper.journal = None
    mock_paper.isOpenAccess = True
    mock_paper.openAccessPdf = {'url': 'https://example.com/paper.pdf'}
    
    # Test with mocked file operations
    with patch('builtins.open', mock_open()) as mock_file:
        result = downloader.download_paper(mock_paper, "test_search")
    
    expected_path = os.path.join(downloader.get_directory(), "Test Paper.pdf")
    assert result == expected_path
    mock_get.assert_called_once_with("https://example.com/paper.pdf")
    downloader.db.record_paper.assert_called_once_with("test_search", mock_paper, expected_path, True)

@patch('os.path.exists')
def test_download_paper_no_pdf(mock_exists, downloader):
    mock_exists.return_value = True
    
    mock_paper = Mock()
    mock_paper.title = "Test Paper"
    mock_paper.journal = None
    mock_paper.isOpenAccess = False
    
    result = downloader.download_paper(mock_paper, "test_search")
    
    assert result is None
    downloader.db.record_paper.assert_called_once_with("test_search", mock_paper, None, False)

@patch('os.path.exists')
def test_download_paper_directory_not_exists(mock_exists, downloader):
    mock_exists.return_value = False
    
    mock_paper = Mock()
    with pytest.raises(ValueError):
        downloader.download_paper(mock_paper, "test_search") 