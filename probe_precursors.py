import sqlite3
from core.msds_intelligence import DB_PATH
from core.legal_engine import LegalCatalogEngine

conn = sqlite3.connect(str(DB_PATH))
conn.row_factory = sqlite3.Row
rows = conn.execute('SELECT chemical_id, product_code, product_name_vi, cas_primary FROM chemicals').fetchall()
print(f'Total chemicals in DB: {len(rows)}')
engine = LegalCatalogEngine.get_instance()
found_precursors = []
for r in rows:
    cas = r['cas_primary'] or ''
    matches = engine.match_cas(cas) if cas else []
    precursors = [m['section_id'] for m in matches if 'IV-C' in m.get('section_id', '') or 'ND26' in m.get('source_id', '')]
    if precursors or cas in ('108-88-3', '67-64-1', '78-93-3'):
        found_precursors.append((r['chemical_id'], r['product_code'], r['product_name_vi'], cas, precursors))

print(f'Found {len(found_precursors)} precursor chemicals in DB:')
for p in found_precursors:
    print(p)

print("\nDirect CAS check in legal engine:")
for test_cas in ['108-88-3', '67-64-1', '78-93-3']:
    res = engine.match_cas(test_cas)
    print(f"CAS {test_cas}: {len(res)} matches -> {[r.get('section_id') for r in res]}")


print("\nChecking compositions table:")
comps = conn.execute("SELECT * FROM compositions").fetchall()
print(f"Total compositions in DB: {len(comps)}")
for c in comps:
    cas = c['cas_number'] or ''
    if cas in ('108-88-3', '67-64-1', '78-93-3'):
        print(f"Found precursor in composition: chem_id={c['chemical_id']}, name={c['component_name']}, cas={cas}")
