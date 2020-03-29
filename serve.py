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


db.connect()
db.create_tables([JenisFaskes, Province, RumahSakit, Jenis_Ruang, Kelas_Ruang, Occupations], safe=True)



@app.route('/')
def index():
    return jsonify({
            'message': 'API for realtime bed monitoring',
            'paths': { 
                '/hospitals': 'retrieve hospitals',
                '/isolations': 'retrieve isolation rooms'
            }
        })

@app.route('/hospitals',  methods=['GET'])
def all():
    hospitals = RumahSakit.select().dicts()
    return jsonify({'rows':list(hospitals)})

@app.route('/isolations', methods=['GET'])
def isolations():
    kelas = Kelas_Ruang.select().where(Kelas_Ruang.title.contains('isolasi'))
    kelasruang = [k.id for k in kelas]
    occupation = Occupations.select().where(Occupations.kelas_ruang.in_(kelasruang))
    isolasi = [model_to_dict(isolasi, recurse=True) for isolasi in occupation]
    return jsonify({'rows':list(isolasi)})

if __name__ == '__main__':
   app.run(debug=False)



