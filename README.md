Realtime Bed Monitoring
===
Script untuk memonitor ketersediaan bed di rumah sakit di Indonesia


Requirements
---
- Python 3
- MySQL
- pipenv


Installation
---
- `git clone https://github.com/cekdiri/api_yankes.git`
- `cd api_yankes`
- Jika belum punya pipenv, jalankan `pip install pipenv`
- Jalankan `pipenv install`


Usage
---
    Copy file settings.cfg.tpl, rename jadi `settings.cfg`. Isikan data config.
    Jalankan `python main.py` di cron. 
    Jalankan `python serve.py` untuk menjalankan API servernya

