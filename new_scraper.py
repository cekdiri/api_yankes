from pathlib import Path
from flask import Flask, render_template, request, jsonify, redirect, make_response
import logging
import requests
import json
import random
from datetime import datetime, timedelta
import re
import os
import sys
import peewee as pw
from requests.packages.urllib3.exceptions import InsecureRequestWarning
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)
import requests_random_user_agent
#import cloudscraper
from bs4 import BeautifulSoup
import dateparser

starter  = datetime.now()
app = Flask(__name__)
dir_path = os.path.dirname(os.path.realpath(__file__))


app.config.from_pyfile(str(dir_path)+'/settings.cfg')

fmt = "%(levelname)s - %(asctime)s %(filename)s:%(lineno)d %(message)s"
formatter = logging.Formatter(fmt=fmt)
log_path = str(dir_path)+'/{}.log'.format(__name__)
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

class RumahSakitKab(BaseModel):
    # ada redundancy data di sini supaya data lama tidak rusak
    # ini tambahan untuk data lokasi kabupaten/kota dari rs
    rumahsakit = pw.ForeignKeyField(RumahSakit, backref='rskabkota')
    kabkota = pw.CharField(max_length=255)
    kabkota_kode = pw.CharField(max_length=255)
    provinsi = pw.CharField(max_length=255)


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
db.create_tables([JenisFaskes, Province, RumahSakit, Jenis_Ruang, Kelas_Ruang, CovidOccupations, RumahSakitKab], safe=True)


faskes_df = json.loads(open(str(dir_path)+"/data/rumah_sakit_all.json", "r").read())

idprov = 1
for key, row in faskes_df.items():
    satker = str(row['kode'])
    nama_rs = str(row['nama'])
    alamat =  str(row['alamat'])
    lat =  row['lat']
    lon =  row['lon']
    if row['provinsi']:
        prov  = Province.select().where(Province.nama_prov==row['provinsi'])
        if prov.count() < 1:
            prov = Province.create(prov_id=idprov, nama_prov=row['provinsi'])
            idprov = idprov + 1
        else:
            prov = prov.get()
    else:
        prov = None
    try:
        jenisfaskes = row['tipe']
    except:
        jenisfaskes = 'Rumah Sakit'
    jenis = JenisFaskes.select().where(JenisFaskes.title==jenisfaskes)
    if jenis.count() < 1:
        jenis =JenisFaskes.create(title=jenisfaskes)
    else:
        jenis = jenis.get()
    rs = RumahSakit.select().where(RumahSakit.kode_rs==row['kode'])
    if rs.count() < 1:
        if row['provinsi']:
            rs = RumahSakit.create(prov_id=prov, 
                kode_rs=row['kode'], 
                nama_unit=row['nama'], 
                alamat=row['alamat'], 
                jenis_faskes=jenis,
                lat = row['lat'],
                lon = row['lon']
            )
    else:
        rs = rs.get()
    kabkot = RumahSakitKab.select().where(RumahSakitKab.rumahsakit==rs)
    if kabkot.count() < 1:
        if 'kabkota' in row.keys():
            kabkot = RumahSakitKab.create(rumahsakit=rs, kabkota=row['kabkota'], kabkota_kode=row['kode_kabkota'], provinsi=row['provinsi'])

    _jenis_ruang = '-'
    _ruang = '-'
    _total_kamar = '0'
    _total_kosong = '0'
    _total_isi = '0'
    _last_update = '-'
    
    i=1
    while(i<=2): 
        #if (satker == '3471052'):
        #s = cloudscraper.create_scraper()
        link = 'http://yankes.kemkes.go.id/app/siranap/tempat_tidur?kode_rs='+satker+'&jenis='+str(i)
        s = requests.Session()
        try:
            r = s.get(link)
            reqs = True
        except requests.exceptions.ConnectionError:
            reqs = False
        try:
            data = r.content
            lanjut = True
        except:
            data = None 
            lanjut = False
        if not reqs:
            import selenium
            from selenium import webdriver
            from selenium.common.exceptions import WebDriverException
            chrome_options = webdriver.ChromeOptions()
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--window-size=1420,1080')
            chrome_options.add_argument('--headless')
            chrome_options.add_argument('--disable-gpu')
            browser = webdriver.Chrome(chrome_options=chrome_options)
            try:
                browser.get(link)
            except WebDriverException:
                lanjut = False
            #print(r)
            try:
                data = browser.page_source
                lanjut = True
            except:
                lanjut = False
            browser.stop_client()
            browser.close()
            browser.quit()

        if lanjut:
            url = BeautifulSoup(data,"lxml")
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
db.close()
ended = datetime.now() - starter 
print('took %s seconds' % (str(timedelta(seconds=ended.total_seconds())),))