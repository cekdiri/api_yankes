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
chrome_options = webdriver.ChromeOptions()
chrome_options.add_argument('--no-sandbox')
chrome_options.add_argument('--window-size=1420,1080')
chrome_options.add_argument('--headless')
chrome_options.add_argument('--disable-gpu')

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

kode_rs = []
with open('data/faskes_rumahsakit.csv', 'r')  as fle:
    csv_reader = csv.DictReader(fle)
    for row in csv_reader:
        prov  = Province.select().where(Province.nama_prov==row['nama_prov'])
        if prov.count() < 1:
            prv = Province.select().count()
            prov = Province.create(prov_id=int(prv + 1), nama_prov=row['nama_prov'])

        jenis = JenisFaskes.select().where(JenisFaskes.title==row['jenis_faskes'])
        if jenis.count() < 1:
            jenis =JenisFaskes.create(title=row['jenis_faskes'])
        rs = RumahSakit.select().where(RumahSakit.kode_rs==row['kode_rs'])
        if rs.count() < 1:
            rs = RumahSakit.create(prov_id=prov, 
                kode_rs=row['kode_rs'], 
                nama_unit=row['nama_unit'], 
                alamat=row['alamat'], 
                jenis_faskes=jenis,
                lat = row['lat'],
                lon = row['lng']
            )
        kode_rs.append(row['kode_rs'])

    
try:
    browser = webdriver.Chrome(chrome_options=chrome_options)
except:
    browser = webdriver.Chrome('chromedriver/chromedriver', options=chrome_options)

for kode in kode_rs:

    link = 'http://sirs.yankes.kemkes.go.id/integrasi/data/bed_monitor.php?satker='+str(kode)
    browser.get(link)
    #print(r)
    data = browser.page_source
    soup = BeautifulSoup(data, 'lxml')
    table = soup.find('table', attrs={'class':'tbl-responsive table table-striped table-bordered'})
    rs = RumahSakit.select().where(RumahSakit.kode_rs==kode).get()
    if table is not None:
        res = []
        table_rows = table.find_all('tr')

        num_rows = len(table_rows)
        #print(satker+'-'+nama_rs)
        print('recording '+str(kode)+' '+rs.nama_unit)
        i = 0
        for tr in table_rows:
            _satker = kode
            _ruang = '-'
            _kelas = '-'
            _total_kamar = '0'
            _terisi_lk = '0'
            _terisi_pr = '0'
            _total_terisi = '0'
            _kosong_lk = '0'
            _kosong_pr = '0'
            _total_kosong = '0'
            _waiting_list = '0'
            _last_update = '0'
            

            if i>1 and i<(num_rows-1):
                
                td = tr.find_all('td')
                #print(td)
                row = [tr.text.strip() for tr in td if tr.text.strip()]
                #print(row)
                #print(str(i)+'-'+str(len(row)))
                if len(row)==12:
                    _temp_ruang = row[1]
                
                #print(_temp_ruang)
                if row:

                    if len(row)==12:
                        _ruang = row[1]
                        _kelas = row[2]
                        _total_kamar = row[3] 
                        _terisi_lk = row[4] 
                        _terisi_pr = row[5]
                        _total_terisi = row[6]
                        _kosong_lk = row[7]
                        _kosong_pr = row[8]
                        _total_kosong = row[9]
                        _waiting_list = row[10]
                        _last_update = row[11]

                    elif len(row)==11:
                        _ruang = _temp_ruang
                        _kelas = row[1] 
                        _total_kamar = row[2] 
                        _terisi_lk = row[3] 
                        _terisi_pr = row[4]
                        _total_terisi = row[5]
                        _kosong_lk = row[6]
                        _kosong_pr = row[7]
                        _total_kosong = row[8]
                        _waiting_list = row[9]
                        _last_update = row[10]
                    elif len(row)==10:
                        _ruang = _temp_ruang
                        if row[0].isnumeric():
                            _kelas = '-'
                        else:
                            _kelas = row[0] 
                        _total_kamar = row[1] 
                        _terisi_lk = row[2] 
                        _terisi_pr = row[3]
                        _total_terisi = row[4]
                        _kosong_lk = row[5]
                        _kosong_pr = row[6]
                        _total_kosong = row[7]
                        _waiting_list = row[8]
                        _last_update = row[9]
                    elif len(row)==9:
                        _ruang = _temp_ruang
                        _kelas = '-'
                        _total_kamar = row[0] 
                        _terisi_lk = row[1] 
                        _terisi_pr = row[2]
                        _total_terisi = row[3]
                        _kosong_lk = row[4]
                        _kosong_pr = row[5]
                        _total_kosong = row[6]
                        _waiting_list = row[7]
                        _last_update = row[8]
                    #print(_waiting_list)

                if _kosong_lk  == '-':
                    _kosong_lk = 0
                if _kosong_pr == '-':
                    _kosong_pr = 0
                if _waiting_list == 'N/A':
                    _waiting_list = 0
                if int(_total_kamar) > 0:
                    ruang = Jenis_Ruang.select().where(Jenis_Ruang.title==_ruang)
                    if ruang.count() < 1:
                        ruang = Jenis_Ruang.create(title=_ruang)
                    else:
                        ruang = ruang.get()
                    kelas = Kelas_Ruang.select().where(Kelas_Ruang.title==_kelas)
                    if kelas.count() < 1:
                        kelas = Kelas_Ruang.create(title=_kelas)
                    else:
                        kelas = kelas.get()   
                    update = dateparser.parse(_last_update)

                    occupation = Occupations.select().where(Occupations.rumahsakit==rs, 
                        Occupations.jenis_ruang==ruang, Occupations.kelas_ruang==kelas, 
                        Occupations.last_update==update)
                    if occupation.count() < 1:
                        occupation = Occupations.create(
                            rumahsakit=rs,
                            jenis_ruang=ruang,
                            kelas_ruang =kelas,
                            used_lk = _terisi_lk,
                            uses_pr = _terisi_pr,
                            used_ttl = _total_terisi,
                            vac_lk = _kosong_lk,
                            vac_pr = _kosong_pr,
                            vac_ttl  = _total_kosong,
                            waiting = _waiting_list,
                            last_update = update
                        )
            i = i +1
browser.stop_client()
browser.close()
browser.quit()
db.close()

