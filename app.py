import os
import sqlite3
import csv
import io
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, session, flash, make_response, g
from werkzeug.security import generate_password_hash, check_password_hash
from fpdf import FPDF

app = Flask(__name__)
app.secret_key = 'tajni_kljuc_mladinovic_doo'
DATABASE = 'database.db'

def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(DATABASE, timeout=30)
        g.db.row_factory = sqlite3.Row
        g.db.execute('PRAGMA journal_mode=WAL;')
        g.db.execute('PRAGMA synchronous=NORMAL;')
    return g.db

@app.teardown_appcontext
def close_db(error):
    db = g.pop('db', None)
    if db is not None:
        db.close()

def dohvati_trenutno_vrijeme():
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')

def init_db():
    if not os.path.exists(DATABASE):
        with app.app_context():
            db = get_db()
            with open('schema.sql', mode='r') as f:
                db.cursor().executescript(f.read())
            
            default_users = [
                ('admin', generate_password_hash('123456'), 'Luka', 'Mladinović', 'admin'),
                ('poslovoda', generate_password_hash('123456'), 'Marko', 'Horvat', 'poslovoda'),
                ('skladistar', generate_password_hash('123456'), 'Ivan', 'Ivić', 'skladistar')
            ]
            
            cursor = db.cursor()
            for user in default_users:
                cursor.execute(
                    "INSERT INTO korisnici (korisnicko_ime, lozinka, ime, prezime, uloga) VALUES (?, ?, ?, ?, ?)",
                    user
                )
            
            dobavljaci = [
                ('MS San d.o.o.', 'Petar Perić', 'prodaja@mssan.hr', '01/3654-321'),
                ('Asbis d.o.o.', 'Ana Anić', 'nabava@asbis.hr', '01/6543-210'),
                ('Microline d.o.o.', 'Igor Ivić', 'info@microline.hr', '01/2345-678')
            ]
            cursor.executemany("INSERT INTO dobavljaci (naziv, kontakt_osoba, email, telefon) VALUES (?, ?, ?, ?)", dobavljaci)

            kategorije = [
                ('Procesori i matične ploče',),
                ('Grafičke kartice',),
                ('RAM i pohrana (SSD/HDD)',),
                ('Monitori i periferija',),
                ('Mrežna oprema i napajanja',),
                ('Mobilni i pametni uređaji',)
            ]
            cursor.executemany("INSERT INTO kategorije (naziv) VALUES (?)", kategorije)

            lokacije = [
                ('Sektor A', 'R1', 'P1', 20), ('Sektor A', 'R1', 'P2', 20),
                ('Sektor A', 'R2', 'P1', 20), ('Sektor A', 'R2', 'P2', 20),
                ('Sektor B', 'R1', 'P1', 20), ('Sektor B', 'R1', 'P2', 20),
                ('Sektor B', 'R2', 'P1', 20), ('Sektor B', 'R2', 'P2', 20),
                ('Sektor C', 'R1', 'P1', 20), ('Sektor C', 'R1', 'P2', 20),
                ('Sektor C', 'R2', 'P1', 20), ('Sektor C', 'R2', 'P2', 20),
                ('Sektor D', 'R1', 'P1', 20), ('Sektor D', 'R1', 'P2', 20),
                ('Sektor D', 'R2', 'P1', 20), ('Sektor D', 'R2', 'P2', 20)
            ]
            cursor.executemany("INSERT INTO lokacije (sektor, regal, polica, kapacitet) VALUES (?, ?, ?, ?)", lokacije)

            proizvodi = [
                ('Intel Core i7-13700K Box', 'CPU-INT-13700', 12, 3, 420.00, 1, 1, 1),
                ('NVIDIA GeForce RTX 4070 12GB', 'GPU-NV-4070', 4, 5, 680.00, 2, 2, 2),
                ('Kingston Fury Beast DDR5 32GB Kit', 'RAM-KG-532', 20, 10, 115.00, 3, 3, 1),
                ('Samsung 980 Pro SSD 1TB NVMe', 'SSD-SAM-980', 18, 5, 95.00, 3, 4, 3),
                ('Monitor Dell UltraSharp 27" 4K', 'MON-DELL-27U', 7, 2, 550.00, 4, 5, 2)
            ]
            cursor.executemany('''
                INSERT INTO proizvodi (naziv, sifra, kolicina, min_kolicina, cijena, kategorija_id, lokacija_id, dobavljac_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', proizvodi)
            
            db.commit()
            print("Baza podataka za Mladinović d.o.o. uspješno kreirana!")

def nadogradi_bazu_za_povijest():
    with app.app_context():
        db = get_db()
        try:
            db.execute('ALTER TABLE transakcije ADD COLUMN zabiljezeni_naziv TEXT')
            db.execute('ALTER TABLE transakcije ADD COLUMN zabiljezena_sifra TEXT')
            transakcije = db.execute('SELECT t.id, p.naziv, p.sifra FROM transakcije t JOIN proizvodi p ON t.proizvod_id = p.id').fetchall()
            for t in transakcije:
                db.execute('UPDATE transakcije SET zabiljezeni_naziv = ?, zabiljezena_sifra = ? WHERE id = ?', (t['naziv'], t['sifra'], t['id']))
            db.execute('ALTER TABLE narudzbe ADD COLUMN zabiljezeni_naziv TEXT')
            db.execute('ALTER TABLE narudzbe ADD COLUMN zabiljezena_sifra TEXT')
            narudzbe = db.execute('SELECT n.id, p.naziv, p.sifra FROM narudzbe n JOIN proizvodi p ON n.proizvod_id = p.id').fetchall()
            for n in narudzbe:
                db.execute('UPDATE narudzbe SET zabiljezeni_naziv = ?, zabiljezena_sifra = ? WHERE id = ?', (n['naziv'], n['sifra'], n['id']))
            db.commit()
            print("Baza uspješno nadograđena za trajno pamćenje povijesti artikala!")
        except sqlite3.OperationalError:
            pass

        try:
            duplikati = db.execute('''
                SELECT sifra, lokacija_id, SUM(kolicina) as ukupno, MIN(id) as glavni_id
                FROM proizvodi
                WHERE lokacija_id IS NOT NULL
                GROUP BY sifra, lokacija_id
                HAVING COUNT(*) > 1
            ''').fetchall()

            for d in duplikati:
                sifra = d['sifra']
                lok_id = d['lokacija_id']
                glavni_id = d['glavni_id']
                ukupno = d['ukupno']

                ostali = db.execute('SELECT id FROM proizvodi WHERE sifra = ? AND lokacija_id = ? AND id != ?', (sifra, lok_id, glavni_id)).fetchall()
                for o in ostali:
                    star_id = o['id']
                    db.execute('UPDATE transakcije SET proizvod_id = ? WHERE proizvod_id = ?', (glavni_id, star_id))
                    db.execute('UPDATE narudzbe SET proizvod_id = ? WHERE proizvod_id = ?', (glavni_id, star_id))
                    db.execute('DELETE FROM proizvodi WHERE id = ?', (star_id,))

                db.execute('UPDATE proizvodi SET kolicina = ? WHERE id = ?', (ukupno, glavni_id))
            db.commit()
        except Exception as e:
            print("Greška pri spajanju duplikata:", e)

def očisti_tekst_za_pdf(tekst):
    if not tekst:
        return ""
    zamjene = {
        'č': 'c', 'Č': 'C', 'ć': 'c', 'Ć': 'C',
        'đ': 'dj', 'Đ': 'Dj', 'š': 's', 'Š': 'S', 'ž': 'z', 'Ž': 'Z'
    }
    for k, v in zamjene.items():
        tekst = tekst.replace(k, v)
    return tekst

def formatiraj_cijenu(iznos):
    if iznos is None:
        iznos = 0.0
    return "{:,.2f}".format(float(iznos)).replace(',', 'X').replace('.', ',').replace('X', '.')

def vrati_gramaticku_poruku(slobodno):
    if slobodno <= 0:
        return "Greška: Na odabranoj lokaciji nema više slobodnih mjesta!"
    elif slobodno == 1:
        return "Greška: Odabrana lokacija nema dovoljno kapaciteta! Preostalo je samo 1 slobodno mjesto."
    elif slobodno in [2, 3, 4]:
        return f"Greška: Odabrana lokacija nema dovoljno kapaciteta! Preostala su samo {slobodno} slobodna mjesta."
    else:
        return f"Greška: Odabrana lokacija nema dovoljno kapaciteta! Preostalo je samo {slobodno} slobodnih mjesta."

def provjeri_kapacitet_lokacije(db, lokacija_id, dodatna_kolicina, ignoriraj_proizvod_id=None):
    lokacija = db.execute('SELECT * FROM lokacije WHERE id = ?', (lokacija_id,)).fetchone()
    if not lokacija:
        return True, 0

    zauzeto_ukupno = db.execute(
        'SELECT SUM(kolicina) as ukupno FROM proizvodi WHERE lokacija_id = ?',
        (lokacija_id,)
    ).fetchone()['ukupno'] or 0

    stvarno_slobodno = max(0, lokacija['kapacitet'] - zauzeto_ukupno)

    if ignoriraj_proizvod_id:
        zauzeto_ostali = db.execute(
            'SELECT SUM(kolicina) as ukupno FROM proizvodi WHERE lokacija_id = ? AND id != ?',
            (lokacija_id, ignoriraj_proizvod_id)
        ).fetchone()['ukupno'] or 0
        slobodno_za_provjeru = max(0, lokacija['kapacitet'] - zauzeto_ostali)
        if dodatna_kolicina > slobodno_za_provjeru:
            return False, stvarno_slobodno
    else:
        if dodatna_kolicina > stvarno_slobodno:
            return False, stvarno_slobodno

    return True, stvarno_slobodno

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        korisnicko_ime = request.form['korisnicko_ime']
        lozinka = request.form['lozinka']
        
        db = get_db()
        korisnik = db.execute('SELECT * FROM korisnici WHERE korisnicko_ime = ?', (korisnicko_ime,)).fetchone()
        
        if korisnik and check_password_hash(korisnik['lozinka'], lozinka):
            session['user_id'] = korisnik['id']
            session['korisnicko_ime'] = korisnik['korisnicko_ime']
            session['ime'] = korisnik['ime']
            session['prezime'] = korisnik['prezime']
            session['uloga'] = korisnik['uloga']
            return redirect(url_for('index'))
        else:
            flash('Pogrešno korisničko ime ili lozinka!', 'error')
            
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    db = get_db()
    lokacije = db.execute('SELECT * FROM lokacije ORDER BY sektor ASC, regal ASC, polica ASC').fetchall()
    proizvodi = db.execute('''
        SELECT p.*, l.sektor, l.regal, l.polica 
        FROM proizvodi p 
        LEFT JOIN lokacije l ON p.lokacija_id = l.id
        ORDER BY p.naziv ASC, l.sektor ASC, l.regal ASC, l.polica ASC
    ''').fetchall()
    
    lokacije_statistika = []
    for loc in lokacije:
        zauzeto = sum([p['kolicina'] for p in proizvodi if p['lokacija_id'] == loc['id']])
        postotak = min(100, int((zauzeto / loc['kapacitet']) * 100)) if loc['kapacitet'] > 0 else 0
        lokacije_statistika.append({
            'id': loc['id'],
            'sektor': loc['sektor'],
            'regal': loc['regal'],
            'polica': loc['polica'],
            'kapacitet': loc['kapacitet'],
            'zauzeto': zauzeto,
            'postotak': postotak
        })

    kriticni_proizvodi = db.execute('''
        SELECT p.id, p.naziv, p.sifra, SUM(p.kolicina) as ukupna_kolicina, p.min_kolicina
        FROM proizvodi p
        GROUP BY p.sifra
        HAVING ukupna_kolicina <= p.min_kolicina
        ORDER BY p.naziv ASC
    ''').fetchall()

    svi_sektori = sorted(list(set([l['sektor'] for l in lokacije])))
    
    return render_template('index.html', lokacije=lokacije_statistika, proizvodi=proizvodi, kriticni=kriticni_proizvodi, sektori=svi_sektori, active_page='tlocrt')

@app.route('/proizvodi', methods=['GET', 'POST'])
def upravljanje_proizvodima():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    db = get_db()
    
    if request.method == 'POST':
        if session['uloga'] == 'skladistar':
            flash('Skladištari nemaju ovlasti za unos novih artikala!', 'error')
            return redirect(url_for('upravljanje_proizvodima'))
            
        naziv = request.form.get('naziv', '').strip()
        sifra = request.form.get('sifra', '').strip()
        kolicina_raw = request.form.get('kolicina', '0').strip()
        min_kolicina_raw = request.form.get('min_kolicina', '0').strip()
        cijena_raw = request.form.get('cijena', '0').strip().replace(',', '.')
        kategorija_id = request.form.get('kategorija_id')
        dobavljac_id = request.form.get('dobavljac_id')
        lokacija_id_raw = request.form.get('lokacija_id')
        
        sifra_duplikat = db.execute('SELECT id FROM proizvodi WHERE LOWER(sifra) = LOWER(?)', (sifra,)).fetchone()
        if sifra_duplikat:
            flash(f'Greška: Artikl sa šifrom "{sifra}" već postoji u katalogu!', 'error')
            return redirect(url_for('upravljanje_proizvodima'))

        if dobavljac_id:
            naziv_dob_duplikat = db.execute('SELECT id FROM proizvodi WHERE LOWER(naziv) = LOWER(?) AND dobavljac_id = ?', (naziv, dobavljac_id)).fetchone()
            if naziv_dob_duplikat:
                flash(f'Greška: Artikl s nazivom "{naziv}" već postoji kod odabranog dobavljača!', 'error')
                return redirect(url_for('upravljanje_proizvodima'))

        try:
            kolicina = int(kolicina_raw) if kolicina_raw else 0
            min_kolicina = int(min_kolicina_raw) if min_kolicina_raw else 0
            cijena = float(cijena_raw) if cijena_raw else 0.0
        except ValueError:
            flash('Greška: Uneseni su neispravni brojčani podaci!', 'error')
            return redirect(url_for('upravljanje_proizvodima'))

        lokacija_id = None
        poruka_lokacije = ""

        if kolicina > 0 and lokacija_id_raw:
            lokacija_id = int(lokacija_id_raw)
            moze_stati, slobodno = provjeri_kapacitet_lokacije(db, lokacija_id, kolicina)
            if not moze_stati:
                flash(vrati_gramaticku_poruku(slobodno), 'error')
                return redirect(url_for('upravljanje_proizvodima'))

            lok = db.execute('SELECT sektor, regal, polica FROM lokacije WHERE id = ?', (lokacija_id,)).fetchone()
            if lok:
                poruka_lokacije = f" [Smješteno na: {lok['sektor']} {lok['regal']}-{lok['polica']}]"

        db.execute('''
            INSERT INTO proizvodi (naziv, sifra, kolicina, min_kolicina, cijena, kategorija_id, lokacija_id, dobavljac_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (naziv, sifra, kolicina, min_kolicina, cijena, kategorija_id, lokacija_id, dobavljac_id))
        
        proizvod_id = db.execute('SELECT last_insert_rowid()').fetchone()[0]
        napomena_transakcija = f"Početni unos u katalog{poruka_lokacije}"

        db.execute('''
            INSERT INTO transakcije (proizvod_id, korisnik_id, tip, kolicina, datum, napomena, zabiljezeni_naziv, zabiljezena_sifra)
            VALUES (?, ?, 'ULAZ', ?, ?, ?, ?, ?)
        ''', (proizvod_id, session['user_id'], kolicina, dohvati_trenutno_vrijeme(), napomena_transakcija, naziv, sifra))
            
        db.commit()
        flash(f'Novi artikl "{naziv}" je uspješno dodan u katalog!', 'success')
        return redirect(url_for('upravljanje_proizvodima'))

    # DODANO SORTIRANJE PO LOKACIJAMA KAKO BI POPIS POLICA UNUTAR ARTIKLA UVIJEK BIO ABECEDNI
    svi_redovi = db.execute('''
        SELECT p.*, k.naziv as kategorija_naziv, l.sektor, l.regal, l.polica, d.naziv as dobavljac_naziv
        FROM proizvodi p
        LEFT JOIN kategorije k ON p.kategorija_id = k.id
        LEFT JOIN lokacije l ON p.lokacija_id = l.id
        LEFT JOIN dobavljaci d ON p.dobavljac_id = d.id
        ORDER BY p.naziv ASC, l.sektor ASC, l.regal ASC, l.polica ASC
    ''').fetchall()

    proizvodi_map = {}
    for p in svi_redovi:
        sifra = p['sifra']
        if sifra not in proizvodi_map:
            proizvodi_map[sifra] = {
                'id': p['id'],
                'sifra': p['sifra'],
                'naziv': p['naziv'],
                'cijena': p['cijena'],
                'min_kolicina': p['min_kolicina'],
                'kategorija_naziv': p['kategorija_naziv'],
                'dobavljac_naziv': p['dobavljac_naziv'],
                'ukupna_kolicina': 0,
                'lokacije_lista': []
            }
        proizvodi_map[sifra]['ukupna_kolicina'] += p['kolicina']
        if p['sektor']:
            proizvodi_map[sifra]['lokacije_lista'].append({
                'id': p['id'],
                'lokacija_id': p['lokacija_id'],
                'sektor': p['sektor'],
                'regal': p['regal'],
                'polica': p['polica'],
                'kolicina': p['kolicina']
            })

    proizvodi = list(proizvodi_map.values())

    kategorije = db.execute('SELECT * FROM kategorije ORDER BY naziv ASC').fetchall()
    dobavljaci = db.execute('SELECT * FROM dobavljaci ORDER BY id ASC').fetchall()
    
    lokacije_raw = db.execute('SELECT * FROM lokacije ORDER BY sektor ASC, regal ASC, polica ASC').fetchall()
    proizvodi_raw = db.execute('SELECT lokacija_id, kolicina FROM proizvodi').fetchall()
    lokacije_stat = []
    for loc in lokacije_raw:
        zauzeto = sum([p['kolicina'] for p in proizvodi_raw if p['lokacija_id'] == loc['id']])
        slobodno = max(0, loc['kapacitet'] - zauzeto)
        lokacije_stat.append({
            'id': loc['id'],
            'sektor': loc['sektor'],
            'regal': loc['regal'],
            'polica': loc['polica'],
            'slobodno': slobodno
        })
    
    return render_template('proizvodi.html', proizvodi=proizvodi, kategorije=kategorije, dobavljaci=dobavljaci, lokacije=lokacije_stat, active_page='proizvodi')

@app.route('/proizvod/uredi/<int:id>', methods=['GET', 'POST'])
def uredi_proizvod(id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    if session['uloga'] == 'skladistar':
        flash('Skladištari nemaju ovlasti za uređivanje artikala!', 'error')
        return redirect(url_for('upravljanje_proizvodima'))

    db = get_db()
    proizvod = db.execute('SELECT * FROM proizvodi WHERE id = ?', (id,)).fetchone()
    if not proizvod:
        flash('Proizvod nije pronađen!', 'error')
        return redirect(url_for('upravljanje_proizvodima'))

    if request.method == 'POST':
        naziv = request.form.get('naziv', '').strip()
        sifra = request.form.get('sifra', '').strip()
        kolicina_raw = request.form.get('kolicina', '0').strip()
        min_kolicina_raw = request.form.get('min_kolicina', '0').strip()
        cijena_raw = request.form.get('cijena', '0').strip().replace(',', '.')
        kategorija_id = request.form.get('kategorija_id')
        lokacija_id = request.form.get('lokacija_id')
        dobavljac_id = request.form.get('dobavljac_id')

        sifra_duplikat = db.execute('SELECT id FROM proizvodi WHERE LOWER(sifra) = LOWER(?) AND sifra != ?', (sifra, proizvod['sifra'])).fetchone()
        if sifra_duplikat:
            flash(f'Greška: Šifra "{sifra}" je već dodijeljena drugom artiklu!', 'error')
            return redirect(url_for('uredi_proizvod', id=id))

        if dobavljac_id:
            naziv_dob_duplikat = db.execute('SELECT id FROM proizvodi WHERE LOWER(naziv) = LOWER(?) AND dobavljac_id = ? AND sifra != ?', (naziv, dobavljac_id, proizvod['sifra'])).fetchone()
            if naziv_dob_duplikat:
                flash(f'Greška: Artikl s nazivom "{naziv}" već postoji kod odabranog dobavljača!', 'error')
                return redirect(url_for('uredi_proizvod', id=id))

        try:
            kolicina = int(kolicina_raw) if kolicina_raw else 0
            min_kolicina = int(min_kolicina_raw) if min_kolicina_raw else 0
            cijena = float(cijena_raw) if cijena_raw else 0.0
        except ValueError:
            flash('Greška: Uneseni su neispravni brojčani podaci!', 'error')
            return redirect(url_for('uredi_proizvod', id=id))

        if lokacija_id:
            lokacija_id_int = int(lokacija_id)
            ignoriraj = id if lokacija_id_int == proizvod['lokacija_id'] else None
            moze_stati, slobodno = provjeri_kapacitet_lokacije(db, lokacija_id_int, kolicina, ignoriraj_proizvod_id=ignoriraj)
            if not moze_stati:
                flash(vrati_gramaticku_poruku(slobodno), 'error')
                return redirect(url_for('uredi_proizvod', id=id))

        try:
            if kolicina == 0:
                ostali = db.execute('SELECT id FROM proizvodi WHERE sifra = ? AND id != ?', (proizvod['sifra'], id)).fetchall()
                if ostali:
                    glavni_id = ostali[0]['id']
                    db.execute('UPDATE transakcije SET proizvod_id = ? WHERE proizvod_id = ?', (glavni_id, id))
                    db.execute('UPDATE narudzbe SET proizvod_id = ? WHERE proizvod_id = ?', (glavni_id, id))
                    db.execute('DELETE FROM proizvodi WHERE id = ?', (id,))
                else:
                    db.execute('UPDATE proizvodi SET kolicina = 0, lokacija_id = NULL WHERE id = ?', (id,))
            else:
                db.execute('UPDATE proizvodi SET kolicina = ?, lokacija_id = ? WHERE id = ?', (kolicina, lokacija_id, id))

            stara_sifra = proizvod['sifra']
            db.execute('''
                UPDATE proizvodi
                SET naziv = ?, sifra = ?, min_kolicina = ?, cijena = ?, kategorija_id = ?, dobavljac_id = ?
                WHERE sifra = ?
            ''', (naziv, sifra, min_kolicina, cijena, kategorija_id, dobavljac_id, stara_sifra))
            
            db.commit()
            flash(f'Artikl "{naziv}" je uspješno ažuriran!', 'success')
            return redirect(url_for('upravljanje_proizvodima'))
        except sqlite3.IntegrityError:
            flash('Greška u bazi podataka kod uređivanja artikla!', 'error')
            return redirect(url_for('uredi_proizvod', id=id))

    kategorije = db.execute('SELECT * FROM kategorije ORDER BY naziv ASC').fetchall()
    dobavljaci = db.execute('SELECT * FROM dobavljaci ORDER BY id ASC').fetchall()
    
    lokacije_raw = db.execute('SELECT * FROM lokacije ORDER BY sektor ASC, regal ASC, polica ASC').fetchall()
    proizvodi_raw = db.execute('SELECT lokacija_id, kolicina FROM proizvodi').fetchall()
    lokacije_stat = []
    for loc in lokacije_raw:
        zauzeto = sum([p['kolicina'] for p in proizvodi_raw if p['lokacija_id'] == loc['id']])
        slobodno = max(0, loc['kapacitet'] - zauzeto)
        lokacije_stat.append({
            'id': loc['id'],
            'sektor': loc['sektor'],
            'regal': loc['regal'],
            'polica': loc['polica'],
            'slobodno': slobodno
        })

    return render_template('uredi_proizvod.html', proizvod=proizvod, kategorije=kategorije, lokacije=lokacije_stat, dobavljaci=dobavljaci, active_page='proizvodi')

@app.route('/proizvod/promjena_zalihe/<int:id>', methods=['POST'])
def promjena_zalihe(id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    db = get_db()
    tip = request.form['tip']
    promjena_kolicine = int(request.form['kolicina'])
    napomena = request.form.get('napomena', '').strip()
    dodaj_na_staru = int(request.form.get('dodaj_na_staru', 0))
    nova_lok_id_raw = request.form.get('nova_lokacija_id')

    proizvod = db.execute('SELECT * FROM proizvodi WHERE id = ?', (id,)).fetchone()
    if not proizvod:
        flash('Proizvod nije pronađen!', 'error')
        return redirect(url_for('upravljanje_proizvodima'))

    if tip == 'IZLAZ':
        if promjena_kolicine > proizvod['kolicina']:
            flash('Greška: Nedovoljna količina artikla na ovoj polici za izdavanje!', 'error')
            return redirect(url_for('upravljanje_proizvodima'))

        nova_kolicina = proizvod['kolicina'] - promjena_kolicine
        lok_id = proizvod['lokacija_id']
        dodatak_lokacije = ""
        if lok_id:
            lok = db.execute('SELECT sektor, regal, polica FROM lokacije WHERE id = ?', (lok_id,)).fetchone()
            if lok:
                dodatak_lokacije = f"[Izdano sa: {lok['sektor']} {lok['regal']}-{lok['polica']}]"

        finalna_napomena = f"{napomena} {dodatak_lokacije}".strip()

        if nova_kolicina == 0:
            ostali = db.execute('SELECT id FROM proizvodi WHERE sifra = ? AND id != ?', (proizvod['sifra'], id)).fetchall()
            if ostali:
                glavni_id = ostali[0]['id']
                db.execute('UPDATE transakcije SET proizvod_id = ? WHERE proizvod_id = ?', (glavni_id, id))
                db.execute('UPDATE narudzbe SET proizvod_id = ? WHERE proizvod_id = ?', (glavni_id, id))
                db.execute('DELETE FROM proizvodi WHERE id = ?', (id,))
                transakcija_proizvod_id = glavni_id
            else:
                db.execute('UPDATE proizvodi SET kolicina = 0, lokacija_id = NULL WHERE id = ?', (id,))
                transakcija_proizvod_id = id
        else:
            db.execute('UPDATE proizvodi SET kolicina = ? WHERE id = ?', (nova_kolicina, id))
            transakcija_proizvod_id = id

        db.execute('''
            INSERT INTO transakcije (proizvod_id, korisnik_id, tip, kolicina, datum, napomena, zabiljezeni_naziv, zabiljezena_sifra)
            VALUES (?, ?, 'IZLAZ', ?, ?, ?, ?, ?)
        ''', (transakcija_proizvod_id, session['user_id'], promjena_kolicine, dohvati_trenutno_vrijeme(), finalna_napomena, proizvod['naziv'], proizvod['sifra']))

        db.commit()
        flash(f'Provedeno: IZLAZ od {promjena_kolicine} kom za "{proizvod["naziv"]}".', 'success')
        return redirect(url_for('upravljanje_proizvodima'))

    poruke_izvjestaj = []

    if dodaj_na_staru > 0 and proizvod['lokacija_id']:
        moze_stati, slobodno = provjeri_kapacitet_lokacije(db, proizvod['lokacija_id'], dodaj_na_staru)
        if not moze_stati:
            flash(vrati_gramaticku_poruku(slobodno), 'error')
            return redirect(url_for('upravljanje_proizvodima'))

        db.execute('UPDATE proizvodi SET kolicina = kolicina + ? WHERE id = ?', (dodaj_na_staru, id))
        lok = db.execute('SELECT sektor, regal, polica FROM lokacije WHERE id = ?', (proizvod['lokacija_id'],)).fetchone()
        nap_stara = f"{napomena} [Smješteno na: {lok['sektor']} {lok['regal']}-{lok['polica']}]".strip()
        db.execute('''
            INSERT INTO transakcije (proizvod_id, korisnik_id, tip, kolicina, datum, napomena, zabiljezeni_naziv, zabiljezena_sifra)
            VALUES (?, ?, 'ULAZ', ?, ?, ?, ?, ?)
        ''', (id, session['user_id'], dodaj_na_staru, dohvati_trenutno_vrijeme(), nap_stara, proizvod['naziv'], proizvod['sifra']))
        poruke_izvjestaj.append(f"+{dodaj_na_staru} kom na {lok['sektor']} ({lok['regal']}-{lok['polica']})")

    if nova_lok_id_raw:
        nova_lok_id = int(nova_lok_id_raw)
        moze_stati, slobodno = provjeri_kapacitet_lokacije(db, nova_lok_id, promjena_kolicine)
        if not moze_stati:
            flash(vrati_gramaticku_poruku(slobodno), 'error')
            return redirect(url_for('upravljanje_proizvodima'))

        nova_lok = db.execute('SELECT sektor, regal, polica FROM lokacije WHERE id = ?', (nova_lok_id,)).fetchone()
        postojece_na_novoj = db.execute(
            'SELECT * FROM proizvodi WHERE sifra = ? AND lokacija_id = ?',
            (proizvod['sifra'], nova_lok_id)
        ).fetchone()

        if postojece_na_novoj:
            db.execute('UPDATE proizvodi SET kolicina = kolicina + ? WHERE id = ?', (promjena_kolicine, postojece_na_novoj['id']))
            dest_id = postojece_na_novoj['id']
        elif not proizvod['lokacija_id']:
            db.execute('UPDATE proizvodi SET kolicina = kolicina + ?, lokacija_id = ? WHERE id = ?', (promjena_kolicine, nova_lok_id, id))
            dest_id = id
        else:
            db.execute('''
                INSERT INTO proizvodi (naziv, sifra, kolicina, min_kolicina, cijena, kategorija_id, lokacija_id, dobavljac_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (proizvod['naziv'], proizvod['sifra'], promjena_kolicine, proizvod['min_kolicina'], proizvod['cijena'], proizvod['kategorija_id'], nova_lok_id, proizvod['dobavljac_id']))
            dest_id = db.execute('SELECT last_insert_rowid()').fetchone()[0]

        nap_nova = f"{napomena} [Smješteno na: {nova_lok['sektor']} {nova_lok['regal']}-{nova_lok['polica']}]".strip()
        db.execute('''
            INSERT INTO transakcije (proizvod_id, korisnik_id, tip, kolicina, datum, napomena, zabiljezeni_naziv, zabiljezena_sifra)
            VALUES (?, ?, 'ULAZ', ?, ?, ?, ?, ?)
        ''', (dest_id, session['user_id'], promjena_kolicine, dohvati_trenutno_vrijeme(), nap_nova, proizvod['naziv'], proizvod['sifra']))
        poruke_izvjestaj.append(f"+{promjena_kolicine} kom na {nova_lok['sektor']} ({nova_lok['regal']}-{nova_lok['polica']})")

    elif dodaj_na_staru == 0 and not nova_lok_id_raw:
        lok_id = proizvod['lokacija_id']
        if lok_id:
            moze_stati, slobodno = provjeri_kapacitet_lokacije(db, lok_id, promjena_kolicine)
            if not moze_stati:
                flash(vrati_gramaticku_poruku(slobodno), 'error')
                return redirect(url_for('upravljanje_proizvodima'))

            db.execute('UPDATE proizvodi SET kolicina = kolicina + ? WHERE id = ?', (promjena_kolicine, id))
            lok = db.execute('SELECT sektor, regal, polica FROM lokacije WHERE id = ?', (lok_id,)).fetchone()
            nap = f"{napomena} [Smješteno na: {lok['sektor']} {lok['regal']}-{lok['polica']}]".strip()
        else:
            db.execute('UPDATE proizvodi SET kolicina = kolicina + ? WHERE id = ?', (promjena_kolicine, id))
            nap = napomena.strip()

        db.execute('''
            INSERT INTO transakcije (proizvod_id, korisnik_id, tip, kolicina, datum, napomena, zabiljezeni_naziv, zabiljezena_sifra)
            VALUES (?, ?, 'ULAZ', ?, ?, ?, ?, ?)
        ''', (id, session['user_id'], promjena_kolicine, dohvati_trenutno_vrijeme(), nap, proizvod['naziv'], proizvod['sifra']))
        poruke_izvjestaj.append(f"+{promjena_kolicine} kom za \"{proizvod['naziv']}\"")

    db.commit()
    spojene_poruke = " i ".join(poruke_izvjestaj)
    flash(f'Provedeno: ULAZ ({spojene_poruke}).', 'success')
    return redirect(url_for('upravljanje_proizvodima'))

@app.route('/proizvod/obrisi/<int:id>', methods=['POST'])
def obrisi_proizvod(id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    if session['uloga'] == 'skladistar':
        flash('Skladištari nemaju ovlasti za brisanje artikala!', 'error')
        return redirect(url_for('upravljanje_proizvodima'))
        
    db = get_db()
    proizvod = db.execute('SELECT naziv, sifra FROM proizvodi WHERE id = ?', (id,)).fetchone()
    if proizvod:
        sifra = proizvod['sifra']
        naziv = proizvod['naziv']
        
        sve_lokacije = db.execute('SELECT kolicina FROM proizvodi WHERE sifra = ?', (sifra,)).fetchall()
        ukupna_kolicina = sum([p['kolicina'] for p in sve_lokacije])
        
        db.execute('''
            INSERT INTO transakcije (proizvod_id, korisnik_id, tip, kolicina, datum, napomena, zabiljezeni_naziv, zabiljezena_sifra)
            VALUES (?, ?, 'IZLAZ', ?, ?, 'Artikl je trajno obrisan iz kataloga', ?, ?)
        ''', (id, session['user_id'], ukupna_kolicina, dohvati_trenutno_vrijeme(), naziv, sifra))
        
        db.execute('DELETE FROM proizvodi WHERE sifra = ?', (sifra,))
        db.commit()
        flash('Artikl je uklonjen iz kataloga!', 'success')
    else:
        flash('Proizvod nije pronađen!', 'error')
    return redirect(url_for('upravljanje_proizvodima'))

@app.route('/premjestanje', methods=['GET', 'POST'])
def premjestanje():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    db = get_db()

    if request.method == 'POST':
        proizvod_id = int(request.form['proizvod_id'])
        nova_lokacija_id = int(request.form['nova_lokacija_id'])
        kolicina_raw = request.form.get('kolicina', '').strip()

        try:
            kolicina_za_premjestanje = int(kolicina_raw) if kolicina_raw else 0
        except ValueError:
            flash('Greška: Unesena je neispravna količina za premještanje!', 'error')
            return redirect(url_for('premjestanje'))

        if kolicina_za_premjestanje <= 0:
            flash('Greška: Količina za premještanje mora biti veća od 0!', 'error')
            return redirect(url_for('premjestanje'))

        proizvod = db.execute('SELECT * FROM proizvodi WHERE id = ?', (proizvod_id,)).fetchone()
        if not proizvod:
            flash('Odabrani proizvod ne postoji!', 'error')
            return redirect(url_for('premjestanje'))

        if kolicina_za_premjestanje > proizvod['kolicina']:
            flash(f'Greška: Ne možete premjestiti više od dostupnih {proizvod["kolicina"]} komada!', 'error')
            return redirect(url_for('premjestanje'))

        if proizvod['lokacija_id'] == nova_lokacija_id:
            flash('Artikl se već nalazi na odabranoj skladišnoj lokaciji!', 'error')
            return redirect(url_for('premjestanje'))

        moze_stati, slobodno = provjeri_kapacitet_lokacije(db, nova_lokacija_id, kolicina_za_premjestanje)
        if not moze_stati:
            flash(vrati_gramaticku_poruku(slobodno), 'error')
            return redirect(url_for('premjestanje'))

        stara_lok = db.execute('SELECT sektor, regal, polica FROM lokacije WHERE id = ?', (proizvod['lokacija_id'],)).fetchone() if proizvod['lokacija_id'] else None
        stara_tekst = f"{stara_lok['sektor']} ({stara_lok['regal']}-{stara_lok['polica']})" if stara_lok else "Nedodijeljeno"

        nova_lok = db.execute('SELECT sektor, regal, polica FROM lokacije WHERE id = ?', (nova_lokacija_id,)).fetchone()
        nova_tekst = f"{nova_lok['sektor']} ({nova_lok['regal']}-{nova_lok['polica']})"

        postojece_na_destinaciji = db.execute(
            'SELECT * FROM proizvodi WHERE sifra = ? AND lokacija_id = ?',
            (proizvod['sifra'], nova_lokacija_id)
        ).fetchone()

        transakcija_proizvod_id = proizvod_id

        if kolicina_za_premjestanje == proizvod['kolicina']:
            if postojece_na_destinaciji:
                db.execute('UPDATE proizvodi SET kolicina = kolicina + ? WHERE id = ?', (kolicina_za_premjestanje, postojece_na_destinaciji['id']))
                db.execute('UPDATE transakcije SET proizvod_id = ? WHERE proizvod_id = ?', (postojece_na_destinaciji['id'], proizvod_id))
                db.execute('UPDATE narudzbe SET proizvod_id = ? WHERE proizvod_id = ?', (postojece_na_destinaciji['id'], proizvod_id))
                db.execute('DELETE FROM proizvodi WHERE id = ?', (proizvod_id,))
                transakcija_proizvod_id = postojece_na_destinaciji['id']
            else:
                db.execute('UPDATE proizvodi SET lokacija_id = ? WHERE id = ?', (nova_lokacija_id, proizvod_id))
        else:
            db.execute('UPDATE proizvodi SET kolicina = kolicina - ? WHERE id = ?', (kolicina_za_premjestanje, proizvod_id))
            if postojece_na_destinaciji:
                db.execute('UPDATE proizvodi SET kolicina = kolicina + ? WHERE id = ?', (kolicina_za_premjestanje, postojece_na_destinaciji['id']))
            else:
                db.execute('''
                    INSERT INTO proizvodi (naziv, sifra, kolicina, min_kolicina, cijena, kategorija_id, lokacija_id, dobavljac_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (proizvod['naziv'], proizvod['sifra'], kolicina_za_premjestanje, proizvod['min_kolicina'], proizvod['cijena'], proizvod['kategorija_id'], nova_lokacija_id, proizvod['dobavljac_id']))

        napomena_tekst = f"Premješteno {kolicina_za_premjestanje} kom. iz {stara_tekst} u {nova_tekst}"
        db.execute('''
            INSERT INTO transakcije (proizvod_id, korisnik_id, tip, kolicina, datum, napomena, zabiljezeni_naziv, zabiljezena_sifra)
            VALUES (?, ?, 'PREMJEŠTANJE', ?, ?, ?, ?, ?)
        ''', (transakcija_proizvod_id, session['user_id'], kolicina_za_premjestanje, dohvati_trenutno_vrijeme(), napomena_tekst, proizvod['naziv'], proizvod['sifra']))

        db.commit()
        flash(f'Uspješno premješteno {kolicina_za_premjestanje} kom. artikla "{proizvod["naziv"]}" iz {stara_tekst} u {nova_tekst}!', 'success')
        return redirect(url_for('premjestanje'))

    proizvodi = db.execute('''
        SELECT p.*, l.sektor, l.regal, l.polica
        FROM proizvodi p
        LEFT JOIN lokacije l ON p.lokacija_id = l.id
        WHERE p.kolicina > 0
        ORDER BY p.naziv ASC, l.sektor ASC, l.regal ASC, l.polica ASC
    ''').fetchall()

    lokacije_raw = db.execute('SELECT * FROM lokacije ORDER BY sektor ASC, regal ASC, polica ASC').fetchall()
    proizvodi_raw = db.execute('SELECT lokacija_id, kolicina FROM proizvodi').fetchall()
    lokacije_stat = []
    for loc in lokacije_raw:
        zauzeto = sum([p['kolicina'] for p in proizvodi_raw if p['lokacija_id'] == loc['id']])
        slobodno = max(0, loc['kapacitet'] - zauzeto)
        lokacije_stat.append({
            'id': loc['id'],
            'sektor': loc['sektor'],
            'regal': loc['regal'],
            'polica': loc['polica'],
            'kapacitet': loc['kapacitet'],
            'slobodno': slobodno
        })

    return render_template('premjestanje.html', proizvodi=proizvodi, lokacije=lokacije_stat, active_page='premjestanje')

@app.route('/kategorije', methods=['GET', 'POST'])
def upravljanje_kategorijama():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    db = get_db()

    if request.method == 'POST':
        if session['uloga'] == 'skladistar':
            flash('Skladištari nemaju ovlasti za unos kategorija!', 'error')
            return redirect(url_for('upravljanje_kategorijama'))

        naziv = request.form.get('naziv', '').strip()

        if not naziv:
            flash('Greška: Unesite naziv kategorije!', 'error')
            return redirect(url_for('upravljanje_kategorijama'))

        try:
            db.execute('INSERT INTO kategorije (naziv) VALUES (?)', (naziv,))
            db.commit()
            flash(f'Nova kategorija "{naziv}" je uspješno dodana!', 'success')
        except sqlite3.IntegrityError:
            flash('Greška: Kategorija s tim nazivom već postoji!', 'error')

        return redirect(url_for('upravljanje_kategorijama'))

    kategorije = db.execute('''
        SELECT k.*, COUNT(p.id) as broj_artikala
        FROM kategorije k
        LEFT JOIN proizvodi p ON k.id = p.kategorija_id
        GROUP BY k.id
        ORDER BY k.naziv ASC
    ''').fetchall()

    return render_template('kategorije.html', kategorije=kategorije, active_page='kategorije')

@app.route('/kategorija/uredi/<int:id>', methods=['GET', 'POST'])
def uredi_kategoriju(id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    if session['uloga'] == 'skladistar':
        flash('Skladištari nemaju ovlasti za uređivanje kategorija!', 'error')
        return redirect(url_for('upravljanje_kategorijama'))

    db = get_db()
    kategorija = db.execute('SELECT * FROM kategorije WHERE id = ?', (id,)).fetchone()
    if not kategorija:
        flash('Kategorija nije pronađena!', 'error')
        return redirect(url_for('upravljanje_kategorijama'))

    if request.method == 'POST':
        naziv = request.form.get('naziv', '').strip()
        if not naziv:
            flash('Greška: Naziv kategorije ne može biti prazan!', 'error')
            return redirect(url_for('uredi_kategoriju', id=id))

        try:
            db.execute('UPDATE kategorije SET naziv = ? WHERE id = ?', (naziv, id))
            db.commit()
            flash('Kategorija je uspješno ažurirana!', 'success')
            return redirect(url_for('upravljanje_kategorijama'))
        except sqlite3.IntegrityError:
            flash('Greška: Kategorija s tim nazivom već postoji!', 'error')
            return redirect(url_for('uredi_kategoriju', id=id))

    return render_template('uredi_kategoriju.html', kategorija=kategorija, active_page='kategorije')

@app.route('/kategorija/obrisi/<int:id>', methods=['POST'])
def obrisi_kategoriju(id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    if session['uloga'] == 'skladistar':
        flash('Skladištari nemaju ovlasti za brisanje kategorija!', 'error')
        return redirect(url_for('upravljanje_kategorijama'))

    db = get_db()
    db.execute('UPDATE proizvodi SET kategorija_id = NULL WHERE kategorija_id = ?', (id,))
    db.execute('DELETE FROM kategorije WHERE id = ?', (id,))
    db.commit()

    flash('Kategorija je uspješno obrisana!', 'success')
    return redirect(url_for('upravljanje_kategorijama'))

@app.route('/dobavljaci', methods=['GET', 'POST'])
def dobavljaci():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    db = get_db()

    if request.method == 'POST':
        if session['uloga'] == 'skladistar':
            flash('Skladištari nemaju ovlasti za unos dobavljača!', 'error')
            return redirect(url_for('dobavljaci'))

        naziv = request.form.get('naziv', '').strip()
        kontakt_osoba = request.form.get('kontakt_osoba', '').strip()
        email = request.form.get('email', '').strip()
        telefon = request.form.get('telefon', '').strip()

        postojeci_dob = db.execute('SELECT id FROM dobavljaci WHERE LOWER(naziv) = LOWER(?)', (naziv,)).fetchone()
        if postojeci_dob:
            flash('Greška: Dobavljač s tim nazivom već postoji!', 'error')
            return redirect(url_for('dobavljaci'))

        try:
            db.execute('''
                INSERT INTO dobavljaci (naziv, kontakt_osoba, email, telefon)
                VALUES (?, ?, ?, ?)
            ''', (naziv, kontakt_osoba, email, telefon))
            db.commit()
            flash('Novi dobavljač je uspješno registriran!', 'success')
        except sqlite3.IntegrityError:
            flash('Greška: Dobavljač s tim nazivom već postoji!', 'error')

        return redirect(url_for('dobavljaci'))

    lista_dobavljaca = db.execute('SELECT * FROM dobavljaci ORDER BY id ASC').fetchall()
    return render_template('dobavljaci.html', dobavljaci=lista_dobavljaca, active_page='dobavljaci')

@app.route('/dobavljac/uredi/<int:id>', methods=['GET', 'POST'])
def uredi_dobavljaca(id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    if session['uloga'] == 'skladistar':
        flash('Skladištari nemaju ovlasti za uređivanje dobavljača!', 'error')
        return redirect(url_for('dobavljaci'))

    db = get_db()
    dobavljac = db.execute('SELECT * FROM dobavljaci WHERE id = ?', (id,)).fetchone()
    
    if not dobavljac:
        flash('Dobavljač nije pronađen!', 'error')
        return redirect(url_for('dobavljaci'))

    if request.method == 'POST':
        naziv = request.form.get('naziv', '').strip()
        kontakt_osoba = request.form.get('kontakt_osoba', '').strip()
        email = request.form.get('email', '').strip()
        telefon = request.form.get('telefon', '').strip()

        postojeci_dob = db.execute('SELECT id FROM dobavljaci WHERE LOWER(naziv) = LOWER(?) AND id != ?', (naziv, id)).fetchone()
        if postojeci_dob:
            flash('Greška: Dobavljač s tim nazivom već postoji!', 'error')
            return redirect(url_for('uredi_dobavljaca', id=id))

        try:
            db.execute('''
                UPDATE dobavljaci 
                SET naziv = ?, kontakt_osoba = ?, email = ?, telefon = ? 
                WHERE id = ?
            ''', (naziv, kontakt_osoba, email, telefon, id))
            db.commit()
            flash('Podaci o dobavljaču su uspješno ažurirani!', 'success')
            return redirect(url_for('dobavljaci'))
        except sqlite3.IntegrityError:
            flash('Greška: Dobavljač s tim nazivom već postoji!', 'error')
            return redirect(url_for('uredi_dobavljaca', id=id))

    return render_template('uredi_dobavljaca.html', dobavljac=dobavljac, active_page='dobavljaci')

@app.route('/dobavljac/obrisi/<int:id>', methods=['POST'])
def obrisi_dobavljaca(id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    if session['uloga'] == 'skladistar':
        flash('Skladištari nemaju ovlasti za brisanje dobavljača!', 'error')
        return redirect(url_for('dobavljaci'))

    db = get_db()
    db.execute('UPDATE proizvodi SET dobavljac_id = NULL WHERE dobavljac_id = ?', (id,))
    db.execute('UPDATE narudzbe SET dobavljac_id = NULL WHERE dobavljac_id = ?', (id,))
    
    db.execute('DELETE FROM dobavljaci WHERE id = ?', (id,))
    db.commit()
    flash('Dobavljač je uspješno obrisan!', 'success')
    return redirect(url_for('dobavljaci'))

@app.route('/narudzbe', methods=['GET', 'POST'])
def narudzbe():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    db = get_db()

    if request.method == 'POST':
        if session['uloga'] == 'skladistar':
            flash('Skladištari nemaju ovlasti za kreiranje narudžbi!', 'error')
            return redirect(url_for('narudzbe'))

        proizvod_id_raw = request.form.get('proizvod_id')
        dobavljac_id_raw = request.form.get('dobavljac_id')
        kolicina_raw = request.form.get('kolicina', '').strip()

        try:
            kolicina = int(kolicina_raw) if kolicina_raw else 0
        except ValueError:
            flash('Greška: Unesena je neispravna količina!', 'error')
            return redirect(url_for('narudzbe'))

        if kolicina <= 0:
            flash('Greška: Količina narudžbe mora biti veća od 0!', 'error')
            return redirect(url_for('narudzbe'))

        dobavljac_id = None
        if dobavljac_id_raw == 'NOVI':
            novi_dob_naziv = request.form.get('novi_dobavljac_naziv', '').strip()
            if not novi_dob_naziv:
                flash('Greška: Morate unijeti naziv novog dobavljača!', 'error')
                return redirect(url_for('narudzbe'))
            
            postojeci_dob = db.execute('SELECT id FROM dobavljaci WHERE LOWER(naziv) = LOWER(?)', (novi_dob_naziv,)).fetchone()
            if postojeci_dob:
                dobavljac_id = postojeci_dob['id']
            else:
                novi_dob_kontakt = request.form.get('novi_dobavljac_kontakt', '').strip()
                novi_dob_email = request.form.get('novi_dobavljac_email', '').strip()
                novi_dob_telefon = request.form.get('novi_dobavljac_telefon', '').strip()
                
                db.execute('''
                    INSERT INTO dobavljaci (naziv, kontakt_osoba, email, telefon)
                    VALUES (?, ?, ?, ?)
                ''', (novi_dob_naziv, novi_dob_kontakt, novi_dob_email, novi_dob_telefon))
                dobavljac_id = db.execute('SELECT last_insert_rowid()').fetchone()[0]
        elif dobavljac_id_raw:
            dobavljac_id = int(dobavljac_id_raw)

        proizvod_id = None
        z_naziv = ""
        z_sifra = ""

        if proizvod_id_raw == 'NOVI':
            novi_p_naziv = request.form.get('novi_proizvod_naziv', '').strip()
            novi_p_sifra = request.form.get('novi_proizvod_sifra', '').strip()
            novi_p_cijena_raw = request.form.get('novi_proizvod_cijena', '0').strip().replace(',', '.')
            novi_p_kat_id = request.form.get('novi_proizvod_kategorija_id')

            if not novi_p_naziv or not novi_p_sifra or not novi_p_kat_id:
                flash('Greška: Molimo ispunite sve podatke za novi artikl!', 'error')
                return redirect(url_for('narudzbe'))

            sifra_duplikat = db.execute('SELECT id FROM proizvodi WHERE LOWER(sifra) = LOWER(?)', (novi_p_sifra,)).fetchone()
            if sifra_duplikat:
                flash(f'Greška: Artikl sa šifrom "{novi_p_sifra}" već postoji u katalogu!', 'error')
                return redirect(url_for('narudzbe'))

            if dobavljac_id:
                naziv_dob_duplikat = db.execute('SELECT id FROM proizvodi WHERE LOWER(naziv) = LOWER(?) AND dobavljac_id = ?', (novi_p_naziv, dobavljac_id)).fetchone()
                if naziv_dob_duplikat:
                    flash(f'Greška: Artikl s nazivom "{novi_p_naziv}" već postoji kod odabranog dobavljača!', 'error')
                    return redirect(url_for('narudzbe'))

            try:
                novi_p_cijena = float(novi_p_cijena_raw) if novi_p_cijena_raw else 0.0
            except ValueError:
                novi_p_cijena = 0.0

            db.execute('''
                INSERT INTO proizvodi (naziv, sifra, kolicina, min_kolicina, cijena, kategorija_id, lokacija_id, dobavljac_id)
                VALUES (?, ?, 0, 5, ?, ?, NULL, ?)
            ''', (novi_p_naziv, novi_p_sifra, novi_p_cijena, novi_p_kat_id, dobavljac_id))
            proizvod_id = db.execute('SELECT last_insert_rowid()').fetchone()[0]
            z_naziv = novi_p_naziv
            z_sifra = novi_p_sifra
            
            db.execute('''
                INSERT INTO transakcije (proizvod_id, korisnik_id, tip, kolicina, datum, napomena, zabiljezeni_naziv, zabiljezena_sifra)
                VALUES (?, ?, 'ULAZ', 0, ?, 'Početni unos (kroz narudžbu)', ?, ?)
            ''', (proizvod_id, session['user_id'], dohvati_trenutno_vrijeme(), z_naziv, z_sifra))
            
        elif proizvod_id_raw:
            proizvod_id = int(proizvod_id_raw)
            p = db.execute('SELECT naziv, sifra, dobavljac_id FROM proizvodi WHERE id = ?', (proizvod_id,)).fetchone()
            if p:
                if not dobavljac_id:
                    dobavljac_id = p['dobavljac_id']
                z_naziv = p['naziv']
                z_sifra = p['sifra']

        if not proizvod_id:
            flash('Greška: Niste odabrali artikl za narudžbu!', 'error')
            return redirect(url_for('narudzbe'))

        db.execute('''
            INSERT INTO narudzbe (proizvod_id, dobavljac_id, kolicina, status, datum, zabiljezeni_naziv, zabiljezena_sifra)
            VALUES (?, ?, ?, 'Na čekanju', ?, ?, ?)
        ''', (proizvod_id, dobavljac_id, kolicina, dohvati_trenutno_vrijeme(), z_naziv, z_sifra))
        
        db.commit()

        flash('Narudžbenica je uspješno kreirana (status: Na čekanju)!', 'success')
        return redirect(url_for('narudzbe'))

    lista_narudzbi = db.execute('''
        SELECT n.*, 
               COALESCE(n.zabiljezeni_naziv, p.naziv) as proizvod_naziv, 
               COALESCE(n.zabiljezena_sifra, p.sifra) as proizvod_sifra, 
               d.naziv as dobavljac_naziv,
               l.sektor, l.regal, l.polica
        FROM narudzbe n
        LEFT JOIN proizvodi p ON n.proizvod_id = p.id
        LEFT JOIN dobavljaci d ON n.dobavljac_id = d.id
        LEFT JOIN lokacije l ON p.lokacija_id = l.id
        ORDER BY n.datum DESC
    ''').fetchall()

    proizvodi = db.execute('SELECT id, naziv, sifra, dobavljac_id FROM proizvodi GROUP BY sifra ORDER BY naziv ASC').fetchall()
    dobavljaci = db.execute('SELECT id, naziv FROM dobavljaci ORDER BY id ASC').fetchall()
    kategorije = db.execute('SELECT id, naziv FROM kategorije ORDER BY naziv ASC').fetchall()

    lokacije_raw = db.execute('SELECT * FROM lokacije ORDER BY sektor ASC, regal ASC, polica ASC').fetchall()
    proizvodi_raw = db.execute('SELECT lokacija_id, kolicina FROM proizvodi').fetchall()
    lokacije_stat = []
    for loc in lokacije_raw:
        zauzeto = sum([p['kolicina'] for p in proizvodi_raw if p['lokacija_id'] == loc['id']])
        slobodno = max(0, loc['kapacitet'] - zauzeto)
        lokacije_stat.append({
            'id': loc['id'],
            'sektor': loc['sektor'],
            'regal': loc['regal'],
            'polica': loc['polica'],
            'kapacitet': loc['kapacitet'],
            'slobodno': slobodno
        })

    return render_template('narudzbe.html', narudzbe=lista_narudzbi, proizvodi=proizvodi, dobavljaci=dobavljaci, kategorije=kategorije, lokacije=lokacije_stat, active_page='narudzbe')

@app.route('/narudzbe/export_csv')
def export_narudzbe_csv():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    db = get_db()
    narudzbe = db.execute('''
        SELECT n.*, 
               COALESCE(n.zabiljezeni_naziv, p.naziv) as proizvod_naziv, 
               COALESCE(n.zabiljezena_sifra, p.sifra) as proizvod_sifra, 
               d.naziv as dobavljac_naziv
        FROM narudzbe n
        LEFT JOIN proizvodi p ON n.proizvod_id = p.id
        LEFT JOIN dobavljaci d ON n.dobavljac_id = d.id
        ORDER BY n.datum DESC
    ''').fetchall()
    
    si = io.StringIO()
    cw = csv.writer(si, delimiter=';')
    cw.writerow(['ID Narudzbe', 'Datum', 'Artikl', 'Sifra', 'Dobavljac', 'Kolicina (kom)', 'Status'])
    
    for n in narudzbe:
        cw.writerow([
            n['id'], 
            n['datum'], 
            n['proizvod_naziv'] or 'Nepoznato / Obrisano', 
            n['proizvod_sifra'] or '-', 
            n['dobavljac_naziv'] or '-', 
            n['kolicina'], 
            n['status']
        ])
        
    output = make_response(si.getvalue().encode('utf-8-sig'))
    output.headers["Content-Disposition"] = "attachment; filename=lista_narudzbi.csv"
    output.headers["Content-type"] = "text/csv; charset=utf-8"
    return output

@app.route('/narudzbe/generiraj_automatski', methods=['POST'])
def generiraj_narudzbe():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    if session['uloga'] == 'skladistar':
        flash('Skladištari nemaju ovlasti za generiranje narudžbi!', 'error')
        return redirect(url_for('narudzbe'))

    db = get_db()
    
    kriticni = db.execute('''
        SELECT p.id, p.naziv, p.sifra, SUM(p.kolicina) as ukupna_kolicina, p.min_kolicina, p.dobavljac_id
        FROM proizvodi p
        GROUP BY p.sifra
        HAVING ukupna_kolicina <= p.min_kolicina
    ''').fetchall()

    generirano_broj = 0
    for p in kriticni:
        otvoreno = db.execute('SELECT id FROM narudzbe WHERE proizvod_id = ? AND status = "Na čekanju"', (p['id'],)).fetchone()
        if not otvoreno and p['dobavljac_id']:
            prijedlog_kolicine = max(10, (p['min_kolicina'] * 2) - p['ukupna_kolicina'])
            db.execute('''
                INSERT INTO narudzbe (proizvod_id, dobavljac_id, kolicina, status, datum, zabiljezeni_naziv, zabiljezena_sifra)
                VALUES (?, ?, ?, 'Na čekanju', ?, ?, ?)
            ''', (p['id'], p['dobavljac_id'], prijedlog_kolicine, dohvati_trenutno_vrijeme(), p['naziv'], p['sifra']))
            generirano_broj += 1

    db.commit()
    if generirano_broj > 0:
        flash(f'Automatski je stvoreno {generirano_broj} novih prijedloga narudžbenica (status: Na čekanju)!', 'success')
    else:
        flash('Nema novih kritičnih artikala za koje je potrebno kreirati narudžbe.', 'info')

    return redirect(url_for('narudzbe'))

@app.route('/narudzba/promijeni_status/<int:id>/<string:novi_status>', methods=['POST'])
def promijeni_status_narudzbe(id, novi_status):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    if session['uloga'] == 'skladistar':
        flash('Skladištari nemaju ovlasti za promjenu statusa narudžbi!', 'error')
        return redirect(url_for('narudzbe'))

    db = get_db()
    narudzba = db.execute('''
        SELECT n.*, 
               COALESCE(n.zabiljezeni_naziv, p.naziv) as proizvod_naziv, 
               COALESCE(n.zabiljezena_sifra, p.sifra) as proizvod_sifra,
               p.lokacija_id as trenutna_lokacija_id, p.kolicina as trenutna_kolicina
        FROM narudzbe n
        LEFT JOIN proizvodi p ON n.proizvod_id = p.id
        WHERE n.id = ?
    ''', (id,)).fetchone()

    if not narudzba:
        flash('Narudžba nije pronađena!', 'error')
        return redirect(url_for('narudzbe'))

    poruka_lokacije = ""

    if novi_status == 'Zaprimljeno' and narudzba['status'] != 'Zaprimljeno':
        lokacija_id_raw = request.form.get('lokacija_id')
        if not lokacija_id_raw:
            flash('Greška: Morate odabrati skladišnu lokaciju na koju zaprimate robu!', 'error')
            return redirect(url_for('narudzbe'))

        lokacija_id = int(lokacija_id_raw)
        kolicina_za_zaprimanje = narudzba['kolicina']
        
        moze_stati, slobodno = provjeri_kapacitet_lokacije(db, lokacija_id, kolicina_za_zaprimanje)
        if not moze_stati:
            flash(vrati_gramaticku_poruku(slobodno), 'error')
            return redirect(url_for('narudzbe'))

        lok = db.execute('SELECT sektor, regal, polica FROM lokacije WHERE id = ?', (lokacija_id,)).fetchone()
        poruka_lokacije = f" [Smješteno na: {lok['sektor']} {lok['regal']}-{lok['polica']}]"

        p = db.execute('SELECT * FROM proizvodi WHERE id = ?', (narudzba['proizvod_id'],)).fetchone()
        postojece_na_novoj = db.execute('SELECT * FROM proizvodi WHERE sifra = ? AND lokacija_id = ?', (p['sifra'], lokacija_id)).fetchone()

        dest_id = p['id']

        if postojece_na_novoj:
            db.execute('UPDATE proizvodi SET kolicina = kolicina + ? WHERE id = ?', (kolicina_za_zaprimanje, postojece_na_novoj['id']))
            dest_id = postojece_na_novoj['id']
        elif not p['lokacija_id']:
            db.execute('UPDATE proizvodi SET kolicina = kolicina + ?, lokacija_id = ? WHERE id = ?', (kolicina_za_zaprimanje, lokacija_id, p['id']))
        else:
            db.execute('''
                INSERT INTO proizvodi (naziv, sifra, kolicina, min_kolicina, cijena, kategorija_id, lokacija_id, dobavljac_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (p['naziv'], p['sifra'], kolicina_za_zaprimanje, p['min_kolicina'], p['cijena'], p['kategorija_id'], lokacija_id, p['dobavljac_id']))
            dest_id = db.execute('SELECT last_insert_rowid()').fetchone()[0]

        db.execute('UPDATE narudzbe SET proizvod_id = ? WHERE id = ?', (dest_id, id))

        db.execute('''
            INSERT INTO transakcije (proizvod_id, korisnik_id, tip, kolicina, datum, napomena, zabiljezeni_naziv, zabiljezena_sifra)
            VALUES (?, ?, 'ULAZ', ?, ?, ?, ?, ?)
        ''', (dest_id, session['user_id'], kolicina_za_zaprimanje, dohvati_trenutno_vrijeme(), f"Zaprimljeno iz narudžbe #{id}{poruka_lokacije}", narudzba['proizvod_naziv'], narudzba['proizvod_sifra']))

    db.execute('UPDATE narudzbe SET status = ? WHERE id = ?', (novi_status, id))
    db.commit()

    if novi_status == 'Zaprimljeno':
        flash(f'Narudžba #{id} je uspješno zaprimljena (+{narudzba["kolicina"]} kom)!{poruka_lokacije}', 'success')
    else:
        flash(f'Status narudžbe je promijenjen u "{novi_status}".', 'success')

    return redirect(url_for('narudzbe'))

@app.route('/narudzba/obrisi/<int:id>', methods=['POST'])
def obrisi_narudzbu(id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    if session['uloga'] == 'skladistar':
        flash('Skladištari nemaju ovlasti za brisanje narudžbi!', 'error')
        return redirect(url_for('narudzbe'))

    db = get_db()
    db.execute('DELETE FROM narudzbe WHERE id = ?', (id,))
    db.commit()
    flash('Narudžba je obrisana!', 'success')
    return redirect(url_for('narudzbe'))

@app.route('/narudzba/pdf/<int:id>')
def preuzmi_narudzbu_pdf(id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    db = get_db()
    narudzba = db.execute('''
        SELECT n.*, 
               COALESCE(n.zabiljezeni_naziv, p.naziv) as proizvod_naziv, 
               COALESCE(n.zabiljezena_sifra, p.sifra) as proizvod_sifra, 
               p.cijena,
               d.naziv as dobavljac_naziv, d.kontakt_osoba, d.email, d.telefon
        FROM narudzbe n
        LEFT JOIN proizvodi p ON n.proizvod_id = p.id
        LEFT JOIN dobavljaci d ON n.dobavljac_id = d.id
        WHERE n.id = ?
    ''', (id,)).fetchone()

    if not narudzba:
        flash('Narudžba nije pronađena!', 'error')
        return redirect(url_for('narudzbe'))

    pdf = FPDF()
    pdf.add_page()
    
    pdf.set_font("Helvetica", 'B', 16)
    pdf.cell(0, 10, očisti_tekst_za_pdf("Mladinović d.o.o."), ln=True, align='C')
    pdf.set_font("Helvetica", size=10)
    pdf.cell(0, 5, očisti_tekst_za_pdf("Skladište računalne opreme"), ln=True, align='C')
    pdf.cell(0, 5, očisti_tekst_za_pdf(f"SLUŽBENA NARUDŽBENICA br. NAR-00{narudzba['id']}"), ln=True, align='C')
    pdf.ln(10)

    pdf.set_font("Helvetica", 'B', 11)
    pdf.cell(0, 7, očisti_tekst_za_pdf("PODACI O DOBAVLJAČU:"), ln=True)
    pdf.set_font("Helvetica", size=10)
    pdf.cell(0, 5, očisti_tekst_za_pdf(f"Tvrtka: {narudzba['dobavljac_naziv'] or 'Nije definirano'}"), ln=True)
    pdf.cell(0, 5, očisti_tekst_za_pdf(f"Kontakt osoba: {narudzba['kontakt_osoba'] or '-'}"), ln=True)
    pdf.cell(0, 5, očisti_tekst_za_pdf(f"E-mail: {narudzba['email'] or '-'}"), ln=True)
    pdf.cell(0, 5, očisti_tekst_za_pdf(f"Telefon: {narudzba['telefon'] or '-'}"), ln=True)
    pdf.ln(8)

    pdf.set_font("Helvetica", 'B', 10)
    pdf.cell(75, 8, očisti_tekst_za_pdf("Naziv Artikla"), border=1)
    pdf.cell(35, 8, očisti_tekst_za_pdf("Šifra"), border=1)
    pdf.cell(25, 8, očisti_tekst_za_pdf("Količina"), border=1, align='C')
    pdf.cell(25, 8, očisti_tekst_za_pdf("Cijena"), border=1, align='R')
    pdf.cell(30, 8, očisti_tekst_za_pdf("Ukupno"), border=1, align='R', ln=True)

    pdf.set_font("Helvetica", size=10)
    pdf.cell(75, 8, očisti_tekst_za_pdf(str(narudzba['proizvod_naziv'])) or "-", border=1)
    pdf.cell(35, 8, očisti_tekst_za_pdf(str(narudzba['proizvod_sifra'])) or "-", border=1)
    pdf.cell(25, 8, f"{narudzba['kolicina']} kom", border=1, align='C')
    
    cijena_kom = narudzba['cijena'] or 0.0
    ukupno_eur = cijena_kom * narudzba['kolicina']
    
    pdf.cell(25, 8, f"{formatiraj_cijenu(cijena_kom)} EUR", border=1, align='R')
    pdf.cell(30, 8, f"{formatiraj_cijenu(ukupno_eur)} EUR", border=1, align='R', ln=True)

    pdf.ln(12)
    pdf.set_font("Helvetica", size=9)
    pdf.cell(0, 5, očisti_tekst_za_pdf(f"Datum izdavanja narudžbenice: {narudzba['datum']}"), ln=True)
    pdf.cell(0, 5, očisti_tekst_za_pdf(f"Trenutni status: {narudzba['status']}"), ln=True)

    pdf.ln(25)
    pdf.cell(90, 5, očisti_tekst_za_pdf("Naručio (Mladinović d.o.o.):"), ln=False)
    pdf.cell(90, 5, očisti_tekst_za_pdf("Potvrda dobavljača:"), ln=True)
    pdf.cell(90, 5, "_________________________________", ln=False)
    pdf.cell(90, 5, "_________________________________", ln=True)

    out = pdf.output(dest='S')
    if isinstance(out, str):
        pdf_bytes = out.encode('latin1')
    else:
        pdf_bytes = bytes(out)

    response = make_response(pdf_bytes)
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'attachment; filename=Narudzbenica_NAR_{narudzba["id"]}.pdf'
    return response

@app.route('/izvjestaji')
def izvjestaji():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    db = get_db()
    ukupno_artikala = db.execute('SELECT SUM(kolicina) as ukupno FROM proizvodi').fetchone()['ukupno'] or 0
    ukupna_vrijednost = db.execute('SELECT SUM(kolicina * cijena) as ukupno FROM proizvodi').fetchone()['ukupno'] or 0.0
    broj_kriticnih = db.execute('''
        SELECT COUNT(*) as ukupno FROM (
            SELECT SUM(kolicina) as ukupno_zal
            FROM proizvodi
            GROUP BY sifra
            HAVING ukupno_zal <= min_kolicina
        )
    ''').fetchone()['ukupno'] or 0

    po_kategorijama = db.execute('''
        SELECT k.naziv, SUM(p.kolicina) as kolicina, SUM(p.kolicina * p.cijena) as vrijednost
        FROM proizvodi p
        JOIN kategorije k ON p.kategorija_id = k.id
        GROUP BY k.id
    ''').fetchall()

    return render_template(
        'izvjestaji.html',
        ukupno_artikala=ukupno_artikala,
        ukupna_vrijednost=ukupna_vrijednost,
        broj_kriticnih=broj_kriticnih,
        po_kategorijama=po_kategorijama,
        active_page='izvjestaji'
    )

@app.route('/izvjestaji/export_csv')
def export_izvjestaji_csv():
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    db = get_db()
    po_kategorijama = db.execute('''
        SELECT k.naziv, SUM(p.kolicina) as kolicina, SUM(p.kolicina * p.cijena) as vrijednost
        FROM proizvodi p
        JOIN kategorije k ON p.kategorija_id = k.id
        GROUP BY k.id
    ''').fetchall()
    
    si = io.StringIO()
    cw = csv.writer(si, delimiter=';')
    cw.writerow(['Kategorija opreme', 'Ukupno komada na skladistu', 'Financijska vrijednost (EUR)'])
    
    for red in po_kategorijama:
        vrijednost_str = formatiraj_cijenu(red['vrijednost'])
        cw.writerow([red['naziv'], red['kolicina'], vrijednost_str])
        
    output = make_response(si.getvalue().encode('utf-8-sig'))
    output.headers["Content-Disposition"] = "attachment; filename=izvjestaj_zaliha.csv"
    output.headers["Content-type"] = "text/csv; charset=utf-8"
    return output

@app.route('/lokacije', methods=['GET', 'POST'])
def upravljanje_lokacijama():
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    db = get_db()
    
    if request.method == 'POST':
        if session['uloga'] == 'skladistar':
            flash('Skladištari nemaju ovlasti za dodavanje novih sektora!', 'error')
            return redirect(url_for('upravljanje_lokacijama'))
            
        sektor = request.form['sektor'].strip()
        regal = request.form['regal'].strip()
        polica = request.form['polica'].strip()
        
        postojeca_lok = db.execute('''
            SELECT id FROM lokacije 
            WHERE LOWER(sektor) = LOWER(?) AND LOWER(regal) = LOWER(?) AND LOWER(polica) = LOWER(?)
        ''', (sektor, regal, polica)).fetchone()
        
        if postojeca_lok:
            flash(f'Greška: Pozicija {sektor} ({regal}-{polica}) već postoji u skladištu!', 'error')
            return redirect(url_for('upravljanje_lokacijama'))
            
        try:
            kapacitet = int(request.form['kapacitet'])
        except ValueError:
            flash('Greška: Kapacitet mora biti broj!', 'error')
            return redirect(url_for('upravljanje_lokacijama'))
        
        db.execute('''
            INSERT INTO lokacije (sektor, regal, polica, kapacitet)
            VALUES (?, ?, ?, ?)
        ''', (sektor, regal, polica, kapacitet))
        db.commit()
        flash('Nova skladišna pozicija je dodana!', 'success')
        return redirect(url_for('upravljanje_lokacijama'))
        
    lokacije = db.execute('''
        SELECT l.*, COALESCE(SUM(p.kolicina), 0) as zauzeto
        FROM lokacije l
        LEFT JOIN proizvodi p ON l.id = p.lokacija_id
        GROUP BY l.id
        ORDER BY l.sektor ASC, l.regal ASC, l.polica ASC
    ''').fetchall()
    
    return render_template('lokacije.html', lokacije=lokacije, active_page='lokacije')

@app.route('/lokacija/uredi/<int:id>', methods=['GET', 'POST'])
def uredi_lokaciju(id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    if session['uloga'] == 'skladistar':
        flash('Skladištari nemaju ovlasti za uređivanje lokacija!', 'error')
        return redirect(url_for('upravljanje_lokacijama'))

    db = get_db()
    lokacija = db.execute('SELECT * FROM lokacije WHERE id = ?', (id,)).fetchone()
    if not lokacija:
        flash('Lokacija nije pronađena!', 'error')
        return redirect(url_for('upravljanje_lokacijama'))

    zauzeto = db.execute('SELECT SUM(kolicina) as ukupno FROM proizvodi WHERE lokacija_id = ?', (id,)).fetchone()['ukupno'] or 0

    if request.method == 'POST':
        sektor = request.form['sektor'].strip()
        regal = request.form['regal'].strip()
        polica = request.form['polica'].strip()
        
        postojeca_lok = db.execute('''
            SELECT id FROM lokacije 
            WHERE LOWER(sektor) = LOWER(?) AND LOWER(regal) = LOWER(?) AND LOWER(polica) = LOWER(?) AND id != ?
        ''', (sektor, regal, polica, id)).fetchone()
        
        if postojeca_lok:
            flash(f'Greška: Pozicija {sektor} ({regal}-{polica}) već postoji u skladištu!', 'error')
            return redirect(url_for('uredi_lokaciju', id=id))

        try:
            kapacitet = int(request.form['kapacitet'])
        except ValueError:
            flash('Greška: Kapacitet mora biti broj!', 'error')
            return redirect(url_for('uredi_lokaciju', id=id))

        if kapacitet < zauzeto:
            flash(f'Greška: Ne možete smanjiti kapacitet na {kapacitet} jer je na polici već smješteno {zauzeto} komada opreme!', 'error')
            return redirect(url_for('uredi_lokaciju', id=id))

        db.execute('''
            UPDATE lokacije 
            SET sektor = ?, regal = ?, polica = ?, kapacitet = ? 
            WHERE id = ?
        ''', (sektor, regal, polica, kapacitet, id))
        db.commit()
        flash('Skladišna pozicija je uspješno ažurirana!', 'success')
        return redirect(url_for('upravljanje_lokacijama'))

    return render_template('uredi_lokaciju.html', lokacija=lokacija, zauzeto=zauzeto, active_page='lokacije')

@app.route('/lokacija/obrisi/<int:id>', methods=['POST'])
def obrisi_lokaciju(id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    if session['uloga'] == 'skladistar':
        flash('Skladištari nemaju ovlasti za brisanje lokacija!', 'error')
        return redirect(url_for('upravljanje_lokacijama'))

    db = get_db()
    zauzeto = db.execute('SELECT SUM(kolicina) as ukupno FROM proizvodi WHERE lokacija_id = ?', (id,)).fetchone()['ukupno'] or 0
    if zauzeto > 0:
        flash('Greška: Ne možete obrisati policu na kojoj se trenutno nalazi oprema! Prvo premjestite robu.', 'error')
        return redirect(url_for('upravljanje_lokacijama'))

    db.execute('DELETE FROM lokacije WHERE id = ?', (id,))
    db.commit()
    flash('Skladišna lokacija je uspješno obrisana!', 'success')
    return redirect(url_for('upravljanje_lokacijama'))

@app.route('/transakcije')
def transakcije():
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    db = get_db()
    lista_transakcija = db.execute('''
        SELECT t.*, 
               COALESCE(t.zabiljezeni_naziv, p.naziv) as proizvod_naziv, 
               COALESCE(t.zabiljezena_sifra, p.sifra) as proizvod_sifra, 
               k.ime, k.prezime
        FROM transakcije t
        LEFT JOIN proizvodi p ON t.proizvod_id = p.id
        LEFT JOIN korisnici k ON t.korisnik_id = k.id
        ORDER BY t.datum DESC
    ''').fetchall()
    
    return render_template('transakcije.html', transakcije=lista_transakcija, active_page='transakcije')

@app.route('/transakcije/export_csv')
def export_transakcije_csv():
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    db = get_db()
    transakcije = db.execute('''
        SELECT t.*, 
               COALESCE(t.zabiljezeni_naziv, p.naziv) as proizvod_naziv, 
               COALESCE(t.zabiljezena_sifra, p.sifra) as proizvod_sifra, 
               k.ime, k.prezime
        FROM transakcije t
        LEFT JOIN proizvodi p ON t.proizvod_id = p.id
        LEFT JOIN korisnici k ON t.korisnik_id = k.id
        ORDER BY t.datum DESC
    ''').fetchall()
    
    si = io.StringIO()
    cw = csv.writer(si, delimiter=';')
    cw.writerow(['Datum i vrijeme', 'Tip', 'Naziv artikla', 'Sifra', 'Kolicina', 'Korisnik (Djelatnik)', 'Napomena'])
    
    for t in transakcije:
        cw.writerow([
            t['datum'], 
            t['tip'], 
            t['proizvod_naziv'] or 'Nepoznato / Obrisano', 
            t['proizvod_sifra'] or '-', 
            t['kolicina'], 
            f"{t['ime']} {t['prezime']}", 
            t['napomena'] or ''
        ])
        
    output = make_response(si.getvalue().encode('utf-8-sig'))
    output.headers["Content-Disposition"] = "attachment; filename=dnevnik_promjena.csv"
    output.headers["Content-type"] = "text/csv; charset=utf-8"
    return output

@app.route('/korisnici', methods=['GET', 'POST'])
def upravljanje_korisnicima():
    if 'user_id' not in session or session['uloga'] != 'admin':
        flash('Pristup odbijen: Samo Administrator može upravljati korisnicima!', 'error')
        return redirect(url_for('index'))
        
    db = get_db()
    
    if request.method == 'POST':
        korisnicko_ime = request.form['korisnicko_ime']
        lozinka = request.form['lozinka']
        ime = request.form['ime']
        prezime = request.form['prezime']
        uloga = request.form['uloga']
        
        hashed = generate_password_hash(lozinka)
        
        try:
            db.execute('''
                INSERT INTO korisnici (korisnicko_ime, lozinka, ime, prezime, uloga)
                VALUES (?, ?, ?, ?, ?)
            ''', (korisnicko_ime, hashed, ime, prezime, uloga))
            db.commit()
            flash('Novi zaposlenik je uspješno registriran!', 'success')
        except sqlite3.IntegrityError:
            flash('Greška: Korisničko ime već postoji!', 'error')
            
        return redirect(url_for('upravljanje_korisnicima'))
        
    korisnici = db.execute('SELECT id, korisnicko_ime, ime, prezime, uloga FROM korisnici').fetchall()
    return render_template('korisnici.html', korisnici=korisnici, active_page='korisnici')

@app.route('/korisnik/uredi/<int:id>', methods=['GET', 'POST'])
def uredi_korisnika(id):
    if 'user_id' not in session or session['uloga'] != 'admin':
        flash('Pristup odbijen: Samo Administrator može upravljati korisnicima!', 'error')
        return redirect(url_for('index'))

    db = get_db()
    korisnik = db.execute('SELECT * FROM korisnici WHERE id = ?', (id,)).fetchone()
    
    if not korisnik:
        flash('Korisnik nije pronađen!', 'error')
        return redirect(url_for('upravljanje_korisnicima'))

    if request.method == 'POST':
        korisnicko_ime = request.form['korisnicko_ime'].strip()
        ime = request.form['ime'].strip()
        prezime = request.form['prezime'].strip()
        uloga = request.form['uloga']
        nova_lozinka = request.form.get('lozinka', '').strip()

        try:
            if nova_lozinka:
                hashed = generate_password_hash(nova_lozinka)
                db.execute('''
                    UPDATE korisnici 
                    SET korisnicko_ime = ?, lozinka = ?, ime = ?, prezime = ?, uloga = ?
                    WHERE id = ?
                ''', (korisnicko_ime, hashed, ime, prezime, uloga, id))
            else:
                db.execute('''
                    UPDATE korisnici 
                    SET korisnicko_ime = ?, ime = ?, prezime = ?, uloga = ?
                    WHERE id = ?
                ''', (korisnicko_ime, ime, prezime, uloga, id))
            db.commit()
            flash('Podaci o korisniku su uspješno ažurirani!', 'success')
            
            if id == session['user_id']:
                session['korisnicko_ime'] = korisnicko_ime
                session['ime'] = ime
                session['prezime'] = prezime
                session['uloga'] = uloga
                
            return redirect(url_for('upravljanje_korisnicima'))
        except sqlite3.IntegrityError:
            flash('Greška: Korisničko ime već postoji!', 'error')
            return redirect(url_for('uredi_korisnika', id=id))

    return render_template('uredi_korisnika.html', korisnik=korisnik, active_page='korisnici')

@app.route('/korisnik/obrisi/<int:id>', methods=['POST'])
def obrisi_korisnika(id):
    if 'user_id' not in session or session['uloga'] != 'admin':
        flash('Nedovoljno ovlasti!', 'error')
        return redirect(url_for('index'))
        
    if id == session['user_id']:
        flash('Ne možete obrisati vlastiti račun!', 'error')
        return redirect(url_for('upravljanje_korisnicima'))
        
    db = get_db()
    db.execute('DELETE FROM korisnici WHERE id = ?', (id,))
    db.commit()
    flash('Korisnički račun je obrisan!', 'success')
    return redirect(url_for('upravljanje_korisnicima'))

if __name__ == '__main__':
    init_db()
    nadogradi_bazu_za_povijest()
    app.run(debug=True, threaded=False, port=5000)