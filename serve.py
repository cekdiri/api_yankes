from flask import Flask, render_template, request, jsonify, redirect, make_response
import logging
import requests
import json
import random
from datetime import datetime, timedelta
import re
import os
import peewee as pw
import csv
from requests.packages.urllib3.exceptions import InsecureRequestWarning
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)
from bs4 import BeautifulSoup
import selenium
from selenium import webdriver
import dateparser
from playhouse.shortcuts import model_to_dict, dict_to_model


app = Flask(__name__)
app.config.from_pyfile('settings.cfg')

fmt = "%(levelname)s - %(asctime)s %(filename)s:%(lineno)d %(message)s"
formatter = logging.Formatter(fmt=fmt)
log_path = './{}.log'.format(__name__)
file_handler = logging.FileHandler(log_path)
file_handler.setFormatter(formatter)

app.logger.setLevel(logging.INFO)
app.logger.addHandler(file_handler)



db = pw.MySQLDatabase(app.config['NAME_DB'], user=app.config['USER_DB'], password=app.config['PASS_DB'],
                         host='127.0.0.1', port=3306)

class BaseModel(pw.Model):
    class Meta:
        database = db

class JenisFaskes(BaseModel):
    title = pw.CharField(max_length=255)

class Province(BaseModel):
    prov_id = pw.IntegerField()
    nama_prov = pw.CharField(max_length=255)

class RumahSakit(BaseModel):
    prov_id = pw.ForeignKeyField(Province, backref='provinsi')
    kode_rs = pw.IntegerField()
    nama_unit = pw.CharField(max_length=255)
    alamat = pw.TextField()
    jenis_faskes = pw.ForeignKeyField(JenisFaskes, backref='jenis')
    lat = pw.CharField(max_length=255)
    lon = pw.CharField(max_length=255)

class Jenis_Ruang(BaseModel):
    title = pw.CharField(max_length=255)

class Kelas_Ruang(BaseModel):
    title = pw.CharField(max_length=255)

class Occupations(BaseModel):
    rumahsakit = pw.ForeignKeyField(RumahSakit)
    jenis_ruang = pw.ForeignKeyField(Jenis_Ruang)
    kelas_ruang = pw.ForeignKeyField(Kelas_Ruang)
    used_lk = pw.IntegerField(default=0)
    uses_pr = pw.IntegerField(default=0)
    used_ttl = pw.IntegerField(default=0)
    vac_lk = pw.IntegerField(default=0)
    vac_pr = pw.IntegerField(default=0)
    vac_ttl  = pw.IntegerField(default=0)
    waiting = pw.IntegerField(default=0)
    last_update = pw.DateTimeField()
    created_at = pw.DateTimeField(default=datetime.utcnow())


class CovidOccupations(BaseModel):
    rumahsakit = pw.ForeignKeyField(RumahSakit)
    jenis_ruang = pw.ForeignKeyField(Jenis_Ruang)
    kelas_ruang = pw.ForeignKeyField(Kelas_Ruang)
    total_kamar = pw.IntegerField(default=0)
    total_terisi = pw.IntegerField(default=0)
    total_kosong = pw.IntegerField(default=0)
    last_update = pw.DateTimeField()
    created_at = pw.DateTimeField(default=datetime.utcnow())



@app.route('/')
def index():
    return jsonify({
            'message': 'API for realtime bed monitoring',
            'paths': { 
                '/province': 'retrieve province',
                '/hospitals/<int:id>': 'retrieve hospitals in a province. use id from /province',
                '/ketersediaan-kamar/<int:id>': 'retrieve occupations for every hospitals in a province. use id from /province',
                '/isolations': 'retrieve isolation rooms'
            }
        })


@app.route('/province',  methods=['GET'])
def provinces():
    province = Province.select().dicts()
    return jsonify({'rows':list(province)})

@app.route('/hospitals/<int:idprov>',  methods=['GET'])
def hospital(idprov):
    hospitals = RumahSakit.select().where(RumahSakit.prov_id==idprov).dicts()
    return jsonify({'rows':list(hospitals)})

@app.route('/occupation/<int:idprov>',  methods=['GET'])
def okupansi(idprov):
    occupation = Occupations.select().join(RumahSakit).where(RumahSakit.prov_id==idprov)
    occp = [model_to_dict(ocp, recurse=True) for ocp in occupation]
    return jsonify({'rows':list(occp)})


@app.route('/ketersediaan-kamar/<int:idprov>',  methods=['GET'])
def view(idprov):
	return jsonify(get_paginated_list(
		idprov, 
		'/ketersediaan-kamar/'+idprov+'/', 
		start=request.args.get('start', 1), 
		limit=5
	))


def get_paginated_list(idprov, url, start, limit):
    prov = Province.select().where(Province.prov_id==idprov).get()
    rumkit = RumahSakit.select().where(RumahSakit.prov_id==prov)
    count = rumkit.count()
    obj = {}
    obj['start'] = start
    obj['limit'] = limit
    obj['count'] = count
    if (count < start):
        return jsonify({'result': 'ERROR'})
    if start == 1:
        obj['previous'] = ''
    else:
        start_copy = max(1, start - limit)
        limit_copy = start - 1
        obj['previous'] = url + '?start=%d&limit=%d' % (start_copy, limit_copy)
    if start + limit > count:
        obj['next'] = ''
    else:
        start_copy = start + limit
        obj['next'] = url + '?start=%d&limit=%d' % (start_copy, limit)
    result = []
    for rum in rumkit:
        result.append(rum)
    result = result[(start - 1):(start - 1 + limit)]
    obj['result'] = []
    for rum in result:
        subresult = {}
        subresult['kamar'] = []
        if len(result) > 0:
            if not rum.nama_unit in [a['nama'] for a in result]:
                subresult['nama'] = rum.nama_unit
                subresult['alamat'] = {
                    'alamat': rum.alamat,
                    'lat': rum.lat,
                    'lon': rum.lon
                }
                subresult['kamar'] = []
            else:
                index = None
                for idx,a in enumerate(result):
                    if a['nama'] == rum.nama_unit:
                        index = idx
                if index:
                    subresult = result[idx]
        else:
            subresult['nama'] = rum.nama_unit
            subresult['alamat'] = {
                'alamat': rum.alamat,
                'lat': rum.lat,
                'lon': rum.lon
            }
            subresult['kamar'] = []
        occ = CovidOccupations.select().where(CovidOccupations.rumahsakit==rum)
        if occ.count() > 0:
            for oc in occ:
                if len(subresult['kamar']) > 0:
                    if not oc.jenis_ruang.title in [a['nama'] for a in subresult['kamar']]:
                        subresult['kamar'].append({
                            'nama': oc.jenis_ruang.title,
                            'status':{
                                'kamar_kosong': oc.total_kosong,
                                'kamar_terisi': oc.total_terisi,
                                'kamar_total': oc.total_kamar
                            },
                            'last_update': oc.last_update
                        })
                    else:
                        for sub in subresult['kamar']:
                            if sub['nama'] == oc.jenis_ruang.title:
                                if oc.last_update > sub['last_update']:
                                    sub['last_update'] = oc.last_update
                                    sub['status']['kamar_kosong'] = oc.total_kosong
                                    sub['status']['kamar_terisi'] = oc.total_terisi
                                    sub['status']['kamar_total'] = oc.total_kamar
                else:
                    subresult['kamar'].append({
                            'nama': oc.jenis_ruang.title,
                            'status':{
                                'kamar_kosong': oc.total_kosong,
                                'kamar_terisi': oc.total_terisi,
                                'kamar_total': oc.total_kamar
                            },
                            'last_update': oc.last_update
                        })
        if len(subresult['kamar']) > 0:
            obj['result'].append(subresult)
            
    
    return jsonify(obj)

@app.route('/table-kamar', methods=['GET'])
def tablekamar():
    try:
        prov = int(request.args.get('prov'))
    except:
        prov = None 
    try:
        jenis_kamar = int(request.args.get('kamar'))
    except:
        jenis_kamar = None

    provinces = Province.select()
    kamars = Jenis_Ruang.select()
    if prov:
        if prov > 0:
            prov = Province.select().where(Province.prov_id==int(prov)).get()
            if jenis_kamar:
                ruang = Jenis_Ruang.select().where(Jenis_Ruang.id==int(jenis_kamar)).get()
                occ = CovidOccupations.select().join(RumahSakit).where(RumahSakit.prov_id==prov, CovidOccupations.jenis_ruang==ruang).group_by(CovidOccupations.rumahsakit)
            else:
                occ = CovidOccupations.select().join(RumahSakit).where(RumahSakit.prov_id==prov).group_by(CovidOccupations.rumahsakit)
            ocrs = []
            for oc in occ:
                okupansi = {}
                for kamar in kamars:
                    try:
                        kondisi = CovidOccupations.select().where(CovidOccupations.rumahsakit==oc.rumahsakit, CovidOccupations.jenis_ruang==kamar).order_by(CovidOccupations.last_update.desc()).limit(1).get()
                        okupansi[kamar.id] = {'total_kosong': kondisi.total_kosong, 'last_update': kondisi.last_update} 
                    except:
                        okupansi[kamar.id] = {'total_kosong': 0, 'last_update': ''} 
                ocrs.append({'rumahsakit': oc, 'okupansi': okupansi })

            return render_template('table-hscroll.html', provinces=provinces, kamars=kamars, occs=ocrs)
        else:
            return render_template('table-hscroll.html', provinces=provinces, kamars=kamars, occs=None)
    else:
        return render_template('table-hscroll.html', provinces=provinces, kamars=kamars, occs=None)

@app.route('/getkamar/<int:idkm>/<int:idrs>', methods=["GET"])
def getkamar(idkm,idrs):
    try:
        rumkit = RumahSakit.select().where(RumahSakit.id==int(idrs))
        kamar  = Jenis_Ruang.select().where(Jenis_Ruang.id==int(idkm))
        occ = CovidOccupations.select().where(CovidOccupations.rumahsakit==rumkit, CovidOccupations.jenis_ruang==kamar).order_by(CovidOccupations.last_update.desc()).limit(1).dicts()
    except:
        occ = []
    return jsonify({'result':list(occ)})

@app.route('/isolations', methods=['GET'])
def isolations():
    kelas = Kelas_Ruang.select().where(Kelas_Ruang.title.contains('isolasi'))
    kelasruang = [k.id for k in kelas]
    occupation = Occupations.select().where(Occupations.kelas_ruang.in_(kelasruang))
    isolasi = [model_to_dict(isolasi, recurse=True) for isolasi in occupation]
    return jsonify({'rows':list(isolasi)})

if __name__ == '__main__':
   app.run(debug=True)



