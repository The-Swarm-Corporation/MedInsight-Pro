import os
from Bio import Entrez
from loguru import logger
from dotenv import load_dotenv
from typing import Optional

# Load environment variables from .env file
load_dotenv()

# Check if email is set in the environment
ENTREZ_EMAIL = os.getenv("ENTREZ_EMAIL")

if not ENTREZ_EMAIL:
    raise EnvironmentError(
        "ENTREZ_EMAIL is not set in the environment. Please set it in your .env file."
    )

Entrez.email = ENTREZ_EMAIL  # Set email for Entrez queries

logger.add("pubmed_query.log", rotation="1 MB")  # Rotating log file


def query_pubmed_with_abstract(
    query: str,
    max_articles: int = 10,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    journal: Optional[str] = None,
    author: Optional[str] = None,
):
    """
    Query PubMed for articles and return their title, authors, abstract, etc.

    Args:
    query (str): The search query.
    max_articles (int): Maximum number of articles to retrieve.
    start_date (Optional[str]): Start date for filtering (e.g., "2020/01/01").
    end_date (Optional[str]): End date for filtering (e.g., "2023/12/31").
    journal (Optional[str]): Filter by journal name.
    author (Optional[str]): Filter by author name.

    Returns:
    List of dict: A list of dictionaries containing article info.
    """
    try:
        # Build the search query with optional filters
        search_query = query
        if journal:
            search_query += f' AND "{journal}"[Journal]'
        if author:
            search_query += f" AND {author}[Author]"
        if start_date and end_date:
            search_query += f" AND ({start_date}[Date - Publication] : {end_date}[Date - Publication])"

        logger.info(f"Querying PubMed with search: {search_query}")

        # Fetch search results from PubMed
        handle = Entrez.esearch(
            db="pubmed", term=search_query, retmax=max_articles
        )
        record = Entrez.read(handle)
        handle.close()

        id_list = record["IdList"]
        logger.info(
            f"Found {len(id_list)} articles for query: {search_query}"
        )

        if not id_list:
            logger.warning("No articles found.")
            return []

        # Fetch article details (XML format)
        handle = Entrez.efetch(
            db="pubmed",
            id=",".join(id_list),
            rettype="xml",
            retmode="text",
        )
        articles = Entrez.read(handle)
        handle.close()

        article_list = []

        # Extract information from articles
        for article in articles["PubmedArticle"]:
            article_data = {}
            medline_citation = article.get("MedlineCitation", {})
            article_metadata = medline_citation.get("Article", {})

            article_data["Title"] = article_metadata.get(
                "ArticleTitle", "N/A"
            )
            article_data["PMID"] = medline_citation.get("PMID", "N/A")
            article_data["Authors"] = [
                (
                    f"{author['LastName']} {author.get('Initials', '')}"
                    if "LastName" in author
                    else "Unknown Author"
                )
                for author in article_metadata.get("AuthorList", [])
            ]
            article_data["Source"] = article_metadata.get(
                "Journal", {}
            ).get("Title", "N/A")
            article_data["PublicationDate"] = (
                article_metadata.get("Journal", {})
                .get("JournalIssue", {})
                .get("PubDate", "N/A")
            )

            # Extract abstract if available
            abstract = article_metadata.get("Abstract", {}).get(
                "AbstractText", []
            )
            article_data["Abstract"] = (
                " ".join(str(part) for part in abstract)
                if abstract
                else "N/A"
            )

            article_list.append(article_data)

        logger.info(
            f"Successfully retrieved {len(article_list)} articles."
        )
        # Output the results
        # Output the results as a single string
        merged_string = ""
        for (
            article
        ) in article_list:  # Changed from articles to article_list
            title = f"Title: {article['Title']}"
            pmid = f"PMID: {article['PMID']}"
            authors = f"Authors: {article['Authors']}"
            source = f"Source: {article['Source']}"
            publication_date = (
                f"Publication Date: {article['PublicationDate']}"
            )
            abstract = f"Abstract: {article['Abstract']}"
            merged_string += f"{title}\n{pmid}\n{authors}\n{source}\n{publication_date}\n{abstract}\n"  # Concatenate to merged_string
            merged_string += "-" * 40 + "\n"  # Add separator
            merged_string += "\n"

        # print(merged_string)  # Print the final merged string
        return merged_string
    except Exception as e:
        logger.exception(
            f"An error occurred during the PubMed query: {e}"
        )
        return []


# # Example usage with more search features
# articles = query_pubmed_with_abstract(
#     query="deep learning in medical imaging",
#     max_articles=20,
# )


# print(articles)
