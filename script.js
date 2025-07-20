// script.js

// --- Global Variables and Configuration ---
let BACKEND_URL = localStorage.getItem('backendUrl') || 'http://localhost:8000';
document.getElementById('backendUrl').value = BACKEND_URL;
document.getElementById('currentBackendUrl').textContent = BACKEND_URL;

let GEMINI_API_KEY = localStorage.getItem('geminiApiKey') || '';
document.getElementById('geminiApiKey').value = GEMINI_API_KEY;
document.getElementById('currentApiKeyStatus').textContent = GEMINI_API_KEY ? 'Set' : 'Not Set';

let ENTREZ_EMAIL = localStorage.getItem('entrezEmail') || '';
document.getElementById('entrezEmail').value = ENTREZ_EMAIL;
document.getElementById('currentEntrezEmailStatus').textContent = ENTREZ_EMAIL ? 'Set' : 'Not Set';


// Variable to store the last retrieved context's PMIDs
let lastContextPmids = [];

// --- Utility Functions ---
function showSpinner(spinnerId) {
    document.getElementById(spinnerId).classList.remove('hidden');
}

function hideSpinner(spinnerId) {
    document.getElementById(spinnerId).classList.add('hidden');
}

function showMessage(elementId, message, type = 'info') {
    const element = document.getElementById(elementId);
    element.textContent = message;
    element.className = `text-sm mt-3 ${type === 'error' ? 'text-red-600' : 'text-gray-600'}`;
}

// Custom Modal Function (replaces alert/confirm)
function showCustomModal(title, message, type = 'info', onConfirm = null) {
    const modalOverlay = document.createElement('div');
    modalOverlay.className = 'modal-overlay';
    modalOverlay.innerHTML = `
        <div class="modal-content">
            <h3 class="modal-header ${type === 'error' ? 'text-red-600' : ''}">${title}</h3>
            <p class="modal-body">${message}</p>
            <div class="modal-footer">
                ${onConfirm ? '<button id="modalCancelBtn" class="btn-secondary">Cancel</button>' : ''}
                <button id="modalConfirmBtn" class="btn-primary">${onConfirm ? 'Confirm' : 'OK'}</button>
            </div>
        </div>
    `;
    document.body.appendChild(modalOverlay);

    return new Promise(resolve => {
        document.getElementById('modalConfirmBtn').onclick = () => {
            document.body.removeChild(modalOverlay);
            resolve(true);
        };
        if (onConfirm) {
            document.getElementById('modalCancelBtn').onclick = () => {
                document.body.removeChild(modalOverlay);
                resolve(false);
            };
        }
    });
}


// --- Backend URL Handling ---
document.getElementById('setBackendUrlBtn').addEventListener('click', () => {
    const newUrl = document.getElementById('backendUrl').value.trim();
    if (newUrl) {
        BACKEND_URL = newUrl;
        localStorage.setItem('backendUrl', newUrl);
        document.getElementById('currentBackendUrl').textContent = newUrl;
        showMessage('urlStatus', 'Backend URL updated successfully.', 'info');
    } else {
        showMessage('urlStatus', 'Please enter a valid URL.', 'error');
    }
});

// --- API Key Handling ---
document.getElementById('setApiKeyBtn').addEventListener('click', () => {
    const newKey = document.getElementById('geminiApiKey').value.trim();
    if (newKey) {
        GEMINI_API_KEY = newKey;
        localStorage.setItem('geminiApiKey', newKey);
        document.getElementById('currentApiKeyStatus').textContent = 'Set';
        showMessage('apiKeyStatus', 'Gemini API Key updated successfully.', 'info');
    } else {
        GEMINI_API_KEY = '';
        localStorage.removeItem('geminiApiKey');
        document.getElementById('currentApiKeyStatus').textContent = 'Not Set';
        showMessage('apiKeyStatus', 'Gemini API Key cleared.', 'info');
    }
});

// --- Entrez Email Handling ---
document.getElementById('setEntrezEmailBtn').addEventListener('click', () => {
    const newEmail = document.getElementById('entrezEmail').value.trim();
    if (newEmail) {
        ENTREZ_EMAIL = newEmail;
        localStorage.setItem('entrezEmail', newEmail);
        document.getElementById('currentEntrezEmailStatus').textContent = 'Set';
        showMessage('entrezEmailStatus', 'Entrez Email updated successfully.', 'info');
    } else {
        ENTREZ_EMAIL = '';
        localStorage.removeItem('entrezEmail');
        document.getElementById('currentEntrezEmailStatus').textContent = 'Not Set';
        showMessage('entrezEmailStatus', 'Entrez Email cleared.', 'info');
    }
});


// --- Metadata Functions ---
async function fetchMetadata() {
    showSpinner('metadataSpinner');
    try {
        const response = await fetch(`${BACKEND_URL}/metadata`);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const data = await response.json();
        // Ensure data.article_count is a number, default to 0 if not
        document.getElementById('articleCount').textContent = typeof data.article_count === 'number' ? data.article_count : 0;
    } catch (error) {
        console.error('Error fetching metadata:', error);
        document.getElementById('articleCount').textContent = 'Error';
        showMessage('ingestStatus', `Failed to fetch metadata: ${error.message}`, 'error');
    } finally {
        hideSpinner('metadataSpinner');
    }
}

document.getElementById('refreshMetadataBtn').addEventListener('click', fetchMetadata);

// --- Ingestion Functions ---
document.getElementById('ingestBtn').addEventListener('click', async () => {
    const term = document.getElementById('ingestTerm').value;
    const maxResults = document.getElementById('maxResults').value;

    if (!term || !maxResults) {
        showMessage('ingestStatus', 'Please enter both search term and max results.', 'error');
        return;
    }
    if (!ENTREZ_EMAIL) {
        showCustomModal('Entrez Email Required', 'Please set your Entrez Email in the Backend Configuration section before ingesting data.', 'warning');
        showMessage('ingestStatus', 'Ingestion failed: Entrez Email not set.', 'error');
        return;
    }

    showSpinner('ingestSpinner');
    showMessage('ingestStatus', 'Ingestion started... This may take a while.');

    try {
        const response = await fetch(`${BACKEND_URL}/ingest`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                term: term,
                max_results: parseInt(maxResults),
                entrez_email: ENTREZ_EMAIL // Send Entrez email
            }),
        });

        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(`HTTP error! status: ${response.status}, detail: ${errorData.detail}`);
        }

        const data = await response.json();
        showMessage('ingestStatus', data.message, 'info');
        // Refresh metadata after ingestion
        fetchMetadata();
    } catch (error) {
        console.error('Error during ingestion:', error);
        showMessage('ingestStatus', `Ingestion failed: ${error.message}`, 'error');
    } finally {
        hideSpinner('ingestSpinner');
    }
});

// --- Clear Database Function ---
document.getElementById('clearDbBtn').addEventListener('click', async () => {
    const confirmed = await showCustomModal('Confirm Action', 'Are you sure you want to clear ALL data from the databases? This action cannot be undone.', 'warning', true);
    if (!confirmed) {
        return;
    }

    showSpinner('ingestSpinner'); // Reusing spinner
    showMessage('ingestStatus', 'Clearing databases...');

    try {
        const response = await fetch(`${BACKEND_URL}/clear_db`, {
            method: 'POST',
        });

        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(`HTTP error! status: ${response.status}, detail: ${errorData.detail}`);
        }

        const data = await response.json();
        showMessage('ingestStatus', data.message, 'info');
        fetchMetadata(); // Refresh metadata to show 0 articles
    } catch (error) {
        console.error('Error clearing database:', error);
        showMessage('ingestStatus', `Failed to clear database: ${error.message}`, 'error');
    } finally {
        hideSpinner('ingestSpinner');
    }
});

// --- RAG Query Functions ---
document.getElementById('askBtn').addEventListener('click', async () => {
    const question = document.getElementById('questionInput').value;
    if (!question.trim()) {
        document.getElementById('llmAnswer').textContent = "Please enter a question.";
        document.getElementById('contextUsed').innerHTML = "<p>No context retrieved yet.</p>";
        lastContextPmids = []; // Clear PMIDs if no question
        return;
    }

    showSpinner('askSpinner');
    document.getElementById('llmAnswer').textContent = "Generating answer...";
    document.getElementById('contextUsed').innerHTML = "<p>Retrieving context...</p>";
    lastContextPmids = []; // Reset PMIDs before new query

    try {
        const response = await fetch(`${BACKEND_URL}/ask`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ query: question, api_key: GEMINI_API_KEY }), // Pass API key
        });

        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(`HTTP error! status: ${response.status}, detail: ${errorData.detail}`);
        }

        const data = await response.json();

        // --- ADDED CHECKS HERE ---
        if (!data || typeof data.answer === 'undefined' || !Array.isArray(data.context)) {
            throw new Error("Invalid response format from backend. Expected 'answer' (string) and 'context' (array).");
        }
        // --- END ADDED CHECKS ---

        document.getElementById('llmAnswer').textContent = data.answer;

        // Extract PMIDs from the context for network visualization
        const uniquePmids = new Set();
        const contextHtml = data.context.map(c => {
            const pmid = c.metadata.article_id;
            if (pmid) {
                uniquePmids.add(pmid);
            }
            return `
                <div class="mb-2 p-2 border border-gray-200 rounded-md bg-white">
                    <p class="font-medium text-gray-800">${c.metadata.title || 'No Title'} (PMID: ${pmid || 'N/A'})</p>
                    <p class="text-xs text-gray-500">Distance: ${c.distance ? c.distance.toFixed(4) : 'N/A'}</p>
                    <p class="text-sm">${c.document || 'No document content available.'}</p>
                </div>
            `;
        }).join('');
        document.getElementById('contextUsed').innerHTML = contextHtml || "<p>No relevant context found.</p>";
        lastContextPmids = Array.from(uniquePmids); // Store unique PMIDs

    } catch (error) {
        console.error('Error asking question:', error);
        document.getElementById('llmAnswer').textContent = `Failed to get answer: ${error.message}`;
        document.getElementById('contextUsed').innerHTML = "<p>Error retrieving context.</p>";
        lastContextPmids = []; // Clear PMIDs on error
    } finally {
        hideSpinner('askSpinner');
    }
});

// --- D3.js Network Visualization ---
const svgWidth = document.getElementById('networkGraph').offsetWidth;
const svgHeight = document.getElementById('networkGraph').offsetHeight;

const svg = d3.select("#networkGraph").append("svg")
    .attr("width", "100%")
    .attr("height", "100%")
    .attr("viewBox", `0 0 ${svgWidth} ${svgHeight}`)
    .attr("preserveAspectRatio", "xMidYMid meet");

const g = svg.append("g"); // Group for zooming and panning

const zoom = d3.zoom()
    .scaleExtent([0.1, 8])
    .on("zoom", (event) => {
        g.attr("transform", event.transform);
    });

svg.call(zoom);

const simulation = d3.forceSimulation()
    .force("link", d3.forceLink().id(d => d.id).distance(100))
    .force("charge", d3.forceManyBody().strength(-300))
    .force("center", d3.forceCenter(svgWidth / 2, svgHeight / 2));

let tooltip = d3.select("#networkTooltip");

function updateGraph(graph) {
    g.selectAll("*").remove(); // Clear previous graph elements

    if (!graph || !graph.nodes || graph.nodes.length === 0) {
        console.warn("No graph data to display.");
        // Optionally display a message in the graph area
        g.append("text")
            .attr("x", svgWidth / 2)
            .attr("y", svgHeight / 2)
            .attr("text-anchor", "middle")
            .attr("fill", "#666")
            .text("No network data to display. Ingest data and/or ask a question first.");
        return;
    }

    // Links (co-authored articles)
    const link = g.append("g")
        .attr("class", "links")
        .selectAll("line")
        .data(graph.links)
        .enter().append("line")
        .attr("class", "link")
        .attr("stroke-width", d => Math.sqrt(d.articles.length) * 2) // Thicker links for more co-authored articles
        .on("mouseover", function(event, d) {
            let tooltipContent = `<strong>Co-authored by:</strong> ${d.source.name} & ${d.target.name}<br><strong>Articles:</strong><ul>`;
            d.articles.slice(0, 5).forEach(article => { // Show up to 5 articles
                tooltipContent += `<li>PMID: ${article.pmid} - ${article.title}</li>`;
            });
            if (d.articles.length > 5) {
                tooltipContent += `<li>...and ${d.articles.length - 5} more</li>`;
            }
            tooltipContent += `</ul>`;

            tooltip
                .style("left", (event.pageX + 10) + "px")
                .style("top", (event.pageY - 20) + "px")
                .html(tooltipContent)
                .classed("visible", true);
        })
        .on("mouseout", function() {
            tooltip.classed("visible", false);
        });

    // Nodes (Authors)
    const node = g.append("g")
        .attr("class", "nodes")
        .selectAll(".node")
        .data(graph.nodes)
        .enter().append("g")
        .attr("class", "node")
        .call(d3.drag()
            .on("start", dragstarted)
            .on("drag", dragged)
            .on("end", dragended));

    node.append("circle")
        .attr("r", 10) // Fixed size for authors
        .attr("fill", "#4CAF50") // Green for authors
        .on("mouseover", function(event, d) {
            tooltip
                .style("left", (event.pageX + 10) + "px")
                .style("top", (event.pageY - 20) + "px")
                .html(`<strong>Author:</strong> ${d.name}`)
                .classed("visible", true);
        })
        .on("mouseout", function() {
            tooltip.classed("visible", false);
        });

    node.append("text")
        .attr("dx", 12)
        .attr("dy", ".35em")
        .text(d => {
            const maxLength = 25; // Truncate long author names
            return d.name.length > maxLength ? d.name.substring(0, maxLength) + "..." : d.name;
        });

    simulation
        .nodes(graph.nodes)
        .on("tick", ticked);

    simulation.force("link")
        .links(graph.links);

    function ticked() {
        link
            .attr("x1", d => d.source.x)
            .attr("y1", d => d.source.y)
            .attr("x2", d => d.target.x)
            .attr("y2", d => d.target.y);

        node
            .attr("transform", d => `translate(${d.x},${d.y})`);
    }
}

function dragstarted(event, d) {
    if (!event.active) simulation.alphaTarget(0.3).restart();
    d.fx = d.x;
    d.fy = d.y;
}

function dragged(event, d) {
    d.fx = event.x;
    d.fy = event.y;
}

function dragended(event, d) {
    if (!event.active) simulation.alphaTarget(0);
    d.fx = null;
    d.fy = null;
}

document.getElementById('loadNetworkBtn').addEventListener('click', async () => {
    showSpinner('networkSpinner');
    try {
        let requestBody = {};
        // If there are PMIDs from the last context, send them
        if (lastContextPmids && lastContextPmids.length > 0) {
            requestBody = { article_pmids: lastContextPmids };
            console.log("Loading network for specific PMIDs:", lastContextPmids);
        } else {
            // Otherwise, load for all articles (backend default if article_pmids is None)
            console.log("Loading network for all articles (no specific context PMIDs found).");
            // No need to set requestBody if it's empty, as backend handles None
        }

        const response = await fetch(`${BACKEND_URL}/network`, {
            method: 'POST', // Changed to POST
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(requestBody),
        });

        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(`HTTP error! status: ${response.status}, detail: ${errorData.detail}`);
        }
        const graphData = await response.json();
        if (graphData.nodes.length === 0) {
            showCustomModal('No Data Available', 'No network data available for the selected context. Please ingest data and/or ask a question first.', 'info');
        }
        updateGraph(graphData);
    } catch (error) {
        console.error('Error loading network data:', error);
        showCustomModal('Error', `Failed to load network data: ${error.message}. Ensure backend is running and data is ingested.`, 'error');
    } finally {
        hideSpinner('networkSpinner');
    }
});

// --- Initial Load ---
window.onload = () => {
    fetchMetadata();
    // Initial call to load network data (optional, can be triggered by button)
    // document.getElementById('loadNetworkBtn').click();
};

// Resize graph on window resize
window.addEventListener('resize', () => {
    const newWidth = document.getElementById('networkGraph').offsetWidth;
    const newHeight = document.getElementById('networkGraph').offsetHeight;
    svg.attr("viewBox", `0 0 ${newWidth} ${newHeight}`);
    simulation.force("center", d3.forceCenter(newWidth / 2, newHeight / 2));
    simulation.alpha(0.3).restart(); // Restart simulation to adjust to new center
});