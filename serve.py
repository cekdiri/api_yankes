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
def covokupansi(idprov):
    rumkit = RumahSakit.select().where(RumahSakit.prov_id==idprov)
    result = []
    for rum in rumkit:
        subresult = {}
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
                    subresult = result[idx]['kamar']
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
            result.append(subresult)
            
    
    return jsonify(result)

@app.route('/isolations', methods=['GET'])
def isolations():
    kelas = Kelas_Ruang.select().where(Kelas_Ruang.title.contains('isolasi'))
    kelasruang = [k.id for k in kelas]
    occupation = Occupations.select().where(Occupations.kelas_ruang.in_(kelasruang))
    isolasi = [model_to_dict(isolasi, recurse=True) for isolasi in occupation]
    return jsonify({'rows':list(isolasi)})

if __name__ == '__main__':
   app.run(debug=False)



