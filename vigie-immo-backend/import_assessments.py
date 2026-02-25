#!/usr/bin/env python3
"""
Import des données d'évaluation foncière du Québec dans PostGIS.

Sources :
- CSV géoréférencé : coordonnées (lon/lat WGS84) + matricule
- ZIP XML : valeurs foncières, adresses, caractéristiques

Usage :
    python import_assessments.py [--dsn DSN] [--skip-download] [--csv-only]
"""

import argparse
import csv
import io
import logging
import os
import sys
import time
import urllib.request
import xml.etree.ElementTree as ET
import zipfile

import psycopg2
import psycopg2.extras

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

CSV_URL = "https://donneesouvertes.affmunqc.net/role/role_unite_p_2025.csv"
XML_URL = "https://donneesouvertes.affmunqc.net/role/Roles_Donnees_Ouvertes_2025.zip"
DOWNLOAD_DIR = "/tmp/vigie_immo_import"
CSV_PATH = os.path.join(DOWNLOAD_DIR, "role_unite_p_2025.csv")
ZIP_PATH = os.path.join(DOWNLOAD_DIR, "Roles_Donnees_Ouvertes_2025.zip")
BATCH_SIZE = 5000
DEFAULT_DSN = "dbname=vigie_immo"


def download_file(url: str, dest: str) -> None:
    """Download a file with progress logging."""
    if os.path.exists(dest):
        size_mb = os.path.getsize(dest) / (1024 * 1024)
        logger.info(f"Fichier existant : {dest} ({size_mb:.1f} MB), skip download")
        return
    logger.info(f"Téléchargement de {url} ...")
    tmp = dest + ".part"
    req = urllib.request.Request(url, headers={"User-Agent": "VigiImmo/1.0"})
    with urllib.request.urlopen(req, timeout=600) as resp, open(tmp, "wb") as f:
        total = int(resp.headers.get("Content-Length", 0))
        downloaded = 0
        while True:
            chunk = resp.read(1024 * 1024)
            if not chunk:
                break
            f.write(chunk)
            downloaded += len(chunk)
            if total:
                pct = downloaded * 100 / total
                print(f"\r  {downloaded / (1024*1024):.1f} / {total / (1024*1024):.1f} MB ({pct:.0f}%)", end="", flush=True)
    print()
    os.rename(tmp, dest)
    logger.info(f"Téléchargement terminé : {dest}")


def parse_csv_coordinates(csv_path: str) -> dict:
    """
    Parse le CSV pour extraire les coordonnées par matricule.
    Retourne {matricule: (longitude, latitude)}.
    Les coordonnées sont en WGS84 (EPSG:4326).
    """
    logger.info("Parsing du CSV des coordonnées ...")
    coords = {}
    with open(csv_path, "r", encoding="utf-8") as f:
        f.readline()  # skip header
        reader = csv.reader(f)
        for row in reader:
            if len(row) < 8:
                continue
            mat18 = row[5]
            try:
                # Coordonnées en format français (virgule = séparateur décimal)
                lon = float(row[6].replace(",", "."))
                lat = float(row[7].replace(",", "."))
            except (ValueError, IndexError):
                continue
            if -85 < lon < -50 and 40 < lat < 65:
                coords[mat18] = (lon, lat)
    logger.info(f"  {len(coords)} coordonnées chargées")
    return coords


def _text(elem, tag):
    """Extract text from a child element, or empty string."""
    child = elem.find(tag)
    return child.text.strip() if child is not None and child.text else ""


def _int_or_none(val):
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return None


def _float_or_none(val):
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def parse_xml_and_insert(zip_path: str, coords: dict, dsn: str) -> int:
    """
    Parse les fichiers XML du ZIP et insère les données dans PostGIS.
    Joint avec les coordonnées du CSV par matricule.
    Retourne le nombre total de lignes insérées.
    """
    conn = psycopg2.connect(dsn)
    conn.autocommit = False
    cur = conn.cursor()

    # Vider la table avant import
    cur.execute("TRUNCATE TABLE property_assessments RESTART IDENTITY;")
    conn.commit()

    total_inserted = 0
    batch = []

    insert_sql = """
        INSERT INTO property_assessments
            (matricule, civic_number, street_name, municipality, land_value,
             building_value, total_value, year_built, lot_area_sqm,
             building_area_sqm, use_code, geom)
        VALUES %s
    """
    template = (
        "(%(matricule)s, %(civic_number)s, %(street_name)s, %(municipality)s, "
        "%(land_value)s, %(building_value)s, %(total_value)s, %(year_built)s, "
        "%(lot_area_sqm)s, %(building_area_sqm)s, %(use_code)s, "
        "ST_SetSRID(ST_MakePoint(%(lon)s, %(lat)s), 4326))"
    )
    template_no_geom = (
        "(%(matricule)s, %(civic_number)s, %(street_name)s, %(municipality)s, "
        "%(land_value)s, %(building_value)s, %(total_value)s, %(year_built)s, "
        "%(lot_area_sqm)s, %(building_area_sqm)s, %(use_code)s, NULL)"
    )

    def flush_batch():
        nonlocal total_inserted
        if not batch:
            return
        # Split into rows with and without geometry
        with_geom = [r for r in batch if r.get("lon") is not None]
        without_geom = [r for r in batch if r.get("lon") is None]
        if with_geom:
            psycopg2.extras.execute_values(
                cur, insert_sql, with_geom, template=template, page_size=BATCH_SIZE
            )
        if without_geom:
            psycopg2.extras.execute_values(
                cur, insert_sql, without_geom, template=template_no_geom, page_size=BATCH_SIZE
            )
        conn.commit()
        total_inserted += len(batch)
        batch.clear()

    with zipfile.ZipFile(zip_path) as zf:
        xml_files = [n for n in zf.namelist() if n.endswith(".xml")]
        logger.info(f"Traitement de {len(xml_files)} fichiers XML ...")

        for i, xml_name in enumerate(xml_files):
            with zf.open(xml_name) as f:
                try:
                    tree = ET.parse(f)
                except ET.ParseError as e:
                    logger.warning(f"  Erreur XML dans {xml_name}: {e}")
                    continue
            root = tree.getroot()
            mun_code = _text(root, "RLM01A")

            for unit in root.findall("RLUEx"):
                # Build matricule from RL0104 parts
                rl0104 = unit.find("RL0104")
                if rl0104 is None:
                    continue
                a = _text(rl0104, "RL0104A")
                b = _text(rl0104, "RL0104B")
                c = _text(rl0104, "RL0104C")
                d = _text(rl0104, "RL0104D")
                matricule = f"{a}{b}{c}{d}".ljust(18, "0")

                # Address from RL0101
                civic_number = None
                street_name = None
                rl0101 = unit.find("RL0101")
                if rl0101 is not None:
                    first_addr = rl0101.find("RL0101x")
                    if first_addr is not None:
                        civic_number = _text(first_addr, "RL0101Ax") or None
                        street_type = _text(first_addr, "RL0101Ex")
                        street_nm = _text(first_addr, "RL0101Gx")
                        if street_nm:
                            street_name = f"{street_type} {street_nm}".strip() if street_type else street_nm

                # Values
                land_value = _int_or_none(_text(unit, "RL0402A"))
                building_value = _int_or_none(_text(unit, "RL0403A"))
                total_value = _int_or_none(_text(unit, "RL0404A"))
                year_built = _int_or_none(_text(unit, "RL0307A"))
                lot_area_sqm = _float_or_none(_text(unit, "RL0302A"))
                building_area_sqm = _float_or_none(_text(unit, "RL0308A"))
                use_code = _text(unit, "RL0105A") or None

                # Coordinates from CSV
                coord = coords.get(matricule)
                lon = coord[0] if coord else None
                lat = coord[1] if coord else None

                batch.append({
                    "matricule": matricule,
                    "civic_number": civic_number,
                    "street_name": street_name,
                    "municipality": mun_code,
                    "land_value": land_value,
                    "building_value": building_value,
                    "total_value": total_value,
                    "year_built": year_built,
                    "lot_area_sqm": lot_area_sqm,
                    "building_area_sqm": building_area_sqm,
                    "use_code": use_code,
                    "lon": lon,
                    "lat": lat,
                })

                if len(batch) >= BATCH_SIZE:
                    flush_batch()

            if (i + 1) % 50 == 0:
                flush_batch()
                logger.info(f"  {i + 1}/{len(xml_files)} fichiers traités, {total_inserted} lignes insérées")

    flush_batch()
    cur.close()
    conn.close()
    return total_inserted


def parse_csv_only_and_insert(csv_path: str, dsn: str) -> int:
    """
    Mode simplifié : insère uniquement les données du CSV (matricule + coordonnées).
    Utile pour tester rapidement sans le ZIP XML.
    """
    logger.info("Mode CSV-only : import des coordonnées uniquement ...")
    conn = psycopg2.connect(dsn)
    conn.autocommit = False
    cur = conn.cursor()

    cur.execute("TRUNCATE TABLE property_assessments RESTART IDENTITY;")
    conn.commit()

    insert_sql = """
        INSERT INTO property_assessments (matricule, municipality, geom)
        VALUES %s
    """
    template = (
        "(%(matricule)s, %(municipality)s, "
        "ST_SetSRID(ST_MakePoint(%(lon)s, %(lat)s), 4326))"
    )

    total = 0
    batch = []
    with open(csv_path, "r", encoding="utf-8") as f:
        f.readline()  # skip header
        reader = csv.reader(f)
        for row in reader:
            if len(row) < 8:
                continue
            code_mun = row[1]
            mat18 = row[5]
            try:
                lon = float(row[6].replace(",", "."))
                lat = float(row[7].replace(",", "."))
            except (ValueError, IndexError):
                continue
            if not (-85 < lon < -50 and 40 < lat < 65):
                continue
            batch.append({"matricule": mat18, "municipality": code_mun, "lon": lon, "lat": lat})
            if len(batch) >= BATCH_SIZE:
                psycopg2.extras.execute_values(cur, insert_sql, batch, template=template, page_size=BATCH_SIZE)
                conn.commit()
                total += len(batch)
                batch.clear()
                if total % 100000 == 0:
                    logger.info(f"  {total} lignes insérées ...")

    if batch:
        psycopg2.extras.execute_values(cur, insert_sql, batch, template=template, page_size=BATCH_SIZE)
        conn.commit()
        total += len(batch)

    cur.close()
    conn.close()
    return total


def main():
    parser = argparse.ArgumentParser(description="Import évaluation foncière dans PostGIS")
    parser.add_argument("--dsn", default=os.environ.get("VIGIE_DB_DSN", DEFAULT_DSN),
                        help="DSN PostgreSQL (défaut: VIGIE_DB_DSN ou 'dbname=vigie_immo')")
    parser.add_argument("--skip-download", action="store_true",
                        help="Ne pas télécharger, utiliser les fichiers existants")
    parser.add_argument("--csv-only", action="store_true",
                        help="Importer uniquement le CSV (coordonnées sans valeurs foncières)")
    args = parser.parse_args()

    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    t0 = time.time()

    # Download
    if not args.skip_download:
        download_file(CSV_URL, CSV_PATH)
        if not args.csv_only:
            download_file(XML_URL, ZIP_PATH)
    else:
        if not os.path.exists(CSV_PATH):
            logger.error(f"CSV introuvable : {CSV_PATH}")
            sys.exit(1)
        if not args.csv_only and not os.path.exists(ZIP_PATH):
            logger.error(f"ZIP introuvable : {ZIP_PATH}")
            sys.exit(1)

    # Import
    if args.csv_only:
        count = parse_csv_only_and_insert(CSV_PATH, args.dsn)
    else:
        coords = parse_csv_coordinates(CSV_PATH)
        count = parse_xml_and_insert(ZIP_PATH, coords, args.dsn)

    elapsed = time.time() - t0
    logger.info(f"Import terminé : {count} lignes en {elapsed:.0f}s")

    # Verify
    conn = psycopg2.connect(args.dsn)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM property_assessments;")
    total = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM property_assessments WHERE geom IS NOT NULL;")
    with_geom = cur.fetchone()[0]
    logger.info(f"Vérification : {total} lignes totales, {with_geom} avec géométrie")
    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
