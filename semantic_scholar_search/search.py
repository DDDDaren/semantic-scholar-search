from semanticscholar import SemanticScholar  # type: ignore
from semanticscholar.SemanticScholarException import NoMorePagesException  # type: ignore
from semanticscholar.Paper import Paper  # type: ignore


def search_papers(
    query,
    bulk=False,
    max_pages=10,
    max_results_per_page=10,
    sort="citationCount:desc",
    min_citation_count=0,
) -> list[Paper]:
    sch = SemanticScholar()  # type: ignore

    results = sch.search_paper(
        query,
        bulk=bulk,
        limit=max_results_per_page,
        sort=sort,
        min_citation_count=min_citation_count,
    )

    for _ in range(max_pages - 1):
        try:
            results.next_page()
        except NoMorePagesException:
            break

    return results.items
