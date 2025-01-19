"""
Database for storing search history

There are two tables:
- searches: stores the search history
- papers: stores the papers downloaded
"""

import sqlite3
from datetime import datetime


class SearchDatabase:
    def __init__(self, db_path="search_history.db"):
        self.db_path = db_path
        self.init_db()

    def init_db(self):
        """Initialize the database with necessary tables"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()

        # Create searches table
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS searches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                query TEXT NOT NULL,
                max_pages INTEGER NOT NULL,
                max_results_per_page INTEGER NOT NULL,
                sort TEXT NOT NULL,
                min_citation_count INTEGER NOT NULL,
                fields_of_study TEXT,
                publication_date_or_year TEXT
            )
        """
        )

        # Create papers table
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS papers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                search_id INTEGER,
                paper_id TEXT,
                title TEXT,
                authors TEXT,
                year INTEGER,
                url TEXT,
                pdf_url TEXT,
                download_path TEXT,
                download_success BOOLEAN,
                download_timestamp TEXT,
                FOREIGN KEY (search_id) REFERENCES searches (id)
            )
        """
        )

        conn.commit()
        conn.close()

    def record_search(
        self,
        session_id,
        query,
        max_pages,
        max_results_per_page,
        sort,
        min_citation_count,
        fields_of_study=None,
        publication_date_or_year=None,
    ):
        """Record a new search"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()

        c.execute(
            """
            INSERT INTO searches (
                session_id, query, max_pages, max_results_per_page, 
                sort, min_citation_count, fields_of_study, publication_date_or_year
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                session_id,
                query,
                max_pages,
                max_results_per_page,
                sort,
                min_citation_count,
                ",".join(fields_of_study) if fields_of_study else None,
                publication_date_or_year,
            ),
        )

        search_id = c.lastrowid
        conn.commit()
        conn.close()
        return search_id

    def record_paper(
        self, search_id, paper, download_path=None, download_success=False
    ):
        """Record a paper and its download status"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()

        authors = (
            ", ".join([author.name for author in paper.authors])
            if paper.authors
            else ""
        )

        c.execute(
            """
            INSERT INTO papers (
                search_id, paper_id, title, authors, year, url,
                download_path, download_success, download_timestamp
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                search_id,
                paper.paperId,
                paper.title,
                authors,
                paper.year,
                paper.url,
                download_path,
                download_success,
                datetime.now().isoformat() if download_path else None,
            ),
        )

        conn.commit()
        conn.close()
