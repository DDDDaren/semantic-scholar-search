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
@patch('builtins.open', new_callable=mock_open)
def test_download_paper_arxiv(mock_file, mock_exists, downloader):
    # Setup
    mock_exists.return_value = True
    
    # Create a mock paper
    mock_paper = Mock(spec=[
        'title', 'externalIds', 'arxivId', 'url', 
        'isOpenAccess', 'openAccessPdf', 'journal'
    ])
    
    mock_paper.title = "Test Paper"
    mock_paper.arxivId = '1234.5678'
    mock_paper.url = 'https://arxiv.org/abs/1234.5678'
    mock_paper.isOpenAccess = False
    mock_paper.openAccessPdf = None
    
    # Set up journal
    mock_journal = Mock()
    mock_journal.name = 'arXiv'
    mock_paper.journal = mock_journal
    
    # Test
    result, method = downloader.download_paper(mock_paper, "test_search")
    
    # Check results
    expected_txt_path = os.path.join(downloader.get_directory(), "Test Paper_arxiv_links.txt")
    assert result == expected_txt_path
    assert method == 'arxiv'
    
    # Verify file write calls
    mock_file.assert_called_with(expected_txt_path, 'w')
    handle = mock_file()
    expected_content = [
        'Title: Test Paper\n',
        'ArXiv ID: 1234.5678\n',
        'Abstract page: https://arxiv.org/abs/1234.5678\n',
        'PDF download: https://arxiv.org/pdf/1234.5678.pdf\n'
    ]
    handle.write.assert_has_calls([call(line) for line in expected_content])
    
    # Verify database recording
    downloader.db.record_paper.assert_called_once_with("test_search", mock_paper, expected_txt_path, True)

@patch('os.path.exists')
@patch('requests.get')
def test_download_paper_open_access(mock_get, mock_exists, downloader):
    # Setup
    mock_exists.return_value = True
    mock_response = Mock()
    mock_response.content = b"fake pdf content"
    mock_response.status_code = 200
    mock_response.headers = {'content-type': 'application/pdf'}
    mock_get.return_value = mock_response
    
    mock_paper = Mock()
    mock_paper.title = "Test Paper"
    mock_paper.journal = None
    mock_paper.isOpenAccess = True
    mock_paper.openAccessPdf = {'url': 'https://example.com/paper.pdf'}
    
    # Test with mocked file operations
    with patch('builtins.open', mock_open()) as mock_file:
        result, method = downloader.download_paper(mock_paper, "test_search")
    
    expected_path = os.path.join(downloader.get_directory(), "Test Paper.pdf")
    assert result == expected_path
    assert method == 'open_access'
    mock_get.assert_called_once()
    downloader.db.record_paper.assert_called_once_with("test_search", mock_paper, expected_path, True)

@patch('os.path.exists')
def test_download_paper_no_pdf(mock_exists, downloader):
    mock_exists.return_value = True
    
    mock_paper = Mock()
    mock_paper.title = "Test Paper"
    mock_paper.journal = None
    mock_paper.isOpenAccess = False
    mock_paper.url = None
    
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
    # Test initial stats
    stats = downloader.get_download_stats()
    assert stats == {
        'total': 0,
        'open_access_success': 0,
        'semantic_reader_success': 0,
        'arxiv_success': 0,
        'failed': 0
    }

@patch('time.time')
@patch('time.sleep')
def test_respect_arxiv_rate_limit(mock_sleep, mock_time, downloader):
    # Setup time sequence
    mock_time.side_effect = [10.0, 11.0]  # First call returns 10.0, second call returns 11.0
    downloader.last_arxiv_request_time = 9.0  # Last request was 1 second ago
    
    # Test rate limiting
    downloader._respect_arxiv_rate_limit()
    
    # Should sleep for 1 second (3 - 1 = 2 seconds remaining)
    mock_sleep.assert_called_once_with(2.0) 