# mongodb_handler.py
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, OperationFailure
import logging
from itertools import combinations # Import combinations for author pairs

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class MongoDBHandler:
    """
    Handles interactions with MongoDB for storing PubMed article metadata.
    """
    def __init__(self, host='localhost', port=27017, db_name='pubmed_rag_db'):
        """
        Initializes the MongoDB client and selects the database.

        Args:
            host (str): MongoDB host.
            port (int): MongoDB port.
            db_name (str): Name of the database to use.
        """
        self.client = None
        self.db = None
        self.host = host
        self.port = port
        self.db_name = db_name
        self.articles_collection = None

    def connect(self):
        """
        Establishes a connection to MongoDB.
        """
        try:
            self.client = MongoClient(self.host, self.port)
            # The ismaster command is cheap and does not require auth.
            self.client.admin.command('ismaster')
            self.db = self.client[self.db_name]
            self.articles_collection = self.db['articles']
            logging.info(f"Successfully connected to MongoDB at {self.host}:{self.port}")
        except ConnectionFailure as e:
            logging.error(f"Could not connect to MongoDB: {e}")
            self.client = None
            self.db = None
        except Exception as e:
            logging.error(f"An unexpected error occurred during MongoDB connection: {e}")
            self.client = None
            self.db = None

    def disconnect(self):
        """
        Closes the MongoDB connection.
        """
        if self.client:
            self.client.close()
            logging.info("MongoDB connection closed.")
            self.client = None
            self.db = None

    def insert_article(self, article_data):
        """
        Inserts a single PubMed article into the 'articles' collection.

        Args:
            article_data (dict): A dictionary containing article metadata.
                                 Must include '_id' for PubMed ID.

        Returns:
            str or None: The inserted article's _id if successful, otherwise None.
        """
        # Changed check from `if not self.articles_collection:`
        if self.articles_collection is None:
            logging.error("MongoDB connection not established. Cannot insert article.")
            return None
        try:
            # Use PubMed ID as _id to ensure uniqueness and easy retrieval
            if '_id' not in article_data:
                logging.error("Article data must contain a '_id' field (PubMed ID).")
                return None
            
            # Check if article already exists
            existing_article = self.articles_collection.find_one({'_id': article_data['_id']})
            if existing_article:
                logging.info(f"Article with PubMed ID {article_data['_id']} already exists. Skipping insertion.")
                return article_data['_id']

            result = self.articles_collection.insert_one(article_data)
            logging.info(f"Inserted article with ID: {result.inserted_id}")
            return str(result.inserted_id)
        except OperationFailure as e:
            logging.error(f"MongoDB operation failed during insertion: {e}")
            return None
        except Exception as e:
            logging.error(f"An unexpected error occurred during article insertion: {e}")
            return None

    def get_all_articles(self):
        """
        Retrieves all articles from the 'articles' collection.

        Returns:
            list: A list of dictionaries, where each dictionary is an article.
        """
        # Changed check from `if not self.articles_collection:`
        if self.articles_collection is None:
            logging.error("MongoDB connection not established. Cannot retrieve articles.")
            return []
        try:
            return list(self.articles_collection.find({}))
        except OperationFailure as e:
            logging.error(f"MongoDB operation failed during retrieval: {e}")
            return []
        except Exception as e:
            logging.error(f"An unexpected error occurred during article retrieval: {e}")
            return []

    def get_article_count(self):
        """
        Returns the total number of articles in the 'articles' collection.

        Returns:
            int: The count of articles.
        """
        # Changed check from `if not self.articles_collection:`
        if self.articles_collection is None:
            logging.error("MongoDB connection not established. Cannot get article count.")
            return 0
        try:
            return self.articles_collection.count_documents({})
        except OperationFailure as e:
            logging.error(f"MongoDB operation failed during count: {e}")
            return 0
        except Exception as e:
            logging.error(f"An unexpected error occurred during article count: {e}")
            return 0

    def get_author_network_data(self, article_pmids: list[str] = None):
        """
        Generates data for the author-centric network visualization,
        optionally filtered by a list of article PMIDs.
        Authors are nodes, and links represent co-authored articles.

        Args:
            article_pmids (list[str], optional): A list of PubMed IDs to filter articles by.
                                                  If None, all articles are considered.

        Returns:
            dict: A dictionary containing 'nodes' and 'links' for D3.js.
                  Nodes are authors.
                  Links connect co-authors, with article details as link metadata.
        """
        if self.articles_collection is None:
            logging.error("MongoDB connection not established. Cannot get network data.")
            return {"nodes": [], "links": []}

        nodes = {} # Use a dictionary to store unique authors and their details
        links = {} # Use a dictionary to store unique links (author pairs) and their shared articles

        try:
            query_filter = {}
            if article_pmids:
                query_filter["_id"] = {"$in": article_pmids}
                logging.info(f"Generating network data for {len(article_pmids)} specified articles.")
            else:
                logging.info("Generating network data for all articles in the database.")

            # Fetch only necessary fields: authors, PMID, and title
            articles = self.articles_collection.find(query_filter, {'_id': 1, 'title': 1, 'authors': 1})

            for article in articles:
                article_pmid = str(article['_id'])
                article_title = article.get('title', 'No Title')
                authors = article.get('authors', [])

                # Add authors as nodes
                for author_name in authors:
                    if author_name not in nodes:
                        nodes[author_name] = {
                            "id": author_name, # Author name as ID
                            "name": author_name,
                            "type": "author"
                        }

                # Create links between co-authors
                # Use combinations to get all unique pairs of authors for this article
                if len(authors) > 1:
                    for author1, author2 in combinations(sorted(authors), 2): # Sort to ensure consistent pair order
                        # Create a unique key for the link (e.g., "AuthorA--AuthorB")
                        link_key = f"{author1}--{author2}"

                        if link_key not in links:
                            links[link_key] = {
                                "source": author1,
                                "target": author2,
                                "articles": [] # List to store articles co-authored by this pair
                            }
                        # Add the current article to the list of articles for this link
                        links[link_key]["articles"].append({
                            "pmid": article_pmid,
                            "title": article_title
                        })
            
            # Convert nodes and links dictionaries to lists for D3.js
            node_list = list(nodes.values())
            link_list = list(links.values())

            logging.info(f"Generated author network data: {len(node_list)} nodes, {len(link_list)} links.")
            return {"nodes": node_list, "links": link_list}
        except OperationFailure as e:
            logging.error(f"MongoDB operation failed during author network data generation: {e}")
            return {"nodes": [], "links": []}
        except Exception as e:
            logging.error(f"An unexpected error occurred during author network data generation: {e}")
            return {"nodes": [], "links": []}

    def clear_database(self):
        """
        Clears all documents from the 'articles' collection. Use with caution.
        """
        # Changed check from `if not self.articles_collection:`
        if self.articles_collection is None:
            logging.error("MongoDB connection not established. Cannot clear database.")
            return
        try:
            result = self.articles_collection.delete_many({})
            logging.warning(f"Cleared {result.deleted_count} documents from 'articles' collection.")
        except OperationFailure as e:
            logging.error(f"MongoDB operation failed during clear: {e}")
        except Exception as e:
            logging.error(f"An unexpected error occurred during database clear: {e}")

# Example usage (for testing purposes, not part of the main application flow)
if __name__ == "__main__":
    mongo_handler = MongoDBHandler()
    mongo_handler.connect()

    # Clear previous data for a clean test
    mongo_handler.clear_database()

    # Insert dummy articles to test co-authorship
    dummy_article_1 = {
        "_id": "PMID1",
        "title": "Novel Approach to Quantum Computing",
        "abstract": "...",
        "authors": ["Alice Smith", "Bob Johnson", "Charlie Brown"],
        "publication_date": "2023-01-15"
    }
    mongo_handler.insert_article(dummy_article_1)

    dummy_article_2 = {
        "_id": "PMID2",
        "title": "AI in Medical Diagnostics",
        "abstract": "...",
        "authors": ["Alice Smith", "David Lee"],
        "publication_date": "2023-02-20"
    }
    mongo_handler.insert_article(dummy_article_2)

    dummy_article_3 = {
        "_id": "PMID3",
        "title": "Blockchain Applications in Healthcare",
        "abstract": "...",
        "authors": ["Bob Johnson", "Eve White"],
        "publication_date": "2023-03-01"
    }
    mongo_handler.insert_article(dummy_article_3)

    # Get author network data (all articles)
    network_data_all = mongo_handler.get_author_network_data()
    logging.info("Author Network Data (All Articles):")
    logging.info(f"Nodes: {network_data_all['nodes']}")
    logging.info(f"Links: {network_data_all['links']}")

    # Get author network data (filtered by PMIDs)
    filtered_pmids = ["PMID1", "PMID3"]
    network_data_filtered = mongo_handler.get_author_network_data(article_pmids=filtered_pmids)
    logging.info(f"Author Network Data (Filtered by PMIDs: {filtered_pmids}):")
    logging.info(f"Nodes: {network_data_filtered['nodes']}")
    logging.info(f"Links: {network_data_filtered['links']}")


    mongo_handler.disconnect()