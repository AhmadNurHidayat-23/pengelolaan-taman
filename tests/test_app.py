import secrets
from datetime import date, timedelta
import pytest
from app import create_app
from app.models import today
from core.db import connect
from core.security import add_user

@pytest.fixture
def env(tmp_path):
    app=create_app({'TESTING':True,'INSTANCE_DIR':str(tmp_path)})
    db=connect(tmp_path)
    password=secrets.token_hex(20)
    for name,role in [('admin','Admin'),('staff','Petugas')]:
        add_user(db,name,'Penguji '+role,role,password)
    db.close()
    clients={}
    for name in ['admin','staff']:
        client=app.test_client()
        r=client.post('/api/login',json={'username':name,'password':password})
        clients[name]=(client,{'X-CSRF-Token':r.json['csrf']})
    c,h=clients['admin']
    assert c.post('/api/regions',json={'name':'Wilayah Contoh'},headers=h).status_code==200
    assert c.post('/api/parks',json=park(),headers=h).status_code==200
    assert c.post('/api/facilities',json=facility(),headers=h).status_code==200
    return app,clients,tmp_path

def day(offset=0):
    return (date.fromisoformat(today())+timedelta(days=offset)).isoformat()

def park(**extra):
    return {'code':'T-01','name':'Taman Contoh','region_id':1,'address':'Alamat demonstrasi','area':1200,**extra}

def facility(**extra):
    return {'park_id':1,'name':'Bangku Contoh','kind':'Tempat duduk','quantity':4,**extra}

def job(**extra):
    return {'facility_id':1,'starts_on':day(-10),'ends_on':day(10),'task':'Perawatan demonstrasi',**extra}

def test_crud_master_park_facility_and_archive(env):
    _,clients,_=env
    c,h=clients['admin']
    assert c.put('/api/regions/1',json={'name':'Wilayah Diubah'},headers=h).status_code==200
    assert c.put('/api/parks/1',json=park(name='Taman Diubah'),headers=h).status_code==200
    assert c.put('/api/facilities/1',json=facility(quantity=5),headers=h).status_code==200
    assert c.delete('/api/regions/1',json={},headers=h).status_code==409
    assert c.delete('/api/parks/1',json={},headers=h).status_code==409
    assert c.delete('/api/facilities/1',json={},headers=h).status_code==200
    assert c.delete('/api/parks/1',json={},headers=h).status_code==200
    assert c.get('/api/state').json['parks']==[]
    assert len(c.get('/api/state?archived=1').json['parks'])==1
    assert c.post('/api/facilities/1/restore',json={},headers=h).status_code==409
    c.post('/api/parks/1/restore',json={},headers=h)
    c.post('/api/facilities/1/restore',json={},headers=h)
    assert len(c.get('/api/state').json['facilities'])==1

def test_inspection_latest_by_date_not_insertion_and_history(env):
    _,clients,_=env
    c,h=clients['staff']
    assert c.get('/api/state').json['facilities'][0]['condition'] is None
    for on,condition in [(day(),'Rusak'),(day(-2),'Baik')]:
        assert c.post('/api/inspections',json={'facility_id':1,'on_date':on,'condition':condition,'note':'Pemeriksaan uji'},headers=h).status_code==200
    assert c.get('/api/state').json['facilities'][0]['condition']=='Rusak'
    assert len(c.get('/api/facilities/1/history').json['inspections'])==2
    assert c.delete('/api/inspections/1',json={},headers=h).status_code==405
    assert c.post('/api/inspections',json={'facility_id':1,'on_date':day(1),'condition':'Baik','note':'Mendatang'},headers=h).status_code==400

def test_maintenance_real_activities_and_archive_rules(env):
    _,clients,_=env
    c,h=clients['admin']
    assert c.post('/api/schedules',json=job(),headers=h).status_code==200
    assert c.get('/api/state').json['schedules'][0]['progress'] is None
    assert c.put('/api/schedules/1',json=job(task='Perawatan Diubah'),headers=h).status_code==200
    staff,sh=clients['staff']
    for on,progress in [(day(),100),(day(-1),25)]:
        assert staff.post('/api/activities',json={'schedule_id':1,'on_date':on,'progress':progress,'note':'Kegiatan uji'},headers=sh).status_code==200
    state=c.get('/api/state').json
    assert state['schedules'][0]['progress']==100
    assert state['schedules'][0]['status']=='Selesai'
    assert state['facilities'][0]['condition'] is None
    assert c.put('/api/schedules/1',json=job(starts_on=day(-9)),headers=h).status_code==409
    assert len(c.get('/api/facilities/1/history').json['activities'])==2
    assert c.delete('/api/facilities/1',json={},headers=h).status_code==200

def test_schedule_cancel_restore_preserves_history(env):
    _,clients,_=env
    c,h=clients['admin']
    c.post('/api/schedules',json=job(),headers=h)
    assert c.delete('/api/facilities/1',json={},headers=h).status_code==409
    assert c.delete('/api/schedules/1',json={},headers=h).status_code==200
    assert c.post('/api/activities',json={'schedule_id':1,'on_date':day(),'progress':20,'note':'Uji'},headers=h).status_code==400
    assert c.post('/api/schedules/1/restore',json={},headers=h).status_code==200
    assert c.get('/api/state').json['schedules'][0]['canceled']==0

def test_validation_foreign_keys_filters_and_csv(env):
    _,clients,_=env
    c,h=clients['admin']
    for values in [park(area=0),park(area=True),park(name=''),park(region_id=999)]:
        assert c.post('/api/parks',json=values,headers=h).status_code in (400,404)
    assert c.post('/api/schedules',json=job(ends_on=day(-11)),headers=h).status_code==400
    c.post('/api/schedules',json=job(),headers=h)
    for values in [{'progress':101,'on_date':day()},{'progress':50,'on_date':day(-11)},{'progress':50,'on_date':'2026-02-30'}]:
        assert c.post('/api/activities',json={'schedule_id':1,'note':'Uji',**values},headers=h).status_code==400
    assert len(c.get('/api/state?q=bangku&region_id=1&park_id=1&condition=Belum%20Diperiksa').json['facilities'])==1
    assert c.get('/api/state?q=tidakada').json['facilities']==[]
    assert 'Bangku Contoh' in c.get('/api/export').data.decode('utf-8-sig')

def test_access_csrf_origin_isolation_and_role_refresh(env):
    app,clients,folder=env
    c,h=clients['staff']
    assert app.test_client().get('/api/state').status_code==401
    assert c.put('/api/parks/1',json=park(),headers=h).status_code==403
    assert c.post('/api/inspections',json={},headers={}).status_code==403
    assert c.post('/api/inspections',json={},headers={**h,'Origin':'https://example.invalid'}).status_code==403
    assert c.post('/api/inspections',json={},headers={'X-CSRF-Token':'é'}).status_code==403
    admin,ah=clients['admin']
    cookie=admin.get_cookie('pengelolaan_taman_session')
    wrong=app.test_client()
    wrong.set_cookie('app_session',cookie.value)
    assert wrong.get('/api/state').status_code==401
    db=connect(folder)
    db.execute("UPDATE users SET role='Petugas' WHERE username='admin'")
    db.commit()
    db.close()
    assert admin.post('/api/regions',json={'name':'Role lama'},headers=ah).status_code==403
    c.post('/api/logout',json={},headers=h)
    assert c.get('/api/state').status_code==401

def test_restart_idempotence_and_integrity(env):
    _,clients,folder=env
    c,h=clients['admin']
    c.post('/api/inspections',json={'facility_id':1,'on_date':day(),'condition':'Baik','note':'Uji'},headers=h)
    create_app({'TESTING':True,'INSTANCE_DIR':str(folder)})
    db=connect(folder)
    assert db.execute('SELECT COUNT(*) FROM inspections').fetchone()[0]==1
    assert db.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
    assert db.execute('PRAGMA foreign_key_check').fetchall()==[]
    db.close()
