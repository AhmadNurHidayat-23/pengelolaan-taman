import csv
import io
from flask import Blueprint, g, request, jsonify, Response
from core.auth import require, data
from core.security import Problem
from core.db import transaction
from . import models, service
api = Blueprint('api', __name__)

@api.get('/api/state')
@require()
def state():
    return jsonify(models.state(g.db, request.args))

@api.route('/api/<kind>', methods=['POST'])
@api.route('/api/<kind>/<int:id>', methods=['PUT','DELETE'])
@require()
def save(kind, id=None):
    if kind not in ('regions','parks','facilities','inspections','schedules','activities'):
        raise Problem('Alamat tidak tersedia.',404)
    if kind in ('regions','parks','facilities','schedules') and g.user['role'] != 'Admin':
        raise Problem('Data induk dan jadwal hanya dikelola Admin.',403)
    if kind in ('inspections','activities') and request.method != 'POST':
        raise Problem('Riwayat pemeriksaan dan kegiatan dipertahankan.',405)
    if request.method == 'DELETE':
        if kind in ('parks','facilities'):
            service.archive(g.db,kind,id)
        elif kind == 'schedules':
            service.cancel(g.db,id)
        else:
            models.find(g.db,kind,id)
            with transaction(g.db):
                g.db.execute('DELETE FROM regions WHERE id=?',(id,))
    elif kind == 'inspections':
        service.inspection(g.db,data(),g.user['id'])
    elif kind == 'activities':
        service.activity(g.db,data(),g.user['id'])
    else:
        {'regions':service.master,'parks':service.park,'facilities':service.facility,'schedules':service.schedule}[kind](g.db,data(),id)
    return jsonify(message='Data berhasil disimpan. Riwayat tetap dipertahankan.')

@api.post('/api/<kind>/<int:id>/restore')
@require(('Admin',))
def restore(kind,id):
    if kind in ('parks','facilities'):
        service.archive(g.db,kind,id,True)
    elif kind == 'schedules':
        service.cancel(g.db,id,True)
    else:
        raise Problem('Alamat tidak tersedia.',404)
    return jsonify(message='Data dipulihkan.')

@api.get('/api/facilities/<int:id>/history')
@require()
def history(id):
    return jsonify(models.history(g.db,id))

@api.get('/api/export')
@require()
def export():
    output=io.StringIO()
    writer=csv.writer(output)
    writer.writerow(['Taman','Wilayah','Fasilitas','Jenis','Jumlah','Kondisi terakhir','Tanggal inspeksi'])
    for f in models.state(g.db,request.args)['facilities']:
        values=[f[k] or '' for k in ('park','region','name','kind','quantity','condition','inspected_on')]
        writer.writerow(["'"+str(v) if str(v).startswith(('=','+','-','@')) else v for v in values])
    return Response('\ufeff'+output.getvalue(),mimetype='text/csv',headers={'Content-Disposition':'attachment; filename=kondisi-taman.csv'})
