"""
PRA-CEK data Excel SEBELUM dijalankan ke portal.

Untuk tiap baris: cek field wajib (NIK 16 digit, nama, tgl lahir, jenis kelamin)
DAN konsistensi NIK vs Tanggal Lahir / Jenis Kelamin. Tujuannya menandai baris
bermasalah lebih dulu, supaya tidak ditolak portal ('Data peserta tidak valid')
satu per satu saat batch.

PAKAI:
   venv\\Scripts\\python.exe tools\\cek_data.py --excel data/input/template_pendaftaran.xlsx
   venv\\Scripts\\python.exe tools\\cek_data.py --excel data/input/template_pendaftaran.xlsx --kelompok lansia
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.readers import baca_excel, validasi, cek_konsistensi_nik   # noqa: E402
from app.schema import KelompokUsia                                 # noqa: E402


def main():
    ap = argparse.ArgumentParser(description="Pra-cek data Excel pendaftaran CKG.")
    ap.add_argument("--excel", required=True)
    ap.add_argument("--kelompok", default="dewasa",
                    help="bayi/balita/dewasa/lansia (default dewasa).")
    ap.add_argument("--header-row", dest="header_row", type=int, default=0)
    args = ap.parse_args()

    ps = baca_excel(args.excel, KelompokUsia(args.kelompok), header_row=args.header_row)
    print(f"Terbaca {len(ps)} baris dari {args.excel}\n")

    n_error = n_warn = n_ok = 0
    for i, p in enumerate(ps, start=1):
        errors = validasi(p)
        warns = cek_konsistensi_nik(p)
        label = f"Baris {i} (Excel baris {p.baris_sumber}) | NIK={p.nik or '-'} | {p.nama or '-'}"
        if not errors and not warns:
            n_ok += 1
            continue
        print(label)
        for e in errors:
            print(f"   [ERROR]      {e}")
            n_error += 1
        for w in warns:
            print(f"   [PERINGATAN] {w}")
            n_warn += 1
        print()

    print("=" * 60)
    print(f"OK: {n_ok}   |   Baris dgn ERROR: "
          f"{sum(1 for p in ps if validasi(p))}   |   "
          f"Total peringatan: {n_warn}")
    print("ERROR = wajib diperbaiki (pasti ditolak). "
          "PERINGATAN = cek KTP, kemungkinan ditolak Dukcapil.")
    # exit code: 2 bila ada error, 1 bila hanya peringatan, 0 bila bersih
    if n_error:
        sys.exit(2)
    if n_warn:
        sys.exit(1)
    print("Semua baris lolos pra-cek.")
    sys.exit(0)


if __name__ == "__main__":
    main()
