import pytest
from unittest.mock import Mock, patch
from semantic_scholar_search.base.search import search_papers
from semanticscholar.SemanticScholarException import NoMorePagesException

@pytest.fixture
def mock_paper():
    return {
        "paperId": "123",
        "title": "Test Paper",
        "authors": [{"name": "John Doe"}],
        "year": 2023,
        "citationCount": 100,
    }

@pytest.fixture
def mock_search_results():
    mock_results = Mock()
    mock_results.items = []
    return mock_results

def test_search_papers_basic():
    with patch('semantic_scholar_search.base.search.SemanticScholar') as mock_sch:
        # Setup mock
        mock_instance = mock_sch.return_value
        mock_results = Mock()
        mock_results.items = [{"title": "Test Paper"}]
        mock_instance.search_paper.return_value = mock_results

        # Test basic search
        results = search_papers("machine learning")
        
        # Verify
        assert len(results) == 1
        assert results[0]["title"] == "Test Paper"
        mock_instance.search_paper.assert_called_once_with(
            "machine learning",
            bulk=False,
            limit=10,
            sort="citationCount:desc",
            min_citation_count=0,
            fields_of_study=None,
            publication_date_or_year=None
        )

def test_search_papers_pagination():
    with patch('semantic_scholar_search.base.search.SemanticScholar') as mock_sch:
        # Setup mock
        mock_instance = mock_sch.return_value
        mock_results = Mock()
        mock_results.items = [{"title": f"Paper {i}"} for i in range(3)]
        mock_instance.search_paper.return_value = mock_results

        # Test pagination
        results = search_papers("machine learning", max_pages=3)
        
        # Verify next_page was called twice (for max_pages=3)
        assert mock_results.next_page.call_count == 2

def test_search_papers_no_more_pages():
    with patch('semantic_scholar_search.base.search.SemanticScholar') as mock_sch:
        # Setup mock
        mock_instance = mock_sch.return_value
        mock_results = Mock()
        mock_results.items = [{"title": "Test Paper"}]
        mock_results.next_page.side_effect = NoMorePagesException()
        mock_instance.search_paper.return_value = mock_results

        # Test when no more pages are available
        results = search_papers("machine learning", max_pages=3)
        
        # Verify that we got results despite the NoMorePagesException
        assert len(results) == 1
        assert results[0]["title"] == "Test Paper"
        # Verify next_page was called once before exception
        assert mock_results.next_page.call_count == 1

def test_search_papers_with_parameters():
    with patch('semantic_scholar_search.base.search.SemanticScholar') as mock_sch:
        # Setup mock
        mock_instance = mock_sch.return_value
        mock_results = Mock()
        mock_results.items = [{"title": "Test Paper"}]
        mock_instance.search_paper.return_value = mock_results

        fields = ["Computer Science", "Medicine"]
        
        # Test with custom parameters
        results = search_papers(
            "machine learning",
            bulk=True,
            max_pages=2,
            max_results_per_page=20,
            sort="publicationDate:desc",
            min_citation_count=10,
            fields_of_study=fields,
            publication_date_or_year="2020:2023"
        )
        
        # Verify custom parameters were passed correctly
        mock_instance.search_paper.assert_called_once_with(
            "machine learning",
            bulk=True,
            limit=20,
            sort="publicationDate:desc",
            min_citation_count=10,
            fields_of_study=fields,
            publication_date_or_year="2020:2023"
        )
