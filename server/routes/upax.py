import os
import logging
from flask import Blueprint, jsonify
from neptune_client import get_driver
from s1_obtain_data import fetch_pax_data
from graph_builder import build_graph_for_pax, graph_is_fresh

logger = logging.getLogger(__name__)

upax_bp = Blueprint('upax', __name__)

REACT_APP_URL = os.environ.get('REACT_APP_URL', 'http://localhost:3005')


@upax_bp.route('/upax_data/<upid>/')
def get_upax_data(upid):
    """Fetch passenger data, build graph in Neo4j, return JSON summary.
    ---
    tags:
      - UPAX Data
    parameters:
      - name: upid
        in: path
        type: string
        required: true
        description: Unified Passenger ID
        example: "2349202"
    responses:
      200:
        description: Passenger data loaded and graph built successfully
      404:
        description: No data found for the given UPID
      500:
        description: Graph build failed
    """

    # 1. Fetch data from Elasticsearch (mock for now)
    pax_data = fetch_pax_data(upid)
    if pax_data is None:
        return jsonify({'status': 'NOT_FOUND', 'message': f'No data found for UPID: {upid}'}), 404

    # 2. Build the Neo4j graph (skip if a fresh one already exists)
    try:
        driver = get_driver()
        # if graph_is_fresh(driver, upid):
        #     logger.info(f"Graph for UPID {upid} is still fresh, skipping rebuild")
        # else:
        build_graph_for_pax(driver, pax_data)
    except Exception as e:
        logger.error(f"Graph build failed for UPID {upid}: {e}")
        return jsonify({'status': 'ERROR', 'message': f'Graph build failed: {str(e)}'}), 500

    # 3. Build JSON response
    def _format_seacat(sc):
        return {
            'enf_action_id': sc.get('ENF_ACTN_ID', ''),
            'incident_datetime': sc.get('NCDNT_DTTM', ''),
            'incident_id': sc.get('NCDNT_ID', ''),
            'incident_type': sc.get('NCDNT_TYP', ''),
        }

    def _format_visa(v):
        return {
            'type': v.get('TYPE', ''),
            'refusal_code': v.get('RFSL_CD', ''),
            'refusal_datetime': v.get('RFSL_DTTM', ''),
        }

    def _format_secondary(sec):
        return {
            'sub_transaction_type': sec.get('SUB_TRN_TYP', ''),
            'reason': sec.get('RSN_TXT', ''),
            'crossing_datetime': sec.get('CRSG_DTTM', ''),
            'referral_workspace_id': sec.get('RFRL_WRKSPC_ID_NBR', ''),
        }

    def _format_co_traveler(ct):
        return {
            'upid': ct.get('UNF_PSNGR_ID', ''),
            'first_name': ct.get('FRST_NM', ''),
            'last_name': ct.get('LST_NM', ''),
            'dob': ct.get('DOB_DT', ''),
            'seacats': [_format_seacat(sc) for sc in ct.get('SEACATS', [])],
            'visa': [_format_visa(v) for v in ct.get('VISA', [])],
            'secondary': [_format_secondary(s) for s in ct.get('SECONDARY', [])],
            'co_travelers': [
                _format_co_traveler(sub_ct)
                for sub_ct in ct.get('CO_TRAVELERS', [])
            ],
        }

    co_travelers = [_format_co_traveler(ct) for ct in pax_data.get('UNF_PRSN_CO_TRAVELERS', [])]

    return jsonify({
        'status': 'SUCCESS',
        'person': {
            'id': pax_data.get('UNF_PSNGR_ID', ''),
            'first_name': pax_data.get('FRST_NM', ''),
            'last_name': pax_data.get('LST_NM', ''),
            'dob': pax_data.get('DOB_DT', ''),
            'gender': pax_data.get('GNDR_CD', ''),
            'citizenship_country': pax_data.get('CTZNSHP_CTRY_CD', ''),
        },
        'seacats': [_format_seacat(sc) for sc in pax_data.get('SEACATS', [])],
        'co_travelers': co_travelers,
        'graph_url': f'{REACT_APP_URL}/person/{upid}',
    })
