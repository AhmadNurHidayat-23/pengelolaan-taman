from core.db import transaction
from core.security import Problem
from core.validate import text, integer, date, choice
from .models import find, today

def active(db, id):
    f = find(db, 'facilities', id)
    if f['archived'] or find(db, 'parks', f['park_id'])['archived']:
        raise Problem('Fasilitas atau taman diarsipkan.', 409)
    return f

def master(db, b, id=None):
    name = text(b.get('name'), 'Wilayah', 100)
    with transaction(db):
        if id:
            find(db, 'regions', id)
            db.execute('UPDATE regions SET name=? WHERE id=?', (name, id))
        else:
            db.execute('INSERT INTO regions(name) VALUES(?)', (name,))

def park(db, b, id=None):
    values = (text(b.get('code'), 'Kode taman', 40), text(b.get('name'), 'Nama taman', 100), integer(b.get('region_id'), 'Wilayah', 1), text(b.get('address'), 'Alamat', 250), integer(b.get('area'), 'Luas m²', 1, 100000000))
    find(db, 'regions', values[2])
    with transaction(db):
        if id:
            if find(db, 'parks', id)['archived']:
                raise Problem('Pulihkan taman sebelum mengedit.', 409)
            db.execute('UPDATE parks SET code=?,name=?,region_id=?,address=?,area=? WHERE id=?', (*values, id))
        else:
            db.execute('INSERT INTO parks(code,name,region_id,address,area) VALUES(?,?,?,?,?)', values)

def facility(db, b, id=None):
    values = (integer(b.get('park_id'), 'Taman', 1), text(b.get('name'), 'Nama fasilitas', 100), text(b.get('kind'), 'Jenis fasilitas', 80), integer(b.get('quantity'), 'Jumlah', 1, 100000))
    if find(db, 'parks', values[0])['archived']:
        raise Problem('Taman telah diarsipkan.', 409)
    with transaction(db):
        if id:
            old = active(db, id)
            if old['park_id'] != values[0] and db.execute('SELECT id FROM inspections WHERE facility_id=? UNION SELECT id FROM schedules WHERE facility_id=?', (id,id)).fetchone():
                raise Problem('Taman fasilitas dengan riwayat tidak dapat diganti.', 409)
            db.execute('UPDATE facilities SET park_id=?,name=?,kind=?,quantity=? WHERE id=?', (*values,id))
        else:
            db.execute('INSERT INTO facilities(park_id,name,kind,quantity) VALUES(?,?,?,?)', values)

def inspection(db, b, actor):
    id = integer(b.get('facility_id'), 'Fasilitas', 1)
    active(db, id)
    on = date(b.get('on_date'))
    if on > today():
        raise Problem('Inspeksi tidak boleh bertanggal mendatang.')
    values = (id, on, choice(b.get('condition'), ('Baik','Perlu Perawatan','Rusak'), 'Kondisi'), text(b.get('note'), 'Catatan inspeksi', 1500), actor)
    with transaction(db):
        db.execute('INSERT INTO inspections(facility_id,on_date,condition,note,actor_id) VALUES(?,?,?,?,?)', values)

def schedule(db, b, id=None):
    facility_id, start, end = integer(b.get('facility_id'), 'Fasilitas', 1), date(b.get('starts_on')), date(b.get('ends_on'))
    active(db, facility_id)
    if end < start:
        raise Problem('Akhir jadwal tidak boleh sebelum mulai.')
    task = text(b.get('task'), 'Rencana perawatan', 600)
    with transaction(db):
        if id:
            old = find(db, 'schedules', id)
            if old['canceled']:
                raise Problem('Pulihkan jadwal sebelum mengedit.', 409)
            if db.execute('SELECT id FROM activities WHERE schedule_id=?', (id,)).fetchone() and (old['facility_id'] != facility_id or old['starts_on'] != start):
                raise Problem('Fasilitas dan awal jadwal yang memiliki kegiatan tidak dapat diganti.', 409)
            db.execute('UPDATE schedules SET facility_id=?,starts_on=?,ends_on=?,task=? WHERE id=?', (facility_id,start,end,task,id))
        else:
            db.execute('INSERT INTO schedules(facility_id,starts_on,ends_on,task) VALUES(?,?,?,?)', (facility_id,start,end,task))

def activity(db, b, actor):
    id, on = integer(b.get('schedule_id'), 'Jadwal', 1), date(b.get('on_date'))
    job = find(db, 'schedules', id)
    active(db, job['facility_id'])
    if job['canceled'] or on < job['starts_on'] or on > today():
        raise Problem('Kegiatan harus pada jadwal aktif, sejak tanggal mulai sampai hari ini.')
    with transaction(db):
        db.execute('INSERT INTO activities(schedule_id,on_date,progress,note,actor_id) VALUES(?,?,?,?,?)', (id,on,integer(b.get('progress'), 'Progres', 0,100),text(b.get('note'), 'Kegiatan perawatan',1500),actor))

def archive(db, kind, id, restore=False):
    item = find(db, kind, id)
    with transaction(db):
        if kind == 'parks' and not restore and db.execute('SELECT id FROM facilities WHERE park_id=? AND archived=0', (id,)).fetchone():
            raise Problem('Arsipkan fasilitas aktif taman terlebih dahulu.',409)
        if kind == 'facilities':
            if restore and find(db, 'parks', item['park_id'])['archived']:
                raise Problem('Pulihkan taman terlebih dahulu.',409)
            if not restore and db.execute('SELECT s.id FROM schedules s WHERE s.facility_id=? AND s.canceled=0 AND COALESCE((SELECT progress FROM activities a WHERE a.schedule_id=s.id ORDER BY a.on_date DESC,a.id DESC LIMIT 1),0)<100', (id,)).fetchone():
                raise Problem('Selesaikan atau batalkan jadwal perawatan terlebih dahulu.',409)
        db.execute(f'UPDATE {kind} SET archived=? WHERE id=?', (0 if restore else 1,id))

def cancel(db, id, restore=False):
    job = find(db, 'schedules', id)
    if restore:
        active(db, job['facility_id'])
    with transaction(db):
        db.execute('UPDATE schedules SET canceled=? WHERE id=?', (0 if restore else 1,id))
