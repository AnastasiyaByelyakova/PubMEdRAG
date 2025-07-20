# main.py
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles # Import StaticFiles
from contextlib import asynccontextmanager
import os
import httpx # For making HTTP requests to Gemini API
import logging
import json # For parsing JSON response from Gemini API

# Import custom handlers and ingestor
from mongodb_handler import MongoDBHandler
from chromadb_handler import ChromaDBHandler
from pubmed_ingestor import PubMedIngestor

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Global variables for database handlers ---
mongo_handler: MongoDBHandler = None
chroma_handler: ChromaDBHandler = None
pubmed_ingestor: PubMedIngestor = None

# --- FastAPI Lifespan Events ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Handles startup and shutdown events for the FastAPI application.
    Connects to databases on startup and disconnects on shutdown.
    """
    global mongo_handler, chroma_handler, pubmed_ingestor

    # --- Startup ---
    logging.info("FastAPI app startup: Connecting to databases...")

    # Initialize MongoDB Handler
    mongo_handler = MongoDBHandler()
    mongo_handler.connect()
    if mongo_handler.client is None:
        logging.error("Failed to connect to MongoDB. Exiting application.")
        # In a real application, you might raise an exception or handle this more gracefully
        # For now, we'll let the app start but functionality will be limited.

    # Initialize ChromaDB Handler
    # Using a persistent client to store embeddings on disk
    chroma_db_path = os.getenv("CHROMADB_PATH", "./chroma_db")
    chroma_handler = ChromaDBHandler(path=chroma_db_path)
    chroma_handler.connect()
    if chroma_handler.client is None or chroma_handler.model is None:
        logging.error("Failed to connect to ChromaDB or load embedding model. RAG functionality will be limited.")

    # Initialize PubMed Ingestor
    # The email will now be passed dynamically from the frontend during ingestion
    pubmed_ingestor = PubMedIngestor(mongo_handler, chroma_handler, email="default@example.com") # Default email, will be overridden

    logging.info("FastAPI app startup complete.")
    yield
    # --- Shutdown ---
    logging.info("FastAPI app shutdown: Disconnecting from databases...")
    if mongo_handler:
        mongo_handler.disconnect()
    if chroma_handler:
        chroma_handler.disconnect()
    logging.info("FastAPI app shutdown complete.")


app = FastAPI(lifespan=lifespan, title="PubMed RAG System", version="1.0.0")

# --- CORS Middleware ---
# Allows requests from all origins. Adjust `allow_origins` in production.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Allows all origins
    allow_credentials=True,
    allow_methods=["*"], # Allows all methods (GET, POST, PUT, DELETE, etc.)
    allow_headers=["*"], # Allows all headers
)

# --- Serve Static Files ---
# Mount the directory containing index.html as a static directory
# Assuming index.html is in the same directory as main.py
app.mount("/static", StaticFiles(directory="."), name="static")

# --- Routes ---

@app.get("/", response_class=HTMLResponse) # Change root endpoint to return HTML
async def read_root():
    """
    Root endpoint for the API, now serving the index.html file.
    """
    with open("index.html", "r") as f:
        html_content = f.read()
    return HTMLResponse(content=html_content)

@app.get("/metadata")
async def get_metadata():
    """
    Retrieves metadata about the ingested data from MongoDB.
    """
    if mongo_handler.client is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="MongoDB not connected.")
    try:
        article_count = mongo_handler.get_article_count()
        # You can add more metadata here if needed, e.g., unique author count
        return {"article_count": article_count}
    except Exception as e:
        logging.error(f"Error getting metadata: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to retrieve metadata.")

@app.post("/ingest")
async def ingest_data(request: Request):
    """
    Triggers the data ingestion process from PubMed.
    """
    if pubmed_ingestor is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="PubMed Ingestor not initialized.")
    try:
        data = await request.json()
        term = data.get("term", "CRISPR")
        max_results = int(data.get("max_results", 10))
        entrez_email = data.get("entrez_email") # Get Entrez email from frontend

        if not term:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="'term' parameter is required for ingestion.")
        if not isinstance(max_results, int) or max_results <= 0:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="'max_results' must be a positive integer.")
        if not entrez_email:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="'entrez_email' is required for PubMed API access.")

        logging.info(f"Ingestion requested for term: '{term}', max_results: {max_results}, email: {entrez_email}")
        
        # Update the email in the existing pubmed_ingestor instance
        pubmed_ingestor.email = entrez_email # Directly set the email attribute

        # Run ingestion in a background task if it's long-running
        # For simplicity, running directly for now, but consider FastAPI background tasks for production
        pubmed_ingestor.fetch_and_ingest(term=term, max_results=max_results)
        return {"message": f"Ingestion process initiated for term '{term}'. Check logs for progress."}
    except HTTPException as e:
        raise e
    except Exception as e:
        logging.error(f"Error during data ingestion request: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to initiate ingestion: {e}")

@app.post("/ask")
async def ask_question(request: Request):
    """
    Receives a user query, retrieves relevant context, and generates an answer using an LLM.
    """
    if chroma_handler.client is None or chroma_handler.model is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="ChromaDB or embedding model not ready for RAG.")

    try:
        data = await request.json()
        query = data.get("query")
        api_key_from_frontend = data.get("api_key")

        if not query:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="'query' parameter is required.")

        logging.info(f"Received question: '{query}'")

        # Step 1: Retrieve relevant chunks from ChromaDB
        retrieved_chunks = chroma_handler.query_chunks(query, n_results=5) # Get top 5 relevant chunks

        context_documents = [chunk['document'] for chunk in retrieved_chunks]
        context_metadatas = [chunk['metadata'] for chunk in retrieved_chunks]

        # Construct a comprehensive context string
        context_string = ""
        for i, doc in enumerate(context_documents):
            metadata = context_metadatas[i]
            article_title = metadata.get('title', 'Unknown Title')
            article_id = metadata.get('article_id', 'Unknown ID')
            context_string += f"--- Article: {article_title} (PMID: {article_id}) ---\n"
            context_string += f"{doc}\n\n"

        if not context_string:
            context_string = "No relevant context found."
            logging.warning(f"No context found for query: '{query}'")

        # Step 2: Call Gemini LLM with the retrieved context
        # Use httpx for async HTTP requests
        # Prioritize API key from frontend, then environment variable, then empty string
        api_key = api_key_from_frontend if api_key_from_frontend else os.getenv("GEMINI_API_KEY", "")
        if not api_key:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Gemini API Key is required but not provided.")

        api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}"

        # Define the prompt string here
        prompt = f"""
        You are an AI assistant specialized in scientific literature.
        Based on the following context, answer the question comprehensively and accurately.
        If the answer is not available in the context, state that clearly.

        Context:
        {context_string}

        Question: {query}

        Answer:
        """

        payload = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.2, # Lower temperature for more focused answers
                "topK": 40,
                "topP": 0.95,
                "maxOutputTokens": 1024
            }
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(api_url, json=payload, timeout=60.0) # Increased timeout
            response.raise_for_status() # Raise an exception for bad status codes (4xx or 5xx)
            llm_result = response.json()

        generated_answer = "Could not generate an answer."
        if llm_result and llm_result.get("candidates"):
            first_candidate = llm_result["candidates"][0]
            if first_candidate.get("content") and first_candidate["content"].get("parts"):
                generated_answer = first_candidate["content"]["parts"][0].get("text", generated_answer)
        else:
            logging.error(f"LLM response structure unexpected: {llm_result}")

        return {
            "answer": generated_answer,
            "context": retrieved_chunks # Return full chunks including metadata and distance
        }
    except httpx.HTTPStatusError as e:
        logging.error(f"HTTP error from LLM API: {e.response.status_code} - {e.response.text}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error from LLM API: {e.response.text}")
    except httpx.RequestError as e:
        logging.error(f"Network error calling LLM API: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Network error calling LLM API: {e}")
    except HTTPException as e:
        raise e
    except Exception as e:
        logging.error(f"An unexpected error occurred during /ask request: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"An internal server error occurred: {e}")


@app.post("/network")
async def get_network_data(request: Request):
    """
    Retrieves author-centric network data for visualization,
    optionally filtered by a list of article PMIDs.
    """
    if mongo_handler.client is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="MongoDB not connected.")
    
    try:
        data = await request.json()
        article_pmids = data.get("article_pmids", None) # Get list of PMIDs from request body

        network_data = mongo_handler.get_author_network_data(article_pmids=article_pmids)
        return network_data
    except Exception as e:
        logging.error(f"Error getting network data: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to retrieve network data.")

# --- Optional: Clear Database Endpoint (for development/testing) ---
@app.post("/clear_db")
async def clear_databases():
    """
    Clears all data from MongoDB and ChromaDB. Use with extreme caution!
    """
    if mongo_handler:
        mongo_handler.clear_database()
    if chroma_handler:
        chroma_handler.clear_collection()
    return {"message": "All data cleared from MongoDB and ChromaDB."}
