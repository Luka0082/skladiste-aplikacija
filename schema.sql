-- Tablica korisnika
CREATE TABLE IF NOT EXISTS korisnici (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    korisnicko_ime TEXT NOT NULL UNIQUE,
    lozinka TEXT NOT NULL,
    ime TEXT NOT NULL,
    prezime TEXT NOT NULL,
    uloga TEXT NOT NULL CHECK(uloga IN ('admin', 'poslovoda', 'skladistar')) DEFAULT 'skladistar'
);

-- Tablica lokacija
CREATE TABLE IF NOT EXISTS lokacije (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sektor TEXT NOT NULL,
    regal TEXT NOT NULL,
    polica TEXT NOT NULL,
    kapacitet INTEGER NOT NULL DEFAULT 10
);

-- Tablica kategorija
CREATE TABLE IF NOT EXISTS kategorije (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    naziv TEXT NOT NULL UNIQUE
);

-- Tablica dobavljača
CREATE TABLE IF NOT EXISTS dobavljaci (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    naziv TEXT NOT NULL UNIQUE,
    kontakt_osoba TEXT,
    email TEXT,
    telefon TEXT
);

-- Tablica proizvoda
CREATE TABLE IF NOT EXISTS proizvodi (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    naziv TEXT NOT NULL,
    sifra TEXT NOT NULL,
    kolicina INTEGER NOT NULL DEFAULT 0,
    min_kolicina INTEGER DEFAULT 5,
    cijena REAL NOT NULL,
    kategorija_id INTEGER,
    lokacija_id INTEGER,
    dobavljac_id INTEGER,
    FOREIGN KEY (kategorija_id) REFERENCES kategorije (id),
    FOREIGN KEY (lokacija_id) REFERENCES lokacije (id) ON DELETE SET NULL,
    FOREIGN KEY (dobavljac_id) REFERENCES dobavljaci (id) ON DELETE SET NULL
);

-- Tablica transakcija (Dnevnik)
CREATE TABLE IF NOT EXISTS transakcije (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    proizvod_id INTEGER,
    korisnik_id INTEGER,
    tip TEXT CHECK(tip IN ('ULAZ', 'IZLAZ', 'PREMJEŠTANJE')),
    kolicina INTEGER NOT NULL,
    datum DATETIME DEFAULT (datetime('now', 'localtime')),
    napomena TEXT,
    FOREIGN KEY (proizvod_id) REFERENCES proizvodi (id) ON DELETE CASCADE,
    FOREIGN KEY (korisnik_id) REFERENCES korisnici (id)
);

-- Tablica narudžbi
CREATE TABLE IF NOT EXISTS narudzbe (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    proizvod_id INTEGER,
    dobavljac_id INTEGER,
    kolicina INTEGER NOT NULL,
    status TEXT CHECK(status IN ('Na čekanju', 'Naručeno', 'Zaprimljeno')) DEFAULT 'Na čekanju',
    datum DATETIME DEFAULT (datetime('now', 'localtime')),
    FOREIGN KEY (proizvod_id) REFERENCES proizvodi (id) ON DELETE CASCADE,
    FOREIGN KEY (dobavljac_id) REFERENCES dobavljaci (id) ON DELETE CASCADE
);