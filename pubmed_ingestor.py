# pubmed_ingestor.py
from Bio import Entrez
from Bio import Medline
import logging
import re
from datetime import datetime
import io # Import io for string buffer
import ssl # Import the ssl module

from mongodb_handler import MongoDBHandler
from chromadb_handler import ChromaDBHandler

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

try:
    _create_unverified_https_context = ssl._create_unverified_context
except AttributeError:
    # Legacy Python that doesn't have _create_unverified_context
    pass
else:
    # Tell Entrez to use the unverified context
    ssl._create_default_https_context = _create_unverified_https_context
# --- END WARNING ---


class PubMedIngestor:
    """
    Fetches scientific article data from PubMed, chunks abstracts, generates embeddings,
    and stores the data in MongoDB and ChromaDB.
    """
    def __init__(self, mongo_handler: MongoDBHandler, chroma_handler: ChromaDBHandler, email: str):
        """
        Initializes the PubMedIngestor with database handlers and an Entrez email.

        Args:
            mongo_handler (MongoDBHandler): An instance of MongoDBHandler.
            chroma_handler (ChromaDBHandler): An instance of ChromaDBHandler.
            email (str): Your email address for Entrez API access.
        """
        self.mongo_handler = mongo_handler
        self.chroma_handler = chroma_handler
        Entrez.email = email
        logging.info(f"PubMedIngestor initialized with Entrez email: {email}")

    def _chunk_text(self, text: str, chunk_size_sentences: int = 3) -> list[str]:
        """
        Splits a given text into chunks based on sentences.

        Args:
            text (str): The input text (e.g., an abstract).
            chunk_size_sentences (int): Number of sentences per chunk.

        Returns:
            list[str]: A list of text chunks.
        """
        if not text:
            return []
        # Split by sentence-ending punctuation, keeping the punctuation
        sentences = re.split(r'(?<=[.!?])\s+', text)
        chunks = []
        current_chunk = []
        for i, sentence in enumerate(sentences):
            current_chunk.append(sentence.strip())
            if (i + 1) % chunk_size_sentences == 0 or i == len(sentences) - 1:
                if current_chunk: # Ensure chunk is not empty
                    chunks.append(" ".join(current_chunk))
                current_chunk = []
        logging.debug(f"Chunked text into {len(chunks)} chunks.")
        return chunks

    def fetch_and_ingest(self, term: str, max_results: int = 10):
        """
        Fetches articles from PubMed, processes them, and ingests into databases.

        Args:
            term (str): The search term for PubMed (e.g., "cancer immunotherapy").
            max_results (int): Maximum number of articles to fetch.
        """
        logging.info(f"Starting ingestion for term: '{term}' with max results: {max_results}")
        try:
            # Step 1: Search PubMed for UIDs
            handle = Entrez.esearch(db="pubmed", term=term, retmax=max_results)
            record = Entrez.read(handle)
            handle.close() # Close the esearch handle immediately
            id_list = record["IdList"]
            logging.info(f"Found {len(id_list)} PubMed IDs for term '{term}'.")

            if not id_list:
                logging.warning(f"No articles found for term '{term}'.")
                return

            # Step 2: Fetch full article details using UIDs
            # Fetch the content and read it into a string before parsing
            handle = Entrez.efetch(db="pubmed", id=id_list, rettype="medline", retmode="text")
            # Read the entire content of the handle into a string
            medline_content = handle.read()
            handle.close() # Close the efetch handle immediately after reading

            # Use io.StringIO to create a file-like object from the string content
            # This allows Medline.parse to work without issues of closed file handles
            records = Medline.parse(io.StringIO(medline_content))

            articles_to_mongo = []
            chunks_to_chroma_texts = []
            chunks_to_chroma_metadatas = []
            chunks_to_chroma_ids = []

            for i, record in enumerate(records):
                pmid = record.get("PMID")
                title = record.get("TI", "No Title Available")
                abstract = record.get("AB", "No Abstract Available")
                authors = record.get("AU", [])
                pub_date_raw = record.get("DP") # Date Published, e.g., "2023 Jan 15"

                publication_date = None
                if pub_date_raw:
                    try:
                        # Attempt to parse common date formats
                        if re.match(r'^\d{4}\s[A-Za-z]{3}\s\d{1,2}$', pub_date_raw): # e.g., "2023 Jan 15"
                            publication_date = datetime.strptime(pub_date_raw, "%Y %b %d").isoformat()
                        elif re.match(r'^\d{4}\s[A-Za-z]{3}$', pub_date_raw): # e.g., "2023 Jan"
                            publication_date = datetime.strptime(pub_date_raw, "%Y %b").isoformat()
                        elif re.match(r'^\d{4}$', pub_date_raw): # e.g., "2023"
                            publication_date = datetime.strptime(pub_date_raw, "%Y").isoformat()
                        else:
                            logging.warning(f"Unrecognized date format for PMID {pmid}: {pub_date_raw}")
                    except ValueError:
                        logging.warning(f"Could not parse date '{pub_date_raw}' for PMID {pmid}")

                if not pmid:
                    logging.warning(f"Skipping article {i+1} due to missing PMID.")
                    continue

                article_data = {
                    "_id": pmid, # Use PMID as MongoDB _id
                    "title": title,
                    "abstract": abstract,
                    "authors": authors,
                    "publication_date": publication_date,
                    "source": "PubMed"
                }
                articles_to_mongo.append(article_data)

                # Chunk the abstract and prepare for ChromaDB
                chunks = self._chunk_text(abstract)
                for j, chunk in enumerate(chunks):
                    chunks_to_chroma_texts.append(chunk)
                    chunks_to_chroma_metadatas.append({
                        "article_id": pmid,
                        "chunk_index": j,
                        "source": "abstract",
                        "title": title # Add title to chunk metadata for context
                    })
                    chunks_to_chroma_ids.append(f"{pmid}_chunk_{j}")

                logging.info(f"Processed article {i+1}/{len(id_list)}: PMID {pmid}, Title: {title[:50]}...")

            # Step 3: Ingest into MongoDB
            # We insert one by one to handle existing articles gracefully
            logging.info(f"Attempting to insert {len(articles_to_mongo)} articles into MongoDB.")
            for article_data in articles_to_mongo:
                self.mongo_handler.insert_article(article_data)

            # Step 4: Ingest into ChromaDB
            if chunks_to_chroma_texts:
                logging.info(f"Attempting to add {len(chunks_to_chroma_texts)} chunks to ChromaDB.")
                self.chroma_handler.add_chunks(
                    chunks_to_chroma_texts,
                    chunks_to_chroma_metadatas,
                    chunks_to_chroma_ids
                )
            else:
                logging.warning("No chunks generated for ChromaDB.")

            logging.info(f"Ingestion process completed for term: '{term}'.")

        except Entrez.RequestError as e:
            logging.error(f"Entrez API request error: {e}. Please check your search term or network connection.")
        except Exception as e:
            logging.error(f"An unexpected error occurred during ingestion: {e}")

# Example usage (for testing purposes, not part of the main application flow)
if __name__ == "__main__":
    # Initialize handlers
    mongo_handler = MongoDBHandler(db_name='pubmed_rag_test_db')
    chroma_handler = ChromaDBHandler(path="./test_chroma_db", collection_name="pubmed_chunks_test")

    # Connect handlers
    mongo_handler.connect()
    chroma_handler.connect()

    # Clear previous data for a clean test run
    mongo_handler.clear_database()
    chroma_handler.clear_collection()

    # Initialize ingestor
    # IMPORTANT: Replace with your actual email address for Entrez
    ingestor = PubMedIngestor(mongo_handler, chroma_handler, email="your.email@example.com")

    # Perform ingestion
    # This will fetch articles related to "CRISPR" and store them
    ingestor.fetch_and_ingest(term="CRISPR", max_results=5)

    # Verify ingestion (optional)
    print("\n--- MongoDB Data ---")
    print(f"Article count: {mongo_handler.get_article_count()}")
    # print("Sample article:", mongo_handler.get_all_articles()[0] if mongo_handler.get_article_count() > 0 else "No articles")

    print("\n--- ChromaDB Data (Querying a sample) ---")
    sample_query_results = chroma_handler.query_chunks("What is CRISPR technology?", n_results=2)
    for res in sample_query_results:
        print(f"Chunk: {res['document'][:100]}...", f"Metadata: {res['metadata']}")

    # Disconnect handlers
    mongo_handler.disconnect()
    chroma_handler.disconnect()
