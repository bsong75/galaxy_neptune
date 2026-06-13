"""AWS Neptune client using openCypher with IAM (SigV4) authentication.

Uses HTTPS endpoint (not Bolt) since IAM auth requires signed requests.
Queries are sent via POST to the openCypher endpoint.

Required packages: boto3, requests, requests-aws4auth
"""
import os
import logging
import boto3
from requests_aws4auth import AWS4Auth
import requests

logger = logging.getLogger(__name__)

NEPTUNE_HOST = os.environ.get(
    'NEPTUNE_HOST', 'your-neptune-cluster.region.neptune.amazonaws.com'
)
NEPTUNE_PORT = os.environ.get('NEPTUNE_PORT', '8182')
NEPTUNE_REGION = os.environ.get('NEPTUNE_REGION', 'us-east-1')

NEPTUNE_URL = f'https://{NEPTUNE_HOST}:{NEPTUNE_PORT}/openCypher'


def _get_auth():
    """Get SigV4 auth using current IAM credentials (role, profile, or env vars)."""
    credentials = boto3.Session().get_credentials().get_frozen_credentials()
    return AWS4Auth(
        credentials.access_key,
        credentials.secret_key,
        NEPTUNE_REGION,
        'neptune-db',
        session_token=credentials.token,
    )


def run_query(cypher, parameters=None):
    """Execute an openCypher query against Neptune.

    Args:
        cypher: The Cypher query string
        parameters: Optional dict of query parameters

    Returns:
        dict with 'results' from Neptune's response
    """
    payload = {'query': cypher}
    if parameters:
        payload['parameters'] = parameters

    auth = _get_auth()
    resp = requests.post(
        NEPTUNE_URL,
        json=payload,
        auth=auth,
        headers={'Content-Type': 'application/json'},
    )
    resp.raise_for_status()
    return resp.json()


class NeptuneSession:
    """Wrapper that mimics neo4j session.run() interface for easier migration."""

    def run(self, cypher, **params):
        result = run_query(cypher, params if params else None)
        return NeptuneResult(result)


class NeptuneResult:
    """Wrapper around Neptune response to mimic neo4j Result interface."""

    def __init__(self, response):
        self._response = response
        self._results = response.get('results', [])

    def consume(self):
        """No-op for compatibility with neo4j driver pattern."""
        pass

    def single(self):
        if self._results:
            return self._results[0]
        return None

    def __iter__(self):
        return iter(self._results)


class NeptuneDriver:
    """Mimics neo4j Driver interface."""

    def session(self):
        return NeptuneSession()


_driver = None


def get_driver():
    global _driver
    if _driver is None:
        _driver = NeptuneDriver()
    return _driver
