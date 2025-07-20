# chromadb_handler.py
import chromadb
from sentence_transformers import SentenceTransformer
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class ChromaDBHandler:
    """
    Handles interactions with ChromaDB for storing and querying text chunk embeddings.
    Integrates a SentenceTransformer model for embedding generation.
    """
    def __init__(self, path="./chroma_db", collection_name="pubmed_chunks", model_name="all-MiniLM-L6-v2"):
        """
        Initializes the ChromaDB client and loads the SentenceTransformer model.

        Args:
            path (str): Path to store ChromaDB data (for persistent client).
                        If None, an in-memory client will be used.
            collection_name (str): Name of the collection to use in ChromaDB.
            model_name (str): Name of the SentenceTransformer model to load.
        """
        self.client = None
        self.collection = None
        self.model = None
        self.path = path
        self.collection_name = collection_name
        self.model_name = model_name

    def connect(self):
        """
        Establishes connection to ChromaDB and loads the embedding model.
        """
        try:
            # Use PersistentClient to store data on disk
            self.client = chromadb.PersistentClient(path=self.path)
            self.collection = self.client.get_or_create_collection(self.collection_name)
            logging.info(f"Successfully connected to ChromaDB at path: {self.path}")

            # Load the SentenceTransformer model
            self.model = SentenceTransformer(self.model_name)
            logging.info(f"Successfully loaded SentenceTransformer model: {self.model_name}")
        except Exception as e:
            logging.error(f"Error connecting to ChromaDB or loading model: {e}")
            self.client = None
            self.collection = None
            self.model = None

    def disconnect(self):
        """
        No explicit disconnect for PersistentClient, but can log the action.
        """
        logging.info("ChromaDB client is ready for shutdown (no explicit disconnect needed for PersistentClient).")
        self.client = None
        self.collection = None
        self.model = None

    def _generate_embeddings(self, texts):
        """
        Generates embeddings for a list of texts using the loaded SentenceTransformer model.

        Args:
            texts (list[str]): A list of text strings.

        Returns:
            list[list[float]]: A list of embeddings, where each embedding is a list of floats.
        """
        if not self.model:
            logging.error("Embedding model not loaded. Cannot generate embeddings.")
            return []
        try:
            embeddings = self.model.encode(texts).tolist()
            return embeddings
        except Exception as e:
            logging.error(f"Error generating embeddings: {e}")
            return []

    def add_chunks(self, texts, metadatas, ids):
        """
        Adds text chunks, their metadata, and generated embeddings to the ChromaDB collection.

        Args:
            texts (list[str]): A list of text strings (chunks).
            metadatas (list[dict]): A list of dictionaries, where each dict is metadata for a chunk.
                                     Must align with 'texts' by index.
            ids (list[str]): A list of unique IDs for each chunk. Must align with 'texts' by index.

        Returns:
            bool: True if chunks were added successfully, False otherwise.
        """
        if not self.collection:
            logging.error("ChromaDB collection not initialized. Cannot add chunks.")
            return False
        if not self.model:
            logging.error("Embedding model not loaded. Cannot add chunks.")
            return False

        if not (len(texts) == len(metadatas) == len(ids)):
            logging.error("Lengths of texts, metadatas, and ids must be equal.")
            return False

        try:
            embeddings = self._generate_embeddings(texts)
            if not embeddings:
                logging.error("Failed to generate embeddings for chunks.")
                return False

            self.collection.add(
                documents=texts,
                embeddings=embeddings,
                metadatas=metadatas,
                ids=ids
            )
            logging.info(f"Added {len(texts)} chunks to ChromaDB collection '{self.collection_name}'.")
            return True
        except Exception as e:
            logging.error(f"Error adding chunks to ChromaDB: {e}")
            return False

    def query_chunks(self, query_text, n_results=5):
        """
        Queries the ChromaDB collection for chunks similar to the query text.

        Args:
            query_text (str): The text to query for.
            n_results (int): The number of top similar results to return.

        Returns:
            list: A list of dictionaries, where each dictionary represents a retrieved chunk
                  with its content, metadata, and distance.
        """
        if not self.collection:
            logging.error("ChromaDB collection not initialized. Cannot query chunks.")
            return []
        if not self.model:
            logging.error("Embedding model not loaded. Cannot query chunks.")
            return []

        try:
            query_embedding = self._generate_embeddings([query_text])[0]
            if not query_embedding:
                logging.error("Failed to generate embedding for query text.")
                return []

            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=n_results,
                include=['documents', 'metadatas', 'distances']
            )

            retrieved_chunks = []
            if results and results['documents'] and results['documents'][0]:
                for i in range(len(results['documents'][0])):
                    retrieved_chunks.append({
                        "document": results['documents'][0][i],
                        "metadata": results['metadatas'][0][i],
                        "distance": results['distances'][0][i]
                    })
            logging.info(f"Retrieved {len(retrieved_chunks)} chunks for query: '{query_text}'")
            return retrieved_chunks
        except Exception as e:
            logging.error(f"Error querying ChromaDB: {e}")
            return []

    def clear_collection(self):
        """
        Deletes the entire collection from ChromaDB. Use with extreme caution.
        """
        if not self.client:
            logging.error("ChromaDB client not initialized. Cannot clear collection.")
            return
        try:
            self.client.delete_collection(self.collection_name)
            self.collection = self.client.get_or_create_collection(self.collection_name) # Recreate empty collection
            logging.warning(f"ChromaDB collection '{self.collection_name}' cleared and recreated.")
        except Exception as e:
            logging.error(f"Error clearing ChromaDB collection: {e}")

# Example usage (for testing purposes, not part of the main application flow)
if __name__ == "__main__":
    chroma_handler = ChromaDBHandler(path="./test_chroma_db") # Use a separate path for testing
    chroma_handler.connect()

    # Clear previous data for a clean test
    chroma_handler.clear_collection()

    # Add some dummy chunks
    texts = [
        "The quick brown fox jumps over the lazy dog.",
        "Artificial intelligence is transforming many industries.",
        "Natural language processing is a subfield of AI.",
        "Dogs are known for their loyalty and companionship.",
        "Quantum computing promises revolutionary advancements."
    ]
    metadatas = [
        {"source": "fable", "article_id": "art1"},
        {"source": "tech_blog", "article_id": "art2"},
        {"source": "academic_paper", "article_id": "art2"},
        {"source": "pet_care", "article_id": "art3"},
        {"source": "science_news", "article_id": "art4"}
    ]
    ids = ["chunk1", "chunk2", "chunk3", "chunk4", "chunk5"]

    chroma_handler.add_chunks(texts, metadatas, ids)

    # Query for similar chunks
    query = "What is AI about?"
    results = chroma_handler.query_chunks(query, n_results=2)
    logging.info(f"\nQuery results for '{query}':")
    for res in results:
        logging.info(f"Document: {res['document']}, Metadata: {res['metadata']}, Distance: {res['distance']:.4f}")

    query = "Tell me about animals."
    results = chroma_handler.query_chunks(query, n_results=2)
    logging.info(f"\nQuery results for '{query}':")
    for res in results:
        logging.info(f"Document: {res['document']}, Metadata: {res['metadata']}, Distance: {res['distance']:.4f}")

    chroma_handler.disconnect()
