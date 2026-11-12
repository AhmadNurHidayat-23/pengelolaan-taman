from datetime import datetime, timezone, timedelta
from core.validate import require_row
TABLES = ('regions', 'parks', 'facilities', 'inspections', 'schedules', 'activities')

def today():
    return datetime.now(timezone(timedelta(hours=7))).date().isoformat()

def find(db, kind, id):
    return require_row(db, kind, id, TABLES)

def rows(db, query, args=()):
    return [dict(r) for r in db.execute(query, args)]

def schedules(db):
    return rows(db, '''SELECT s.*,f.name facility,p.name park,
    (SELECT progress FROM activities a WHERE a.schedule_id=s.id ORDER BY a.on_date DESC,a.id DESC LIMIT 1) progress
    FROM schedules s JOIN facilities f ON f.id=s.facility_id JOIN parks p ON p.id=f.park_id ORDER BY s.starts_on DESC,s.id DESC''')

def state(db, f):
    q = str(f.get('q', '')).lower().strip()[:120]
    archive = 1 if f.get('archived') == '1' else 0
    parks = rows(db, 'SELECT p.*,r.name region FROM parks p JOIN regions r ON r.id=p.region_id WHERE p.archived=? ORDER BY p.name', (archive,))
    parks = [p for p in parks if (not q or any(q in p[k].lower() for k in ('name', 'code', 'address'))) and (not f.get('region_id') or str(p['region_id']) == str(f['region_id']))]
    facilities = rows(db, '''SELECT f.*,p.name park,r.name region,
    (SELECT condition FROM inspections i WHERE i.facility_id=f.id ORDER BY i.on_date DESC,i.id DESC LIMIT 1) condition,
    (SELECT on_date FROM inspections i WHERE i.facility_id=f.id ORDER BY i.on_date DESC,i.id DESC LIMIT 1) inspected_on
    FROM facilities f JOIN parks p ON p.id=f.park_id JOIN regions r ON r.id=p.region_id WHERE f.archived=? AND p.archived=0 ORDER BY p.name,f.name''', (archive,))
    facilities = [v for v in facilities if (not f.get('park_id') or str(v['park_id']) == str(f['park_id'])) and (not f.get('region_id') or str(db.execute('SELECT region_id FROM parks WHERE id=?', (v['park_id'],)).fetchone()[0]) == str(f['region_id'])) and (not q or q in (v['name']+' '+v['park']).lower()) and (not f.get('condition') or (v['condition'] or 'Belum Diperiksa') == f['condition'])]
    jobs = schedules(db)
    for j in jobs:
        j['status'] = 'Dibatalkan' if j['canceled'] else 'Belum Ada Laporan' if j['progress'] is None else 'Selesai' if j['progress'] == 100 else 'Dalam Perawatan'
    return {'parks': parks, 'facilities': facilities, 'schedules': jobs, 'regions': rows(db, 'SELECT * FROM regions ORDER BY name'), 'allParks': rows(db, 'SELECT id,name FROM parks WHERE archived=0 ORDER BY name'), 'allFacilities': rows(db, 'SELECT f.id,p.name||\' / \'||f.name name FROM facilities f JOIN parks p ON p.id=f.park_id WHERE f.archived=0 AND p.archived=0 ORDER BY p.name,f.name'), 'summary': {'parks': len(parks), 'facilities': len(facilities), 'attention': sum(v['condition'] in ('Perlu Perawatan','Rusak') for v in facilities), 'unknown': sum(v['condition'] is None for v in facilities)}}

def history(db, id):
    find(db, 'facilities', id)
    return {'inspections': rows(db, 'SELECT i.*,u.name actor FROM inspections i JOIN users u ON u.id=i.actor_id WHERE facility_id=? ORDER BY on_date DESC,i.id DESC', (id,)), 'activities': rows(db, 'SELECT a.*,s.task,u.name actor FROM activities a JOIN schedules s ON s.id=a.schedule_id JOIN users u ON u.id=a.actor_id WHERE s.facility_id=? ORDER BY a.on_date DESC,a.id DESC', (id,))}
