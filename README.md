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