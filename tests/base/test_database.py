import unittest
import sqlite3
import os
from datetime import datetime
from semantic_scholar_search.base.database import SearchDatabase
from unittest.mock import Mock

class TestSearchDatabase(unittest.TestCase):
    def setUp(self):
        """Set up test database before each test"""
        self.test_db_path = "test_search_history.db"
        self.db = SearchDatabase(self.test_db_path)

    def tearDown(self):
        """Clean up test database after each test"""
        if os.path.exists(self.test_db_path):
            os.remove(self.test_db_path)

    def test_init_db(self):
        """Test if database is properly initialized with required tables"""
        conn = sqlite3.connect(self.test_db_path)
        cursor = conn.cursor()
        
        # Check if tables exist
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {table[0] for table in cursor.fetchall()}
        
        self.assertIn('searches', tables)
        self.assertIn('papers', tables)
        
        conn.close()

    def test_record_search(self):
        """Test recording a new search"""
        search_id = self.db.record_search(
            session_id="test_session",
            query="machine learning",
            max_pages=2,
            max_results_per_page=10,
            sort="relevance",
            min_citation_count=5
        )
        
        # Verify the search was recorded
        conn = sqlite3.connect(self.test_db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM searches WHERE id=?", (search_id,))
        result = cursor.fetchone()
        conn.close()
        
        self.assertIsNotNone(result)
        self.assertEqual(result[1], "test_session")
        self.assertEqual(result[2], "machine learning")
        self.assertEqual(result[3], 2)
        self.assertEqual(result[4], 10)
        self.assertEqual(result[5], "relevance")
        self.assertEqual(result[6], 5)

    def test_record_paper(self):
        """Test recording a paper"""
        # First create a search to reference
        search_id = self.db.record_search(
            session_id="test_session",
            query="test query",
            max_pages=1,
            max_results_per_page=10,
            sort="relevance:desc",
            min_citation_count=0
        )
        
        # Create a mock paper object with proper author name strings
        mock_paper = Mock()
        mock_paper.paperId = "paper123"
        mock_paper.title = "Test Paper"
        # Create Mock authors with name property explicitly set as string
        author1 = Mock()
        author1.name = "John Doe"
        author2 = Mock()
        author2.name = "Jane Smith"
        mock_paper.authors = [author1, author2]
        mock_paper.year = 2023
        mock_paper.url = "https://example.com/paper123"
        
        # Record the paper
        self.db.record_paper(
            search_id=search_id,
            paper=mock_paper,
            download_path="/path/to/paper.pdf",
            download_success=True
        )
        
        # Verify the paper was recorded
        conn = sqlite3.connect(self.test_db_path)
        cursor = conn.cursor()
        
        # Add debug print to see the full row data
        cursor.execute("SELECT * FROM papers WHERE paper_id=?", ("paper123",))
        result = cursor.fetchone()
        print(f"Database row: {result}")  # Debug print
        
        # Add query to check table schema
        cursor.execute("PRAGMA table_info(papers)")
        columns = cursor.fetchall()
        print(f"Table schema: {columns}")  # Debug print
        
        conn.close()
        
        self.assertIsNotNone(result)
        self.assertEqual(result[1], search_id)
        self.assertEqual(result[2], "paper123")
        self.assertEqual(result[3], "Test Paper")
        self.assertEqual(result[4], "John Doe, Jane Smith")
        self.assertEqual(result[5], 2023)
        self.assertEqual(result[6], "https://example.com/paper123")
        self.assertEqual(result[8], "/path/to/paper.pdf")
        self.assertEqual(result[9], True)
        self.assertIsNotNone(result[10])

    def test_record_search_with_date_range(self):
        """Test recording a search with publication date range"""
        search_id = self.db.record_search(
            session_id="test_session",
            query="machine learning",
            max_pages=2,
            max_results_per_page=10,
            sort="relevance",
            min_citation_count=5,
            fields_of_study=["Computer Science"],
            publication_date_or_year="2020:2023"
        )
        
        conn = sqlite3.connect(self.test_db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM searches WHERE id=?", (search_id,))
        result = cursor.fetchone()
        conn.close()
        
        self.assertIsNotNone(result)
        self.assertEqual(result[1], "test_session")
        self.assertEqual(result[2], "machine learning")
        self.assertEqual(result[7], "Computer Science")
        self.assertEqual(result[8], "2020:2023")

if __name__ == '__main__':
    unittest.main() 