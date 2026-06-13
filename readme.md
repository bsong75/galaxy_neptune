# Neo4j Galaxy

Graph-based passenger network explorer. Builds a Neo4j graph from passenger data and visualizes it with a React force-graph frontend.

## Architecture

| Service | Container | Port |
|---------|-----------|------|
| Neo4j | `neo4j_instance` | Browser: `7475`, Bolt: `7688` |
| Flask API | `flask_api` | `5000` |
| React Frontend | `react_front` | `3005` |

## Prerequisites

- Docker & Docker Compose

## Quick Start

```bash
# Build and start all containers
docker compose up --build -d
```

## Usage

### Step 1 — Load data into Neo4j

Call the upax endpoint with a UPID to fetch mock passenger data and build the graph:

```
http://localhost:3005/api/upax_data/2349202/
```

You should get a JSON response with `"status": "SUCCESS"`.

### Step 2 — View the graph

Navigate to the person URL (returned as `graph_url` in the step 1 response):

```
http://localhost:3005/person/2349202
```

The graph auto-loads with the core network (MainPassenger, AssociatedPersons, Derogs).

### Available UPIDs (mock data)

| UPID | Name |
|------|------|
| `2349202` | JOHN SMITH |

### Frontend Controls

- **Load PAX Network** — reload the core graph
- **Show All Details** — expand to show all node types (documents, phones, addresses, aliases, etc.)
- **Hide Details** — collapse back to core view
- **Search** — find passengers by ID or name
- **Filters** — filter by node type, relationship type, or date range
- **Chat panel** — ask questions or run Cypher queries against the graph
- **Theme toggle** — switch between dark and light mode

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/upax_data/<upid>/` | Load passenger data into Neo4j |
| GET | `/api/graph/core?upid=<upid>` | Core graph (passenger + associates + derogs) |
| GET | `/api/graph/full?upid=<upid>` | Full graph (all node types) |
| GET | `/api/graph/details?upid=<upid>` | Full graph for detail expansion |
| GET | `/api/graph/person/<id>?upid=<upid>` | Single passenger + 1-hop neighbors |
| GET | `/api/graph/expand/<element_id>?upid=<upid>` | Expand a node's neighbors |
| GET | `/api/graph/search?q=<query>&upid=<upid>` | Search passengers by ID/name |
| GET | `/api/graph/filter?upid=<upid>&nodeTypes=...&relTypes=...` | Filtered graph |
| POST | `/api/graph/cypher` | Run a read-only Cypher query |
| POST | `/api/graph/summarize` | AI summary of graph data (requires GROQ_API_KEY) |
| GET | `/api/graph/schema` | Available node labels and relationship types |

## Neo4j Browser

Access the Neo4j browser directly at `http://localhost:7475`. Connect with:
- Username: `neo4j`
- Password: `password`

## Stopping

```bash
docker compose down
```

To also remove the Neo4j data volume:

```bash
docker compose down -v
```
