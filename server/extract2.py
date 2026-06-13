"""Fetch passenger data from API and build the pax JSON file.

Flow:
1. Lookup main passenger by UPID -> get their info + UNF_PRSN_CO_TRAVELERS (name+DOB only)
2. For each co-traveler, search by name+DOB -> get full record including their own co-travelers
3. For each nested co-traveler, search by name+DOB -> get full record (2 levels deep only)

Steps 2 and 3 use asyncio + aiohttp for concurrent API calls.
"""

import os
import json
import logging
import asyncio
import aiohttp

logger = logging.getLogger(__name__)

BASE_URL = os.environ.get('PAX_API_URL', 'http://localhost:8080')
API_KEY = os.environ.get('PAX_API_KEY', '')
DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data')
MAX_CONCURRENT = int(os.environ.get('PAX_MAX_CONCURRENT', '20'))

HEADERS = {'x-api-key': API_KEY} if API_KEY else {}


async def fetch_main_passenger(session, upid):
    """Step 1: Fetch main passenger record by UPID."""
    async with session.get(f'{BASE_URL}/up/doc', params={'upid': upid},
                           headers=HEADERS, timeout=aiohttp.ClientTimeout(total=30)) as resp:
        resp.raise_for_status()
        return await resp.json()


async def search_person(session, semaphore, first_name, last_name, dob):
    """Search for a person by name and DOB. Returns the first match or None."""
    dob_formatted = dob.replace("-", "")[:8]
    params = {
        'first_name': first_name,
        'last_name': last_name,
        'dob': dob_formatted,
    }
    logger.info("  search_person params: first=%s, last=%s, dob_formatted=%s",
                first_name, last_name, dob_formatted)
    async with semaphore:
        async with session.get(f'{BASE_URL}/up/sbjprsn', params=params,
                               headers=HEADERS, timeout=aiohttp.ClientTimeout(total=30)) as resp:
            resp.raise_for_status()
            results = await resp.json()

    logger.info("  /up/sbjprsn response type: %s, value: %s",
                type(results).__name__, str(results)[:300])
    return results


def build_co_traveler(person_data):
    """Extract the fields we need from a resolved person record."""
    return {
        'UNF_PSNGR_ID': str(person_data.get('UNF_PSNGR_ID', '')),
        'FRST_NM': person_data.get('FRST_NM', ''),
        'LST_NM': person_data.get('LST_NM', ''),
        'DOB_DT': person_data.get('DOB_DT', ''),
        'SEACATS': person_data.get('ADVERSE',{}).get('SEACATS', []),
        'SECONDARY': person_data.get('ADVERSE',{}).get('SECONDARY', []),
        'VISA': person_data.get('ADVERSE',{}).get('VISA', []),
        'CO_TRAVELERS': [],  # Will be populated in step 3
    }


async def resolve_single_co_traveler(session, semaphore, ct, seen_upids):
    """Resolve a single co-traveler by name+DOB lookup. Returns (built_dict, raw) or None."""
    first = ct.get('FRST_NM', '')
    last = ct.get('LST_NM', '')
    dob = ct.get('DOB_DT', '')

    if not first or not last or not dob:
        logger.warning("Skipping co-traveler with missing name/DOB: %s", ct)
        return None

    logger.info("Searching for co-traveler: %s %s, DOB: %s", first, last, dob)
    person = await search_person(session, semaphore, first, last, dob)

    if not person:
        logger.warning("No match found for %s %s (%s)", first, last, dob)
        return None

    person_upid = str(person.get('UNF_PSNGR_ID', ''))
    if person_upid and person_upid in seen_upids:
        logger.info("Skipping duplicate: %s %s (UPID %s)", first, last, person_upid)
        return None

    return (build_co_traveler(person), person, person_upid)


async def resolve_co_travelers(session, semaphore, co_trav_list, seen_upids):
    """Resolve a list of co-travelers concurrently by name+DOB lookup.

    Skips anyone whose UNF_PSNGR_ID is already in seen_upids.
    Adds newly resolved UPIDs to seen_upids (mutates the set).
    Returns list of tuples: (built_dict, raw_api_response).
    """
    tasks = [resolve_single_co_traveler(session, semaphore, ct, seen_upids)
             for ct in co_trav_list]
    results = await asyncio.gather(*tasks)

    resolved = []
    for result in results:
        if result is None:
            continue
        built, raw, person_upid = result
        # Re-check seen_upids since concurrent tasks may have duplicates
        if person_upid and person_upid in seen_upids:
            continue
        if person_upid:
            seen_upids.add(person_upid)
        resolved.append((built, raw))

    return resolved


async def process_direct_co_traveler(session, semaphore, ct, seen_upids):
    """Process a single direct co-traveler: resolve UPID and fetch nested co-travelers."""
    first = ct.get('FRST_NM', '')
    last = ct.get('LST_NM', '')
    dob = ct.get('DOB_DT', '')

    # Main pax response only has name+DOB for co-travelers;
    # search to get full record (UNF_PSNGR_ID, SEACATS, VISA, SECONDARY, co-travelers)
    logger.info("Resolving full record for %s %s...", first, last)
    person = await search_person(session, semaphore, first, last, dob)
    if person:
        ct_dict = build_co_traveler(person)
        logger.info("  Search result keys: %s", list(person.keys()))
        logger.info("  UNF_PSNGR_ID value: '%s'", person.get('UNF_PSNGR_ID'))
        person_upid = str(person.get('UNF_PSNGR_ID', ''))
        if person_upid:
            seen_upids.add(person_upid)

        # Step 3: Resolve nested co-travelers from the search result
        nested_raw = person.get('UNF_PRSN_CO_TRAVELERS', [])
        if nested_raw:
            logger.info("  %s %s has %d nested co-travelers", first, last, len(nested_raw))
            # Exclude main passenger + direct co-travelers, but allow sharing across parents
            nested_seen = set(seen_upids)
            nested_pairs = await resolve_co_travelers(session, semaphore, nested_raw, nested_seen)
            ct_dict['CO_TRAVELERS'] = [nd for nd, _ in nested_pairs]
    else:
        logger.warning("No match found for %s %s (%s), skipping", first, last, dob)
        return None

    return ct_dict


async def build_pax_file(upid):
    """Main entry point: build the full pax data dict for a given UPID.

    Returns the assembled dict (also saves to disk).
    """
    logger.info("=== Building pax file for UPID: %s ===", upid)

    semaphore = asyncio.Semaphore(MAX_CONCURRENT)

    connector = aiohttp.TCPConnector(ssl=False)
    async with aiohttp.ClientSession(connector=connector) as session:
        # Step 1: Get main passenger
        logger.info("Step 1: Fetching main passenger...")
        main = await fetch_main_passenger(session, upid)

        pax_data = {
            'UNF_PSNGR_ID': str(main.get('UNF_PSNGR_ID', upid)),
            'FRST_NM': main.get('FRST_NM', ''),
            'LST_NM': main.get('LST_NM', ''),
            'DOB_DT': main.get('DOB_DT', ''),
            'CTZNSHP_CTRY_CD': main.get('CTZNSHP_CTRY_CD', ''),
            'GNDR_CD': main.get('GNDR_CD', ''),
            'BIRTH_LOC': main.get('BIRTH_LOC', []),
            'SEACATS': main.get('ADVERSE',{}).get('SEACATS', []),
            'SECONDARY': main.get('ADVERSE',{}).get('SECONDARY', []),
            'VISA': main.get('ADVERSE',{}).get('VISA', []),
            'UNF_PRSN_CO_TRAVELERS': [],
            'PHONE_NUMBERS': main.get('PHONE_NUMBERS', []),
            'ADDRESSES': main.get('ADDRESSES', []),
        }

        # Track seen UPIDs to avoid duplicates (main passenger is always "seen")
        seen_upids = {str(main.get('UNF_PSNGR_ID', upid))}

        # Step 2: Process all direct co-travelers concurrently (capped by semaphore)
        raw_co_travelers = main.get('UNF_PRSN_CO_TRAVELERS', [])
        logger.info("Step 2: Processing %d direct co-travelers (max %d concurrent)...",
                    len(raw_co_travelers), MAX_CONCURRENT)

        tasks = [process_direct_co_traveler(session, semaphore, ct, seen_upids)
                 for ct in raw_co_travelers]
        direct_co_travelers = await asyncio.gather(*tasks)

        pax_data['UNF_PRSN_CO_TRAVELERS'] = [ct for ct in direct_co_travelers if ct]

    # Save to disk
    os.makedirs(DATA_DIR, exist_ok=True)
    filepath = os.path.join(DATA_DIR, f'{upid}_pax_data_real.json')
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(pax_data, f, indent=4)

    logger.info("Saved pax file: %s", filepath)

    # Generate summary
    build_pax_summary(pax_data)

    return pax_data


def build_pax_summary(pax_data):
    """Build a summary of the pax data: counts of adverse records, travelers, and unique persons."""
    upid = pax_data.get('UNF_PSNGR_ID', '')
    co_travelers = pax_data.get('UNF_PRSN_CO_TRAVELERS', [])

    # Main passenger adverse counts
    main_seacats = len(pax_data.get('SEACATS', []))
    main_visa = len(pax_data.get('VISA', []))
    main_secondary = len(pax_data.get('SECONDARY', []))

    # Totals across the entire network
    total_seacats = main_seacats
    total_visa = main_visa
    total_secondary = main_secondary

    # Count co-travelers and nested co-travelers
    num_co_travelers = len(co_travelers)
    num_nested_co_travelers = 0

    # Track unique persons (by UNF_PSNGR_ID)
    unique_upids = set()
    if upid:
        unique_upids.add(upid)

    for ct in co_travelers:
        ct_upid = ct.get('UNF_PSNGR_ID', '')
        if ct_upid:
            unique_upids.add(ct_upid)

        total_seacats += len(ct.get('SEACATS', []))
        total_visa += len(ct.get('VISA', []))
        total_secondary += len(ct.get('SECONDARY', []))

        nested = ct.get('CO_TRAVELERS', [])
        num_nested_co_travelers += len(nested)

        for nct in nested:
            nct_upid = nct.get('UNF_PSNGR_ID', '')
            if nct_upid:
                unique_upids.add(nct_upid)

            total_seacats += len(nct.get('SEACATS', []))
            total_visa += len(nct.get('VISA', []))
            total_secondary += len(nct.get('SECONDARY', []))

    summary = {
        'UNF_PSNGR_ID': upid,
        'main_passenger': f"{pax_data.get('FRST_NM', '')} {pax_data.get('LST_NM', '')}",
        'main_passenger_adverse': {
            'SEACATS': main_seacats,
            'VISA': main_visa,
            'SECONDARY': main_secondary,
        },
        'network_totals': {
            'SEACATS': total_seacats,
            'VISA': total_visa,
            'SECONDARY': total_secondary,
        },
        'num_co_travelers': num_co_travelers,
        'num_nested_co_travelers': num_nested_co_travelers,
        'num_unique_persons': len(unique_upids),
    }

    # Save summary to disk
    os.makedirs(DATA_DIR, exist_ok=True)
    filepath = os.path.join(DATA_DIR, f'{upid}_pax_summary.json')
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=4)

    logger.info("Saved summary: %s", filepath)
    return summary


if __name__ == '__main__':
    import sys
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

    asyncio.run(build_pax_file(sys.argv[1]))
