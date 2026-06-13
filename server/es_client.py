from elasticsearch import Elasticsearch
import os

ELASTICSEARCH_URL = os.environ.get('ELASTICSEARCH_URL', 'http://localhost:9200')
ELASTICSEARCH_USER = os.environ.get('ELASTICSEARCH_USER', 'elastic')
ELASTICSEARCH_PASSWORD = os.environ.get('ELASTICSEARCH_PASSWORD', 'changeme')

PAX_INDEX = 'pax_data'

_es = None


def get_es_client():
    global _es
    if _es is None:
        _es = Elasticsearch(
            ELASTICSEARCH_URL,
            basic_auth=(ELASTICSEARCH_USER, ELASTICSEARCH_PASSWORD),
        )
    return _es
