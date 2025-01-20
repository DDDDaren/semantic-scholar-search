import pytest
from unittest.mock import Mock, patch, mock_open
import os
from semantic_scholar_search.base.download import Downloader
from unittest.mock import call

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
        sort="relevance:desc",
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
def test_download_paper_arxiv(mock_exists, downloader):
    mock_exists.return_value = True
    
    # Create a mock paper with proper ArXiv attributes
    mock_paper = Mock()
    mock_paper.title = "Test Paper"
    mock_paper.journal = Mock()
    mock_paper.journal.name = "ArXiv"  # Set as attribute instead of constructor
    mock_paper.journal.volume = "1234.5678"
    mock_paper.url = ""
    mock_paper.isOpenAccess = False
    mock_paper.openAccessPdf = None
    mock_paper.externalIds = {}
    mock_paper.alternateVersions = []

    # Mock arxiv client
    mock_arxiv_paper = Mock()
    mock_arxiv_paper.download_pdf = Mock()
    downloader.arxiv_client.results = Mock(return_value=iter([mock_arxiv_paper]))

    with patch('builtins.open', mock_open()):
        result, method = downloader.download_paper(mock_paper, "test_search")

    expected_path = os.path.join(downloader.get_directory(), "Test Paper.pdf")
    assert result == expected_path
    assert method == "arxiv"
    mock_arxiv_paper.download_pdf.assert_called_once_with(filename=expected_path)
    downloader.db.record_paper.assert_called_once_with("test_search", mock_paper, expected_path, True)

@patch('os.path.exists')
def test_download_paper_open_access(mock_exists, downloader):
    mock_exists.return_value = True
    
    # Create mock paper
    mock_paper = Mock()
    mock_paper.title = "Test Paper"
    mock_paper.journal = None
    mock_paper.url = ""  # Add empty string for url
    mock_paper.isOpenAccess = True
    mock_paper.openAccessPdf = Mock(url="https://example.com/paper.pdf")
    mock_paper.externalIds = {}
    mock_paper.alternateVersions = []

    # Mock requests session
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.headers = {'content-type': 'application/pdf'}
    mock_response.content = b"fake pdf content"
    downloader.session.get = Mock(return_value=mock_response)

    with patch('builtins.open', mock_open()) as mock_file:
        result, method = downloader.download_paper(mock_paper, "test_search")

    expected_path = os.path.join(downloader.get_directory(), "Test Paper.pdf")
    assert result == expected_path
    assert method == "open_access"
    downloader.session.get.assert_called_once_with("https://example.com/paper.pdf")
    mock_file().write.assert_called_once_with(b"fake pdf content")
    downloader.db.record_paper.assert_called_once_with("test_search", mock_paper, expected_path, True)

@patch('os.path.exists')
def test_download_paper_direct_url(mock_exists, downloader):
    mock_exists.return_value = True
    
    # Create mock paper
    mock_paper = Mock()
    mock_paper.title = "Test Paper"
    mock_paper.journal = None
    mock_paper.url = "https://example.com/direct.pdf"
    mock_paper.isOpenAccess = False
    mock_paper.openAccessPdf = None

    # Mock requests session
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.headers = {'content-type': 'application/pdf'}
    mock_response.content = b"fake pdf content"
    downloader.session.get = Mock(return_value=mock_response)

    with patch('builtins.open', mock_open()) as mock_file:
        result, method = downloader.download_paper(mock_paper, "test_search")

    expected_path = os.path.join(downloader.get_directory(), "Test Paper.pdf")
    assert result == expected_path
    assert method == "direct_url"
    downloader.session.get.assert_called_once_with("https://example.com/direct.pdf")
    mock_file().write.assert_called_once_with(b"fake pdf content")
    downloader.db.record_paper.assert_called_once_with("test_search", mock_paper, expected_path, True)

@patch('os.path.exists')
def test_download_paper_no_pdf(mock_exists, downloader):
    mock_exists.return_value = True
    
    mock_paper = Mock()
    mock_paper.title = "Test Paper"
    mock_paper.journal = None
    mock_paper.url = None
    mock_paper.isOpenAccess = False
    mock_paper.openAccessPdf = None
    
    result, method = downloader.download_paper(mock_paper, "test_search")
    
    assert result is None
    assert method is None
    downloader.db.record_paper.assert_called_once_with("test_search", mock_paper, None, False)

@patch('os.path.exists')
def test_download_paper_directory_not_exists(mock_exists, downloader):
    mock_exists.return_value = False
    
    mock_paper = Mock()
    with pytest.raises(ValueError):
        downloader.download_paper(mock_paper, "test_search")

def test_get_download_stats(downloader):
    stats = downloader.get_download_stats()
    assert stats == {
        'total': 0,
        'open_access_success': 0,
        'arxiv_success': 0,
        'direct_url_success': 0,
        'failed': 0
    }

@patch('time.time')
@patch('time.sleep')
def test_respect_arxiv_rate_limit(mock_sleep, mock_time, downloader):
    mock_time.side_effect = [10.0, 11.0]
    downloader.last_arxiv_request_time = 9.0
    
    downloader._respect_arxiv_rate_limit()
    
    mock_sleep.assert_called_once_with(2.0)

def test_extract_arxiv_id(downloader):
    # Test direct ArXiv paper
    paper1 = Mock()
    paper1.journal = Mock()
    paper1.journal.name = "ArXiv"  # Set as attribute instead of constructor
    paper1.journal.volume = "2101.12345"
    paper1.url = ""
    paper1.externalIds = {}
    paper1.alternateVersions = []
    assert downloader._extract_arxiv_id(paper1) == "2101.12345"

    # Test paper with ArXiv URL
    paper2 = Mock()
    paper2.journal = None
    paper2.url = "https://arxiv.org/abs/2101.12345"
    paper2.externalIds = {}
    paper2.alternateVersions = []
    assert downloader._extract_arxiv_id(paper2) == "2101.12345"

    # Test paper with ArXiv in externalIds
    paper3 = Mock()
    paper3.journal = None
    paper3.url = ""
    paper3.externalIds = {"ArXiv": "2101.12345"}
    paper3.alternateVersions = []
    assert downloader._extract_arxiv_id(paper3) == "2101.12345"

    # Test paper with no ArXiv information
    paper4 = Mock()
    paper4.journal = None
    paper4.url = ""
    paper4.externalIds = {}
    paper4.alternateVersions = []
    assert downloader._extract_arxiv_id(paper4) is None 