# PubMed RAG System

## Project Title

**PubMed RAG System: Contextualized Scientific Article Retrieval and Co-authorship Network Visualization**

## Description

This project implements a Retrieval-Augmented Generation (RAG) system designed to interact with scientific literature from PubMed. It allows users to ingest articles based on search terms, ask questions that are answered using the ingested content, and visualize a co-authorship network of authors from the relevant articles. The system leverages MongoDB for metadata storage, ChromaDB for vector embeddings and retrieval, and FastAPI for the backend API, with a responsive web frontend built using HTML, JavaScript, and Tailwind CSS.

## Features

* **PubMed Data Ingestion:** Fetch scientific articles (PMID, Title, Abstract, Authors, Publication Date) from PubMed using the Entrez API.

* **Abstract Chunking & Embedding:** Abstracts are chunked into smaller, semantically meaningful units, and then embedded into vector representations using a Sentence Transformer model (all-MiniLM-L6-v2).

* **Hybrid Data Storage:**

  * **MongoDB:** Stores structured metadata of articles (PMID, Title, Authors, Publication Date).

  * **ChromaDB:** Stores vector embeddings of abstract chunks for efficient semantic search.

* **Retrieval-Augmented Generation (RAG):**

  * Accepts natural language questions from the user.

  * Retrieves the most semantically relevant abstract chunks from ChromaDB.

  * Feeds the retrieved context along with the question to a Large Language Model (LLM - Google Gemini 2.0 Flash) to generate a concise and informed answer.

* **Author Co-authorship Network Visualization:**

  * Generates an interactive force-directed graph using D3.js.

  * **Nodes:** Represent individual authors.

  * **Links (Edges):** Connect two authors if they have co-authored at least one article.

  * **Context-Based Filtering:** The graph can be dynamically loaded to show co-authorship networks *only* among authors from the articles retrieved in the last RAG query's context.

  * **Interactive Tooltips:** Hover over links to see the titles and PMIDs of co-authored articles.

  * **Zoom and Pan:** Navigate the graph easily.

* **User-Friendly Web Interface:** A clean and responsive frontend for easy interaction with the system.

* **Configurable Backend:** Allows setting the FastAPI backend URL, Gemini API Key, and Entrez Email directly from the web interface.

## Technologies Used

* **Backend:**

  * Python 3.x

  * FastAPI: Web framework for building the API.

  * PyMongo: Python driver for MongoDB.

  * ChromaDB: Open-source vector database.

  * Sentence Transformers: For generating embeddings (using `all-MiniLM-L6-v2`).

  * Biopython (`Bio.Entrez`, `Bio.Medline`): For interacting with PubMed.

  * `httpx`: Asynchronous HTTP client for LLM API calls.

  * `uvicorn`: ASGI server for running FastAPI.

* **Frontend:**

  * HTML5

  * CSS3 (Tailwind CSS for utility-first styling)

  * JavaScript

  * D3.js: For interactive network graph visualization.

* **Databases:**

  * MongoDB: NoSQL database for structured article metadata.

  * ChromaDB (Persistent Client): Vector database for embeddings.

* **Large Language Model (LLM):**

  * Google Gemini 2.0 Flash (via Google Generative Language API)

## Setup Instructions

### 1. Clone the Repository
### 2. Create and Activate a Virtual Environment

It's highly recommended to use a virtual environment to manage dependencies.

```bash
python -m venv venv
source venv/bin/activate
```

### 3. Install Python Dependencies

```bash
pip install -r requirements.txt
```

### 4. Install and Run MongoDB

Ensure you have MongoDB installed and running on your system.

* **Download:** [MongoDB Community Server](https://www.mongodb.com/try/download/community)

* **Installation:** Follow the official MongoDB installation guide for your operating system.

* **Verify Running:** After installation, ensure the MongoDB service is running (e.g., check `services.msc` on Windows, or `systemctl status mongod` on Linux). It typically runs on `localhost:27017`.

### 5. Configure API Keys and Email

#### a. Entrez Email

PubMed's Entrez API requires you to provide your email address. You can set this directly in the web interface under "Backend Configuration" after starting the application.

#### b. Google Gemini API Key

To use the RAG functionality, you need a Google Gemini API Key.

* **Get a key:** [Google AI Studio](https://aistudio.google.com/app/apikey)

* **Set in Interface:** Enter your API key in the "Gemini API Key" field in the web interface under "Backend Configuration". This will be stored in your browser's local storage.

## How to Run the Application

### 1. Start the FastAPI Backend

Navigate to the project root directory in your terminal (where `main.py` is located) and run:

```bash
uvicorn main:app --reload
```


You should see output indicating that Uvicorn is running, typically on `http://127.0.0.1:8000`. The `--reload` flag will automatically restart the server when you make changes to the Python files.

### 2. Access the Web Frontend

Open your web browser and navigate to:

http://localhost:8000/

Perform a hard refresh (`Ctrl + Shift + R` or `Cmd + Shift + R`) if the page doesn't load correctly or if you've made recent frontend changes.

## Usage

### 1. Backend Configuration

* **FastAPI Backend URL:** Defaults to `http://localhost:8000`. Change if your backend is running on a different address/port.

* **Gemini API Key:** Paste your Google Gemini API Key here. This is crucial for the "Ask a Question" feature.

* **Entrez Email:** Enter your email address for PubMed API access. This is required for "Data Ingestion".

### 2. Data Ingestion

* Enter a **"Search Term"** (e.g., "CRISPR", "Alzheimer's disease").

* Specify **"Max Results"** (number of articles to fetch).

* Click **"Ingest Data"**. The system will fetch articles, chunk abstracts, create embeddings, and store data in MongoDB and ChromaDB. This may take some time depending on `max_results`.

* You can click **"Clear All Data"** to remove all ingested articles from both databases.

### 3. Database Metadata

* The "Total Articles" counter shows how many articles are currently stored in MongoDB.

* Click **"Refresh Metadata"** to update this count.

### 4. Ask a Question (RAG)

* Type your question in the **"Your Question"** textarea (e.g., "What are the therapeutic applications of CRISPR-Cas9?").

* Click **"Ask"**. The system will retrieve relevant context from ChromaDB and use the Gemini LLM to generate an answer. The answer and the context documents will be displayed.

### 5. Author Co-authorship Network

* Click **"Load Context-based Network Graph"**.

* **If you have just asked a question**, the graph will display the co-authorship network *only* among the authors of the articles that were part of the LLM's context.

* **If no context is available (e.g., after clearing data or before asking a question)**, it will load the co-authorship network from *all* articles in the database.

* **Interaction:**

  * **Drag nodes:** Click and drag author nodes to move them.

  * **Zoom/Pan:** Use your mouse wheel to zoom in/out, and click-drag the background to pan.

  * **Link Tooltip:** Hover over a link (line between two authors) to see the titles and PMIDs of the articles they co-authored. Thicker links indicate more shared articles.

## Project Structure

```bash
.
├── main.py                 # FastAPI backend application
├── mongodb_handler.py      # Handles MongoDB interactions
├── chromadb_handler.py     # Handles ChromaDB interactions and embedding model loading
├── pubmed_ingestor.py      # Logic for fetching and ingesting PubMed data
├── index.html              # Frontend HTML structure
├── script.js               # Frontend JavaScript logic
├── style.css               # Frontend CSS styling
└── README.md               # This file

```

