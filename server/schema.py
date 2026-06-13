GRAPH_SCHEMA = """
Node types and their properties:
- MainPassenger: id (string, unique), first_name (string), last_name (string), dob (string), gender (string), citizenship_country (string)
- Phone: number (string, unique)
- Country: code (string, unique)
- BirthLocation: country (string), city (string)
- Address: address (string), type (string, e.g. 'H' for home)
- AssociatedPerson: id (string, unique), first_name (string), last_name (string), dob (string)
- Seacat: id (string), enf_action_id (string), incident_datetime (string), incident_id (string), incident_type (string)
- Visa: id (string), name (string), type (string), refusal_code (string), refusal_datetime (string)
- Secondary: id (string), name (string), sub_transaction_type (string), reason (string), crossing_datetime (string), referral_workspace_id (string)

Relationship types:
MainPassenger -> entity:
  MainPassenger -[:FROM_COUNTRY]-> Country
  MainPassenger -[:BORN_IN]-> BirthLocation
  MainPassenger -[:HAS_PHONE]-> Phone
  MainPassenger -[:HAS_ADDRESS]-> Address
  MainPassenger -[:CO_TRAVELER]-> AssociatedPerson
  MainPassenger -[:HAS_SEACAT]-> Seacat

AssociatedPerson -> entity:
  AssociatedPerson -[:CO_TRAVELER]-> AssociatedPerson
  AssociatedPerson -[:HAS_SEACAT]-> Seacat
  AssociatedPerson -[:HAS_VISA]-> Visa
  AssociatedPerson -[:HAS_SECONDARY]-> Secondary

Important terminology:
- "Derog" or "derogatory information" refers collectively to SEACAT, VISA, and SECONDARY records.
- When the user asks about "derogs", query all three types: Seacat, Visa, and Secondary.
- SEACAT records track seizure events and enforcement actions/incidents. When the user asks about "seizures" or "seizure events", query Seacat nodes.
- VISA records track visa refusals.
- SECONDARY records track secondary inspection referrals.
"""
