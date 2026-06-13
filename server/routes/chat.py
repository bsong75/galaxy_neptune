from flask import Blueprint, jsonify, request
from neptune_client import get_driver
from schema import GRAPH_SCHEMA
from routes.graph import run_and_collect
import requests
import os
import re

chat_bp = Blueprint('chat', __name__)

GROQ_API_KEY = os.environ.get('GROQ_API_KEY', '')
GROQ_URL = 'https://api.groq.com/openai/v1/chat/completions'
GROQ_MODEL = os.environ.get('GROQ_MODEL', 'llama-3.3-70b-versatile')

SYSTEM_PROMPT = f"""You are an openCypher query expert for a passenger graph database running on AWS Neptune.

Your ONLY job is to convert natural-language questions into openCypher queries. If the user's message is NOT a question about the graph (e.g. greetings like "hi", "hello", or off-topic chat), respond with exactly: NOT_A_QUERY

{GRAPH_SCHEMA}

Rules:
1. Return ONLY the Cypher query — no explanations, no markdown, no extra text.
2. Return results as columns named n, r, m (source node, relationship, target node).
3. Only include relationships the user actually asks about. Do NOT fan out to all connected nodes.
4. Add LIMIT 100 unless the user specifies otherwise.
5. Never use destructive operations (DELETE, REMOVE, DROP, SET, CREATE, MERGE).
6. When the user mentions a person by name, use case-insensitive matching with toLower() and CONTAINS on first_name or last_name properties. Names may be partial — e.g. "uncle bob" means first_name CONTAINS "uncle" or first_name CONTAINS "bob".
7. When the user asks about a specific person's relationships (e.g. "derogs for uncle bob"), match that person first, then traverse to the related nodes.
8. IMPORTANT: Never use inline property maps in MATCH clauses. Always use WHERE clauses instead.
   - WRONG: MATCH (n:MainPassenger {{upid: $upid}})
   - CORRECT: MATCH (n:MainPassenger) WHERE n.upid = $upid

Examples:

User: "Who is the main passenger?"
MATCH (n:MainPassenger) RETURN n, null AS r, null AS m LIMIT 100

User: "Show me all co-travelers"
MATCH (n:MainPassenger)-[r:CO_TRAVELER]->(m:AssociatedPerson) RETURN n, r, m LIMIT 100

User: "What derogs does the main passenger have?"
MATCH (n:MainPassenger)-[r:HAS_SEACAT]->(m:Seacat) RETURN n, r, m LIMIT 100

User: "Show all derogs for associated persons"
MATCH (n:AssociatedPerson)-[r:HAS_SEACAT|HAS_VISA|HAS_SECONDARY]->(m) RETURN n, r, m LIMIT 100

User: "How many derogs does uncle bob have?"
MATCH (n:AssociatedPerson) WHERE toLower(n.first_name) CONTAINS 'uncle' OR toLower(n.first_name) CONTAINS 'bob' OR toLower(n.last_name) CONTAINS 'uncle' OR toLower(n.last_name) CONTAINS 'bob' MATCH (n)-[r:HAS_SEACAT|HAS_VISA|HAS_SECONDARY]->(m) RETURN n, r, m LIMIT 100

User: "Show me info about daddy john"
MATCH (n:AssociatedPerson) WHERE toLower(n.first_name) CONTAINS 'daddy' OR toLower(n.first_name) CONTAINS 'john' OR toLower(n.last_name) CONTAINS 'daddy' OR toLower(n.last_name) CONTAINS 'john' RETURN n, null AS r, null AS m LIMIT 100

User: "Show visa refusals"
MATCH (n:AssociatedPerson)-[r:HAS_VISA]->(m:Visa) RETURN n, r, m LIMIT 100

User: "Show secondary inspections"
MATCH (n:AssociatedPerson)-[r:HAS_SECONDARY]->(m:Secondary) RETURN n, r, m LIMIT 100

User: "Show me the full graph"
MATCH (n)-[r]->(m) RETURN n, r, m LIMIT 100
"""


ANSWER_PROMPT = """You are a helpful assistant that summarizes graph database query results in plain English.
Given the user's original question and the query results (as a list of node properties), provide a concise, informative answer.
- Be specific: mention names, counts, types, dates, and other details from the data.
- Keep it to 2-3 sentences max.
- If results are empty, say you didn't find any matching data.
- Do NOT mention Cypher, Neptune, nodes, or relationships — speak as if answering the user directly.
"""


def _summarize_results(message, graph_data):
    """Make a second LLM call to generate a natural language answer from query results."""
    # Build a compact summary of the node data for the LLM
    node_summaries = []
    for node in graph_data.get('nodes', [])[:20]:  # Cap at 20 to keep prompt small
        props = {k: v for k, v in node.items() if k not in ('id', 'color', 'icon', 'upid', 'created_at')}
        node_summaries.append(props)

    result_text = f"Results ({len(graph_data.get('nodes', []))} items): {node_summaries}"

    try:
        resp = requests.post(
            GROQ_URL,
            headers={
                'Authorization': f'Bearer {GROQ_API_KEY}',
                'Content-Type': 'application/json',
            },
            json={
                'model': GROQ_MODEL,
                'messages': [
                    {'role': 'system', 'content': ANSWER_PROMPT},
                    {'role': 'user', 'content': f'Question: {message}\n\n{result_text}'},
                ],
                'temperature': 0,
            },
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()['choices'][0]['message']['content']
    except Exception:
        # Fallback if summarization fails
        count = len(graph_data.get('nodes', []))
        return f'Found {count} results.' if count else 'No matching data found.'


def extract_cypher(text):
    """Extract Cypher query from LLM response."""
    # Try to find code block first
    match = re.search(r'```(?:cypher)?\s*\n?(.*?)\n?```', text, re.DOTALL)
    if match:
        return match.group(1).strip()

    # Otherwise, try to find a line starting with MATCH, CALL, or WITH
    for line in text.strip().split('\n'):
        stripped = line.strip()
        if stripped.upper().startswith(('MATCH', 'CALL', 'WITH', 'OPTIONAL')):
            # Grab from this line to end
            start_idx = text.index(line)
            return text[start_idx:].strip()

    # Fallback: return the whole thing
    return text.strip()


@chat_bp.route('/chat', methods=['POST'])
def chat():
    """Send a natural language question and get graph results back.
    ---
    tags:
      - Chat
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          required:
            - message
          properties:
            message:
              type: string
              description: Natural language question about the graph
              example: "Who is the main passenger?"
    responses:
      200:
        description: Cypher query, graph data, and natural language answer
      400:
        description: No message provided
      500:
        description: LLM API key not configured
      502:
        description: LLM API error
    """
    data = request.get_json()
    message = data.get('message', '')

    if not message:
        return jsonify({'error': 'No message provided'}), 400

    # Call Groq API
    if not GROQ_API_KEY:
        return jsonify({'error': 'GROQ_API_KEY not set'}), 500

    try:
        groq_response = requests.post(
            GROQ_URL,
            headers={
                'Authorization': f'Bearer {GROQ_API_KEY}',
                'Content-Type': 'application/json',
            },
            json={
                'model': GROQ_MODEL,
                'messages': [
                    {'role': 'system', 'content': SYSTEM_PROMPT},
                    {'role': 'user', 'content': message},
                ],
                'temperature': 0,
            },
            timeout=60,
        )
        groq_response.raise_for_status()
        llm_text = groq_response.json()['choices'][0]['message']['content']
    except requests.RequestException as e:
        return jsonify({'error': f'Groq API error: {str(e)}'}), 502

    # Handle non-query messages (greetings, off-topic)
    if 'NOT_A_QUERY' in llm_text.strip():
        return jsonify({
            'cypher': '',
            'data': {'nodes': [], 'links': []},
            'answer': 'Ask me a question about the graph! For example: "Who is the main passenger?" or "Show derogs for co-travelers"',
        })

    # Extract and run Cypher
    cypher = extract_cypher(llm_text)

    # Safety check: block destructive operations
    cypher_upper = cypher.upper()
    if any(word in cypher_upper for word in ['DELETE', 'REMOVE', 'DROP', 'SET ', 'CREATE', 'MERGE']):
        return jsonify({
            'cypher': cypher,
            'data': {'nodes': [], 'links': []},
            'answer': 'Query blocked: only read operations are allowed.',
        })

    try:
        driver = get_driver()
        with driver.session() as session:
            graph_data = run_and_collect(session, cypher)

        answer = _summarize_results(message, graph_data)

        return jsonify({
            'cypher': cypher,
            'data': graph_data,
            'answer': answer,
        })
    except Exception as e:
        return jsonify({
            'cypher': cypher,
            'data': {'nodes': [], 'links': []},
            'answer': f'Cypher execution error: {str(e)}',
        })
