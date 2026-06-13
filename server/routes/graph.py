import os
import requests as http_requests
from flask import Blueprint, jsonify, request
from neptune_client import get_driver

graph_bp = Blueprint('graph', __name__)

NODE_COLORS = {
    'MainPassenger': '#4CAF50',
    'Phone': '#2196F3',
    'Country': '#00BCD4',
    'BirthLocation': '#F44336',
    'Address': '#9C27B0',
    'AssociatedPerson': '#8BC34A',
    'Seacat': '#E91E63',
    'Visa': '#FF9800',
    'Secondary': '#607D8B',
}

NODE_SIZES = {
    'MainPassenger': 12,
}


def node_to_dict(node):
    """Convert a graph node to a dict for react-force-graph."""
    labels = list(node.labels)
    label = labels[0] if labels else 'Unknown'
    props = {}
    for key, val in dict(node).items():
        # Skip internal tracking fields from the response
        if key in ('upid', 'created_at'):
            continue
        if hasattr(val, 'isoformat'):
            props[key] = val.isoformat()
        else:
            props[key] = val
    return {
        'id': node.element_id,
        'label': label,
        'properties': props,
        'color': NODE_COLORS.get(label, '#999999'),
        'val': NODE_SIZES.get(label, 6),
    }


def run_and_collect(session, cypher, **params):
    """Run a Cypher query and convert results to {nodes, links} while session is open."""
    nodes_map = {}
    links = []

    result = session.run(cypher, **params)
    for record in result:
        n = record.get('n')
        r = record.get('r')
        m = record.get('m')

        if n is not None:
            nodes_map[n.element_id] = node_to_dict(n)
        if m is not None:
            nodes_map[m.element_id] = node_to_dict(m)
        if r is not None:
            links.append({
                'source': r.start_node.element_id,
                'target': r.end_node.element_id,
                'type': r.type,
            })

    return {'nodes': list(nodes_map.values()), 'links': links}


def _get_upid():
    """Extract upid from query params. Returns None if not provided."""
    return request.args.get('upid', None)


@graph_bp.route('/graph/full')
def get_full_graph():
    """Get the full graph for a given UPID.
    ---
    tags:
      - Graph
    parameters:
      - name: upid
        in: query
        type: string
        required: true
        description: Unified Passenger ID
        example: "2349202"
      - name: limit
        in: query
        type: integer
        required: false
        description: Max number of results
    responses:
      200:
        description: Graph data with nodes and links
      400:
        description: Missing upid parameter
    """
    upid = _get_upid()
    if not upid:
        return jsonify({'error': 'upid parameter is required'}), 400

    limit = request.args.get('limit', None, type=int)
    driver = get_driver()

    cypher = """
        MATCH (n) WHERE n.upid = $upid
        OPTIONAL MATCH (n)-[r]->(m) WHERE m.upid = $upid
        RETURN n, r, m
    """
    params = {'upid': upid}
    if limit:
        cypher += " LIMIT $limit"
        params['limit'] = limit

    with driver.session() as session:
        data = run_and_collect(session, cypher, **params)

    return jsonify(data)


@graph_bp.route('/graph/core')
def get_core_graph():
    """Get MainPassenger, AssociatedPerson, Seacat, Visa, and Secondary nodes for a UPID.
    ---
    tags:
      - Graph
    parameters:
      - name: upid
        in: query
        type: string
        required: true
        description: Unified Passenger ID
        example: "2349202"
    responses:
      200:
        description: Core graph data (passengers, co-travelers, seacats, visa, secondary)
      400:
        description: Missing upid parameter
    """
    upid = _get_upid()
    if not upid:
        return jsonify({'error': 'upid parameter is required'}), 400

    driver = get_driver()

    nodes_map = {}
    links = []

    with driver.session() as session:
        # MainPassenger + co-traveler relationships
        d1 = run_and_collect(session, """
            MATCH (mp:MainPassenger) WHERE mp.upid = $upid
            OPTIONAL MATCH (mp)-[r:CO_TRAVELER]->(ap:AssociatedPerson) WHERE ap.upid = $upid
            RETURN mp AS n, r, ap AS m
        """, upid=upid)
        # MainPassenger seacats
        d2 = run_and_collect(session, """
            MATCH (mp:MainPassenger)-[r:HAS_SEACAT]->(s:Seacat)
            WHERE mp.upid = $upid AND s.upid = $upid
            RETURN mp AS n, r, s AS m
        """, upid=upid)
        # AssociatedPerson seacats
        d3 = run_and_collect(session, """
            MATCH (ap:AssociatedPerson)-[r:HAS_SEACAT]->(s:Seacat)
            WHERE ap.upid = $upid AND s.upid = $upid
            RETURN ap AS n, r, s AS m
        """, upid=upid)
        # AssociatedPerson -> AssociatedPerson (nested co-travelers)
        d4 = run_and_collect(session, """
            MATCH (ap1:AssociatedPerson)-[r:CO_TRAVELER]->(ap2:AssociatedPerson)
            WHERE ap1.upid = $upid AND ap2.upid = $upid
            RETURN ap1 AS n, r, ap2 AS m
        """, upid=upid)
        # AssociatedPerson visa records
        d5 = run_and_collect(session, """
            MATCH (ap:AssociatedPerson)-[r:HAS_VISA]->(v:Visa)
            WHERE ap.upid = $upid AND v.upid = $upid
            RETURN ap AS n, r, v AS m
        """, upid=upid)
        # AssociatedPerson secondary records
        d6 = run_and_collect(session, """
            MATCH (ap:AssociatedPerson)-[r:HAS_SECONDARY]->(s:Secondary)
            WHERE ap.upid = $upid AND s.upid = $upid
            RETURN ap AS n, r, s AS m
        """, upid=upid)

    # Merge all results
    for dataset in [d1, d2, d3, d4, d5, d6]:
        for node in dataset['nodes']:
            nodes_map[node['id']] = node
        links.extend(dataset['links'])

    # Deduplicate links
    seen = set()
    unique_links = []
    for link in links:
        key = f"{link['source']}-{link['type']}-{link['target']}"
        if key not in seen:
            seen.add(key)
            unique_links.append(link)

    return jsonify({'nodes': list(nodes_map.values()), 'links': unique_links})


@graph_bp.route('/graph/flagged')
def get_flagged_graph():
    """Level 1: MainPassenger + only co-travelers with SEACAT/VISA/SECONDARY flags
    (or bridge co-travelers whose nested co-travelers have flags).
    ---
    tags:
      - Graph
    parameters:
      - name: upid
        in: query
        type: string
        required: true
        description: Unified Passenger ID
    responses:
      200:
        description: Flagged network graph
      400:
        description: Missing upid parameter
    """
    upid = _get_upid()
    if not upid:
        return jsonify({'error': 'upid parameter is required'}), 400

    driver = get_driver()

    nodes_map = {}
    links = []

    with driver.session() as session:
        # MainPassenger (always shown)
        d_mp = run_and_collect(session, """
            MATCH (mp:MainPassenger) WHERE mp.upid = $upid
            RETURN mp AS n, null AS r, null AS m
        """, upid=upid)

        # MainPassenger seacats
        d_mp_sc = run_and_collect(session, """
            MATCH (mp:MainPassenger)-[r:HAS_SEACAT]->(s:Seacat)
            WHERE mp.upid = $upid AND s.upid = $upid
            RETURN mp AS n, r, s AS m
        """, upid=upid)

        # Direct co-travelers who have flags themselves
        d_flagged = run_and_collect(session, """
            MATCH (mp:MainPassenger)-[r:CO_TRAVELER]->(ap:AssociatedPerson)
            WHERE mp.upid = $upid AND ap.upid = $upid
              AND (size((ap)-[:HAS_SEACAT]->()) > 0
                OR size((ap)-[:HAS_VISA]->()) > 0
                OR size((ap)-[:HAS_SECONDARY]->()) > 0)
            RETURN mp AS n, r, ap AS m
        """, upid=upid)

        # Direct co-travelers who are "bridges" — they don't have flags but their
        # nested co-travelers do
        d_bridge = run_and_collect(session, """
            MATCH (mp:MainPassenger)-[r:CO_TRAVELER]->(ap:AssociatedPerson)
            WHERE mp.upid = $upid AND ap.upid = $upid
              AND size((ap)-[:HAS_SEACAT]->()) = 0
              AND size((ap)-[:HAS_VISA]->()) = 0
              AND size((ap)-[:HAS_SECONDARY]->()) = 0
              AND (size((ap)-[:CO_TRAVELER]->(:AssociatedPerson)-[:HAS_SEACAT]->()) > 0
                OR size((ap)-[:CO_TRAVELER]->(:AssociatedPerson)-[:HAS_VISA]->()) > 0
                OR size((ap)-[:CO_TRAVELER]->(:AssociatedPerson)-[:HAS_SECONDARY]->()) > 0)
            RETURN mp AS n, r, ap AS m
        """, upid=upid)

        # Nested co-travelers who have flags (and their parent link)
        d_nested_flagged = run_and_collect(session, """
            MATCH (ap1:AssociatedPerson)-[r:CO_TRAVELER]->(ap2:AssociatedPerson)
            WHERE ap1.upid = $upid AND ap2.upid = $upid
              AND (size((ap2)-[:HAS_SEACAT]->()) > 0
                OR size((ap2)-[:HAS_VISA]->()) > 0
                OR size((ap2)-[:HAS_SECONDARY]->()) > 0)
            RETURN ap1 AS n, r, ap2 AS m
        """, upid=upid)

        # Flag nodes (SEACAT/VISA/SECONDARY) for all shown AssociatedPersons
        d_sc = run_and_collect(session, """
            MATCH (ap:AssociatedPerson)-[r:HAS_SEACAT]->(s:Seacat)
            WHERE ap.upid = $upid AND s.upid = $upid
            RETURN ap AS n, r, s AS m
        """, upid=upid)
        d_vi = run_and_collect(session, """
            MATCH (ap:AssociatedPerson)-[r:HAS_VISA]->(v:Visa)
            WHERE ap.upid = $upid AND v.upid = $upid
            RETURN ap AS n, r, v AS m
        """, upid=upid)
        d_sec = run_and_collect(session, """
            MATCH (ap:AssociatedPerson)-[r:HAS_SECONDARY]->(s:Secondary)
            WHERE ap.upid = $upid AND s.upid = $upid
            RETURN ap AS n, r, s AS m
        """, upid=upid)

    # Collect all flagged/bridge person IDs to filter flag nodes
    all_datasets = [d_mp, d_mp_sc, d_flagged, d_bridge, d_nested_flagged, d_sc, d_vi, d_sec]

    # First pass: collect shown person element IDs
    shown_person_ids = set()
    for dataset in [d_mp, d_flagged, d_bridge, d_nested_flagged]:
        for node in dataset['nodes']:
            if node['label'] in ('MainPassenger', 'AssociatedPerson'):
                shown_person_ids.add(node['id'])

    # Second pass: merge nodes/links, only include flag nodes connected to shown persons
    for dataset in all_datasets:
        for node in dataset['nodes']:
            if node['label'] in ('MainPassenger', 'AssociatedPerson'):
                if node['id'] in shown_person_ids:
                    nodes_map[node['id']] = node
            elif node['label'] in ('Seacat', 'Visa', 'Secondary'):
                nodes_map[node['id']] = node
            else:
                nodes_map[node['id']] = node
        for link in dataset['links']:
            links.append(link)

    # Filter: only keep links where both source and target are in nodes_map
    # and only keep flag nodes connected to shown persons
    final_nodes = {}
    valid_links = []
    for link in links:
        src = link['source']
        tgt = link['target']
        if src in nodes_map and tgt in nodes_map:
            # For flag links, ensure the person end is a shown person
            if link['type'] in ('HAS_SEACAT', 'HAS_VISA', 'HAS_SECONDARY'):
                if src in shown_person_ids:
                    valid_links.append(link)
                    final_nodes[src] = nodes_map[src]
                    final_nodes[tgt] = nodes_map[tgt]
            elif link['type'] == 'CO_TRAVELER':
                if src in shown_person_ids and tgt in shown_person_ids:
                    valid_links.append(link)
                    final_nodes[src] = nodes_map[src]
                    final_nodes[tgt] = nodes_map[tgt]
            else:
                valid_links.append(link)
                final_nodes[src] = nodes_map[src]
                final_nodes[tgt] = nodes_map[tgt]

    # Always include MainPassenger even if no links
    for node in d_mp['nodes']:
        final_nodes[node['id']] = node

    # Deduplicate links
    seen = set()
    unique_links = []
    for link in valid_links:
        key = f"{link['source']}-{link['type']}-{link['target']}"
        if key not in seen:
            seen.add(key)
            unique_links.append(link)

    return jsonify({'nodes': list(final_nodes.values()), 'links': unique_links})


@graph_bp.route('/graph/people')
def get_people_graph():
    """Level 2: All people + their SEACAT/VISA/SECONDARY flags (no phones, addresses, etc.).
    ---
    tags:
      - Graph
    parameters:
      - name: upid
        in: query
        type: string
        required: true
        description: Unified Passenger ID
    responses:
      200:
        description: All people graph with flags
      400:
        description: Missing upid parameter
    """
    upid = _get_upid()
    if not upid:
        return jsonify({'error': 'upid parameter is required'}), 400

    driver = get_driver()

    nodes_map = {}
    links = []

    with driver.session() as session:
        # MainPassenger + direct co-travelers
        d1 = run_and_collect(session, """
            MATCH (mp:MainPassenger) WHERE mp.upid = $upid
            OPTIONAL MATCH (mp)-[r:CO_TRAVELER]->(ap:AssociatedPerson) WHERE ap.upid = $upid
            RETURN mp AS n, r, ap AS m
        """, upid=upid)
        # Nested co-travelers (AP -> AP)
        d2 = run_and_collect(session, """
            MATCH (ap1:AssociatedPerson)-[r:CO_TRAVELER]->(ap2:AssociatedPerson)
            WHERE ap1.upid = $upid AND ap2.upid = $upid
            RETURN ap1 AS n, r, ap2 AS m
        """, upid=upid)
        # MainPassenger seacats
        d3 = run_and_collect(session, """
            MATCH (mp:MainPassenger)-[r:HAS_SEACAT]->(s:Seacat)
            WHERE mp.upid = $upid AND s.upid = $upid
            RETURN mp AS n, r, s AS m
        """, upid=upid)
        # AssociatedPerson seacats
        d4 = run_and_collect(session, """
            MATCH (ap:AssociatedPerson)-[r:HAS_SEACAT]->(s:Seacat)
            WHERE ap.upid = $upid AND s.upid = $upid
            RETURN ap AS n, r, s AS m
        """, upid=upid)
        # AssociatedPerson visa records
        d5 = run_and_collect(session, """
            MATCH (ap:AssociatedPerson)-[r:HAS_VISA]->(v:Visa)
            WHERE ap.upid = $upid AND v.upid = $upid
            RETURN ap AS n, r, v AS m
        """, upid=upid)
        # AssociatedPerson secondary records
        d6 = run_and_collect(session, """
            MATCH (ap:AssociatedPerson)-[r:HAS_SECONDARY]->(s:Secondary)
            WHERE ap.upid = $upid AND s.upid = $upid
            RETURN ap AS n, r, s AS m
        """, upid=upid)

    for dataset in [d1, d2, d3, d4, d5, d6]:
        for node in dataset['nodes']:
            nodes_map[node['id']] = node
        links.extend(dataset['links'])

    # Deduplicate links
    seen = set()
    unique_links = []
    for link in links:
        key = f"{link['source']}-{link['type']}-{link['target']}"
        if key not in seen:
            seen.add(key)
            unique_links.append(link)

    return jsonify({'nodes': list(nodes_map.values()), 'links': unique_links})


@graph_bp.route('/graph/details')
def get_detail_graph():
    """Get the full graph for a UPID (for expanding from the core view).
    ---
    tags:
      - Graph
    parameters:
      - name: upid
        in: query
        type: string
        required: true
        description: Unified Passenger ID
        example: "2349202"
    responses:
      200:
        description: Full detail graph data
      400:
        description: Missing upid parameter
    """
    upid = _get_upid()
    if not upid:
        return jsonify({'error': 'upid parameter is required'}), 400

    driver = get_driver()

    with driver.session() as session:
        data = run_and_collect(session, """
            MATCH (n) WHERE n.upid = $upid
            OPTIONAL MATCH (n)-[r]->(m) WHERE m.upid = $upid
            RETURN n, r, m
        """, upid=upid)

    return jsonify(data)


@graph_bp.route('/graph/person/<person_id>')
def get_person(person_id):
    """Get a MainPassenger and their 1-hop neighbors.
    ---
    tags:
      - Graph
    parameters:
      - name: person_id
        in: path
        type: string
        required: true
        description: MainPassenger ID
        example: "2349202"
      - name: upid
        in: query
        type: string
        required: false
        description: Scope results to a specific UPID
    responses:
      200:
        description: Person node and connected neighbors
    """
    upid = _get_upid()
    driver = get_driver()

    params = {'person_id': person_id}
    if upid:
        params['upid'] = upid
        cypher = """
            MATCH (n:MainPassenger) WHERE n.id = $person_id
            OPTIONAL MATCH (n)-[r]-(m) WHERE m.upid = $upid
            RETURN n, r, m
        """
    else:
        cypher = """
            MATCH (n:MainPassenger) WHERE n.id = $person_id
            OPTIONAL MATCH (n)-[r]-(m)
            RETURN n, r, m
        """

    with driver.session() as session:
        data = run_and_collect(session, cypher, **params)

    return jsonify(data)


@graph_bp.route('/graph/expand/<path:element_id>')
def expand_node(element_id):
    """Expand a node's neighbors by element ID.
    ---
    tags:
      - Graph
    parameters:
      - name: element_id
        in: path
        type: string
        required: true
        description: Element ID of the node to expand
      - name: upid
        in: query
        type: string
        required: false
        description: Scope results to a specific UPID
    responses:
      200:
        description: Expanded node with its neighbors
    """
    upid = _get_upid()
    driver = get_driver()

    params = {'element_id': element_id}
    if upid:
        params['upid'] = upid

    cypher = """
        MATCH (n) WHERE id(n) = $element_id
        OPTIONAL MATCH (n)-[r]-(m)
    """
    if upid:
        cypher = """
            MATCH (n) WHERE id(n) = $element_id
            OPTIONAL MATCH (n)-[r]-(m) WHERE m.upid = $upid
        """
    cypher += " RETURN n, r, m"

    with driver.session() as session:
        data = run_and_collect(session, cypher, **params)

    return jsonify(data)


@graph_bp.route('/graph/search')
def search_graph():
    """Search for MainPassenger by id or name within a UPID.
    ---
    tags:
      - Graph
    parameters:
      - name: q
        in: query
        type: string
        required: true
        description: Search query (matches ID, first name, or last name)
        example: "SMITH"
      - name: upid
        in: query
        type: string
        required: false
        description: Scope search to a specific UPID
    responses:
      200:
        description: Matching passengers and their connections
    """
    q = request.args.get('q', '')
    upid = _get_upid()

    if not q:
        return jsonify({'nodes': [], 'links': []})

    driver = get_driver()
    params = {'q': q}

    params['q_lower'] = q.lower()

    if upid:
        params['upid'] = upid
        cypher = """
            MATCH (n) WHERE n.upid = $upid
              AND (n:MainPassenger OR n:AssociatedPerson)
              AND (n.id CONTAINS $q
                OR toLower(n.first_name) CONTAINS $q_lower
                OR toLower(n.last_name) CONTAINS $q_lower
                OR n.unf_psngr_id CONTAINS $q)
            OPTIONAL MATCH (n)-[r]-(m) WHERE m.upid = $upid
            RETURN n, r, m
        """
    else:
        cypher = """
            MATCH (n)
            WHERE (n:MainPassenger OR n:AssociatedPerson)
              AND (n.id CONTAINS $q
                OR toLower(n.first_name) CONTAINS $q_lower
                OR toLower(n.last_name) CONTAINS $q_lower
                OR n.unf_psngr_id CONTAINS $q)
            OPTIONAL MATCH (n)-[r]-(m)
            RETURN n, r, m
        """

    with driver.session() as session:
        data = run_and_collect(session, cypher, **params)

    return jsonify(data)


@graph_bp.route('/graph/filter')
def filter_graph():
    """Filter graph by node types, relationship types for a UPID.
    ---
    tags:
      - Graph
    parameters:
      - name: upid
        in: query
        type: string
        required: true
        description: Unified Passenger ID
        example: "2349202"
      - name: nodeTypes
        in: query
        type: string
        required: false
        description: Comma-separated node labels to include (e.g. "MainPassenger,Seacat")
      - name: relTypes
        in: query
        type: string
        required: false
        description: Comma-separated relationship types to include (e.g. "HAS_SEACAT,CO_TRAVELER")
      - name: limit
        in: query
        type: integer
        required: false
        description: Max number of results
    responses:
      200:
        description: Filtered graph data
      400:
        description: Missing upid parameter
    """
    upid = _get_upid()
    if not upid:
        return jsonify({'error': 'upid parameter is required'}), 400

    node_types = request.args.get('nodeTypes', '')
    rel_types = request.args.get('relTypes', '')
    limit = request.args.get('limit', None, type=int)

    node_type_list = [t.strip() for t in node_types.split(',') if t.strip()] if node_types else []
    rel_type_list = [t.strip() for t in rel_types.split(',') if t.strip()] if rel_types else []

    driver = get_driver()

    # Build dynamic Cypher based on filters
    where_clauses = ['n.upid = $upid']
    params = {'upid': upid}
    if limit:
        params['limit'] = limit

    if node_type_list:
        label_checks = ' OR '.join([f'"{label}" IN labels(n)' for label in node_type_list])
        where_clauses.append(f'({label_checks})')

    cypher = "MATCH (n)"
    cypher += " WHERE " + " AND ".join(where_clauses)
    cypher += " OPTIONAL MATCH (n)-[r]->(m) WHERE m.upid = $upid"

    if rel_type_list:
        rel_checks = ' OR '.join([f'type(r) = "{rt}"' for rt in rel_type_list])
        cypher += f" AND ({rel_checks})"

    limit_clause = " LIMIT $limit" if limit else ""
    cypher += f" RETURN n, r, m{limit_clause}"

    with driver.session() as session:
        data = run_and_collect(session, cypher, **params)

    return jsonify(data)


@graph_bp.route('/graph/cypher', methods=['POST'])
def run_cypher():
    """Execute a read-only Cypher query and return graph results.
    ---
    tags:
      - Graph
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          required:
            - cypher
          properties:
            cypher:
              type: string
              description: Cypher query to execute (read-only)
              example: "MATCH (n:MainPassenger)-[r]->(m) RETURN n, r, m LIMIT 10"
    responses:
      200:
        description: Graph data from the query
      400:
        description: Missing cypher or destructive operation blocked
    """
    data = request.get_json()
    cypher = data.get('cypher', '')

    if not cypher:
        return jsonify({'error': 'No cypher provided'}), 400

    # Safety check: block destructive operations
    cypher_upper = cypher.upper()
    if any(word in cypher_upper for word in ['DELETE', 'REMOVE', 'DROP', 'SET ', 'CREATE', 'MERGE']):
        return jsonify({'error': 'Only read operations are allowed.'}), 400

    try:
        driver = get_driver()
        with driver.session() as session:
            graph_data = run_and_collect(session, cypher)
        return jsonify(graph_data)
    except Exception as e:
        return jsonify({'error': f'Cypher error: {str(e)}'}), 400


@graph_bp.route('/graph/summarize', methods=['POST'])
def summarize_graph():
    """Generate an AI summary of the graph data.
    ---
    tags:
      - Graph
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          properties:
            nodes:
              type: array
              description: List of graph nodes to summarize
              items:
                type: object
    responses:
      200:
        description: AI-generated summary of the graph
    """
    data = request.get_json()
    nodes = data.get('nodes', [])

    if not nodes:
        return jsonify({'summary': 'No graph data to summarize.'})

    groq_key = os.environ.get('GROQ_API_KEY', '')
    if not groq_key:
        return jsonify({'summary': 'AI summary unavailable (GROQ_API_KEY not set).'})

    # Build compact summary for the LLM
    # Sort so flag nodes (Seacat, Visa, Secondary) come first to avoid being cut off
    label_priority = {'MainPassenger': 0, 'Seacat': 1, 'Visa': 2, 'Secondary': 3, 'AssociatedPerson': 4}
    sorted_nodes = sorted(nodes, key=lambda n: label_priority.get(n.get('label', ''), 9))

    node_summaries = []
    for node in sorted_nodes[:40]:
        props = {k: v for k, v in node.get('properties', {}).items()}
        props['_type'] = node.get('label', 'Unknown')
        node_summaries.append(props)

    prompt = """You are an intelligence analyst assistant. Given graph data about a passenger and their connections, provide a brief executive summary.

The data contains items with a "_type" field indicating what kind of record it is:
- "_type": "MainPassenger" — the primary subject
- "_type": "AssociatedPerson" — a co-traveler (connected person)
- "_type": "Seacat" — a SEACAT record (seizure/enforcement action). Look for fields: incident_type, incident_id, enf_action_id
- "_type": "Visa" — a VISA refusal record. Look for fields: type, refusal_code, refusal_datetime
- "_type": "Secondary" — a SECONDARY inspection record. Look for fields: sub_transaction_type, reason, crossing_datetime

Format your response as follows:
1. One opening sentence with the main passenger's name and key identifiers.
2. A bullet point list for SEACAT records (seizure/enforcement actions), one bullet per record:
   - Include the incident type and ID
3. A bullet point list for VISA refusal records, if any.
4. A bullet point list for SECONDARY inspection records, if any.
5. One closing sentence summarizing co-travelers count.

If no records exist for a category, skip that section entirely. Do NOT say "not available" — just omit it.
Use bullet points (•) for each list. Be concise and factual. Do NOT mention graph databases, nodes, or technical terms — write as if briefing an analyst."""

    try:
        resp = http_requests.post(
            'https://api.groq.com/openai/v1/chat/completions',
            headers={
                'Authorization': f'Bearer {groq_key}',
                'Content-Type': 'application/json',
            },
            json={
                'model': os.environ.get('GROQ_MODEL', 'llama-3.3-70b-versatile'),
                'messages': [
                    {'role': 'system', 'content': prompt},
                    {'role': 'user', 'content': f'Graph data ({len(nodes)} items): {node_summaries}'},
                ],
                'temperature': 0,
            },
            timeout=30,
        )
        resp.raise_for_status()
        summary = resp.json()['choices'][0]['message']['content']
        return jsonify({'summary': summary})
    except Exception as e:
        return jsonify({'summary': f'Summary generation failed: {str(e)}'})


@graph_bp.route('/graph/schema')
def get_schema():
    """Return available node labels and relationship types.
    ---
    tags:
      - Graph
    responses:
      200:
        description: Node labels, relationship types, and color mapping
    """
    driver = get_driver()

    with driver.session() as session:
        labels_result = session.run("MATCH (n) RETURN DISTINCT labels(n) AS label")
        labels = []
        for record in labels_result:
            for l in record['label']:
                if l not in labels:
                    labels.append(l)

        rel_result = session.run("MATCH ()-[r]->() RETURN DISTINCT type(r) AS relationshipType")
        rel_types = [record['relationshipType'] for record in rel_result]

    return jsonify({
        'nodeLabels': labels,
        'relationshipTypes': rel_types,
        'nodeColors': NODE_COLORS,
    })
