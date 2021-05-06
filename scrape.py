import pandas as pd
from bs4 import BeautifulSoup as soup
import csv
from pathlib import Path
import selenium
from selenium import webdriver
from flask import Flask, render_template, request, jsonify, redirect, make_response
import logging
import requests
import json
import random
from datetime import datetime, timedelta
import re
import os
import peewee as pw
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

class CovidOccupations(BaseModel):
    rumahsakit = pw.ForeignKeyField(RumahSakit)
    jenis_ruang = pw.ForeignKeyField(Jenis_Ruang)
    kelas_ruang = pw.ForeignKeyField(Kelas_Ruang)
    total_kamar = pw.IntegerField(default=0)
    total_terisi = pw.IntegerField(default=0)
    total_kosong = pw.IntegerField(default=0)
    last_update = pw.DateTimeField()
    created_at = pw.DateTimeField(default=datetime.utcnow())


db.connect()
db.create_tables([JenisFaskes, Province, RumahSakit, Jenis_Ruang, Kelas_Ruang, CovidOccupations], safe=True)


#Use csv Writer
#csvWriter = csv.writer(csvFile)
#csvWriter.writerow(['satker', 'nama', 'alamat', 'prov', 'jenis_ruang', 'ruang', 'total_kamar', 'total_terisi', 'total_kosong', 'last_update','lat','lng'])


faskes_df = pd.read_csv("data/list-faskes-filtered.csv",delimiter=',',encoding='ISO-8859-1')
#faskes_df.head()
browser = webdriver.Chrome(chrome_options=chrome_options)

for index, row in faskes_df.iterrows():
    
    satker = str(row['kode_rs'])
    nama_rs = str(row['nama_unit'])
    alamat =  str(row['alamat'])
    prov =  str(row['nama_prov'])
    lat =  row['lat']
    lon =  row['lng']
    
    prov  = Province.select().where(Province.prov_id==row['prov_id'])
    if prov.count() < 1:
        prov = Province.create(prov_id=row['prov_id'], nama_prov=row['nama_prov'])
    else:
        prov = prov.get()

    jenis = JenisFaskes.select().where(JenisFaskes.title==row['jenis_faskes'])
    if jenis.count() < 1:
        jenis =JenisFaskes.create(title=row['jenis_faskes'])
    else:
        jenis = jenis.get()
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
    else:
        rs = rs.get()

    _jenis_ruang = '-'
    _ruang = '-'
    _total_kamar = '0'
    _total_kosong = '0'
    _total_isi = '0'
    _last_update = '-'
    
    i=1
    while(i<=2): 
        #if (satker == '3471052'):
        link = 'http://yankes.kemkes.go.id/app/siranap/tempat_tidur?kode_rs='+satker+'&jenis='+str(i)
        browser.get(link)
        #print(r)
        data = browser.page_source
        url = soup(data,"lxml")
        print(str(satker)+'-'+str(i))
        card = url.find_all('div', attrs={'class':'card h-100'})
        #print(nama_rs)
        if card is not None:
            for col in card:
                _satker = satker
                _nama = nama_rs
                _alamat = alamat
                _prov = prov
                _lat = lat
                _long = lon
                if (i==1):
                    _jenis_ruang = 'Tempat Tidur Covid 19'
                elif (i==2):
                    _jenis_ruang = 'Tempat Tidur Non Covid 19'
                _ruang = col.find('h5', attrs={'class':'text-center'}).text
                #print(str(_ruang))
                _total_kamar = col.find('div', attrs={'class':'col-4 offset-2 pl-0 pr-0 col-md-4 offset-md-2 border text-center mr-2 pt-1'}).find('h1').text
                _total_kosong = col.find('div', attrs={'class':'col-4 pl-0 pr-0 col-md-4 border text-center pt-1'}).find('h1').text
                _total_terisi = int(_total_kamar) - int(_total_kosong)
                _last_update = col.find('div', attrs={'class':'ml-auto mt-1'}).text

                #csvWriter.writerow([_satker, _nama, _alamat, _prov, _jenis_ruang, _ruang, _total_kamar, _total_terisi, _total_kosong, _last_update, _lat, _long])
                
                ruang = Jenis_Ruang.select().where(Jenis_Ruang.title==_ruang)
                if ruang.count() < 1:
                    ruang = Jenis_Ruang.create(title=_ruang)
                else:
                    ruang = ruang.get()
                kelas = Kelas_Ruang.select().where(Kelas_Ruang.title==_jenis_ruang)
                if kelas.count() < 1:
                    kelas = Kelas_Ruang.create(title=_jenis_ruang)
                else:
                    kelas = kelas.get()   
                update = datetime.strptime(_last_update, '%d-%m-%Y %H:%M:%S')

                occupation = CovidOccupations.select().where(CovidOccupations.rumahsakit==rs, 
                    CovidOccupations.jenis_ruang==ruang, CovidOccupations.kelas_ruang==kelas, 
                    CovidOccupations.last_update==update)
                if occupation.count() < 1:
                    occupation = CovidOccupations.create(
                        rumahsakit=rs,
                        jenis_ruang=ruang,
                        kelas_ruang=kelas,
                        total_kamar = _total_kamar,
                        total_terisi = _total_terisi,
                        total_kosong = _total_kosong,                        
                        last_update = update
                    )
                    print('save update '+str(update))
        i+=1
browser.stop_client()
browser.close()
browser.quit()
db.close()

