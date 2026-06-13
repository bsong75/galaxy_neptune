# Galaxy Neptune

Graph-based passenger network explorer. Builds a graph in Amazon Neptune from passenger data and visualizes it with a React force-graph frontend.

## Architecture

| Service | Container | Port |
|---------|-----------|------|
| Amazon Neptune | AWS managed | openCypher endpoint: `8182` |
| Flask API | `flask_api` | `5000` |
| React Frontend | `react_front` | `3005` |

## Prerequisites

- Docker & Docker Compose
- AWS credentials with access to a Neptune cluster

## Quick Start

```bash
# Build and start all containers
docker compose up --build -d
```

## Usage

### Step 1 — Load data into Neptune

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
| GET | `/api/upax_data/<upid>/` | Load passenger data into Neptune |
| GET | `/api/graph/core?upid=<upid>` | Core graph (passenger + associates + derogs) |
| GET | `/api/graph/full?upid=<upid>` | Full graph (all node types) |
| GET | `/api/graph/details?upid=<upid>` | Full graph for detail expansion |
| GET | `/api/graph/person/<id>?upid=<upid>` | Single passenger + 1-hop neighbors |
| GET | `/api/graph/expand/<element_id>?upid=<upid>` | Expand a node's neighbors |
| GET | `/api/graph/search?q=<query>&upid=<upid>` | Search passengers by ID/name |
| GET | `/api/graph/filter?upid=<upid>&nodeTypes=...&relTypes=...` | Filtered graph |
| POST | `/api/graph/cypher` | Run a read-only openCypher query |
| POST | `/api/graph/summarize` | AI summary of graph data (requires GROQ_API_KEY) |
| GET | `/api/graph/schema` | Available node labels and relationship types |

## Stopping

```bash
docker compose down
```

To also remove data volumes:

```bash
docker compose down -v
```
