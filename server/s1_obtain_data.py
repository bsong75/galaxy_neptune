import json
import os
import logging
import uuid
from datetime import datetime, timezone, timedelta

from es_client import get_es_client, PAX_INDEX

logger = logging.getLogger(__name__)

DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')

FRESHNESS_HOURS = 24


def fetch_pax_data(upid: str) -> dict | None:
    """Fetch passenger data by UPID.

    Checks Elasticsearch first for a fresh cached copy (< 24 hours).
    Falls back to {upid}_pax_data.json, then ingests into ES.
    """
    logger.info(f"Fetching pax data for UPID: {upid}")

    # 1. Try Elasticsearch first
    try:
        es = get_es_client()
        hit = _search_es(es, upid)
        if hit is not None:
            logger.info(f"Found fresh data in Elasticsearch for UPID: {upid}")
            return hit
    except Exception as e:
        logger.warning(f"Elasticsearch lookup failed, falling back to file: {e}")

    # 2. Fallback to JSON file
    raw = _load_from_file(upid)
    if raw is None:
        return None

    # 3. Ingest into ES for next time
    try:
        es = get_es_client()
        _ingest_to_es(es, upid, raw)
    except Exception as e:
        logger.warning(f"Failed to ingest into Elasticsearch: {e}")

    return raw


def _search_es(es, upid: str) -> dict | None:
    """Search ES for a fresh document matching this UPID."""
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=FRESHNESS_HOURS)).isoformat()

    result = es.search(
        index=PAX_INDEX,
        body={
            'query': {
                'bool': {
                    'must': [
                        {'term': {'UNF_PSNGR_ID': str(upid)}},
                        {'range': {'ingested_ts': {'gte': cutoff}}},
                    ]
                }
            },
            'size': 1,
        },
        ignore=[404],
    )

    hits = result.get('hits', {}).get('hits', [])
    if not hits:
        return None

    source = hits[0]['_source']
    # Remove metadata fields before returning
    source.pop('doc_id', None)
    source.pop('ingested_ts', None)
    return source


def _load_from_file(upid: str) -> dict | None:
    """Load passenger data from {upid}_pax_data.json."""
    filepath = os.path.join(DATA_DIR, f"{upid}_pax_data.json")
    if not os.path.exists(filepath):
        logger.warning(f"No data file found for UPID: {upid} (expected {filepath})")
        return None

    try:
        with open(filepath, 'r') as f:
            data = json.load(f)
        logger.info(f"Loaded data from {filepath}")
        return data
    except (json.JSONDecodeError, IOError) as e:
        logger.error(f"Error reading {filepath}: {e}")
        return None


_es_index_verified = False

INDEX_MAPPING = {
    'mappings': {
        'properties': {
            'UNF_PSNGR_ID': {'type': 'keyword'},
            'FRST_NM': {'type': 'keyword'},
            'LST_NM': {'type': 'keyword'},
            'DOB_DT': {'type': 'keyword'},
            'CTZNSHP_CTRY_CD': {'type': 'keyword'},
            'GNDR_CD': {'type': 'keyword'},
            'doc_id': {'type': 'keyword'},
            'ingested_ts': {'type': 'date'},
            'BIRTH_LOC': {'type': 'object', 'enabled': False},
            'PHONE_NUMBERS': {'type': 'object', 'enabled': False},
            'ADDRESSES': {'type': 'object', 'enabled': False},
            'SEACATS': {'type': 'object', 'enabled': False},
            'UNF_PRSN_CO_TRAVELERS': {'type': 'object', 'enabled': False},
        },
    },
}


def _ensure_index(es) -> None:
    """Ensure the pax_data index exists with the correct mapping.

    If the index has a bad mapping (e.g. auto-mapped nested fields),
    it is deleted and recreated with the correct explicit mapping.
    """
    global _es_index_verified
    if _es_index_verified:
        return

    if es.indices.exists(index=PAX_INDEX):
        # Verify the mapping is correct (UNF_PRSN_CO_TRAVELERS should have enabled=false)
        mapping = es.indices.get_mapping(index=PAX_INDEX)
        props = mapping[PAX_INDEX]['mappings'].get('properties', {})
        co_trav = props.get('UNF_PRSN_CO_TRAVELERS', {})
        if co_trav.get('enabled') is False:
            _es_index_verified = True
            return
        # Bad mapping — delete and recreate
        logger.warning(f"Index {PAX_INDEX} has incorrect mapping, recreating")
        es.indices.delete(index=PAX_INDEX)

    es.indices.create(index=PAX_INDEX, body=INDEX_MAPPING)
    _es_index_verified = True
    logger.info(f"Created Elasticsearch index: {PAX_INDEX}")


def _ingest_to_es(es, upid: str, data: dict) -> None:
    """Index passenger data into Elasticsearch with metadata."""
    _ensure_index(es)

    doc_id = str(uuid.uuid4())
    doc = {
        **data,
        'doc_id': doc_id,
        'ingested_ts': datetime.now(timezone.utc).isoformat(),
    }

    es.index(index=PAX_INDEX, id=doc_id, body=doc)
    logger.info(f"Ingested UPID {upid} into Elasticsearch (doc_id: {doc_id})")