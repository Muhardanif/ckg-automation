"""
Generator file Excel CONTOH (dummy) untuk menguji reader/normalisasi.

Menghasilkan 4 file di folder `contoh_excel/`, satu per kelompok usia, dengan
FORMAT BERBEDA-BEDA agar mendekati kondisi nyata:
  - bayi   : ADA BARIS JUDUL di atas header  -> saat upload pakai header_row = 1
  - balita : header di baris pertama (header_row = 0), tanggal "dd/mm/YYYY"
  - dewasa : jenis kelamin ditulis "Laki-laki"/"Perempuan", tanggal "YYYY-mm-dd"
  - lansia : jenis kelamin "L"/"P", tanggal "dd-mm-YYYY"

Catatan: NIK & nama di sini FIKTIF (bukan data nyata). Beberapa baris sengaja
dibuat tidak valid (NIK kurang digit / jenis kelamin kosong) agar Anda bisa
melihat kolom "Status Validasi" di halaman preview bekerja.

Jalankan:
    venv\\Scripts\\python.exe tools\\buat_contoh_excel.py
"""
import os
from openpyxl import Workbook

OUT_DIR = "contoh_excel"
os.makedirs(OUT_DIR, exist_ok=True)


def _tulis(path, header, rows, judul=None):
    """Tulis satu sheet. Bila `judul` diisi, taruh di baris 1 (header jadi baris 2)."""
    wb = Workbook()
    ws = wb.active
    if judul:
        ws.append([judul])           # baris 1 = judul (header_row = 1 saat upload)
    ws.append(header)
    for r in rows:
        ws.append(r)
    wb.save(path)
    print(f"  - {path}  ({len(rows)} baris data)")


# ---------------------------------------------------------------------------
# BAYI  -> ada baris judul; upload dengan header_row = 1
# ---------------------------------------------------------------------------
bayi_header = ["NIK", "Nama", "Tanggal Lahir", "Jenis Kelamin", "No. HP", "Alamat",
               "BB (kg)", "PB (cm)", "Lingkar Kepala", "Skrining Hipotiroid", "Imunisasi"]
bayi_rows = [
    ["3201010101250001", "Bayi Aqila", "2025-01-10", "P", "081200000001", "Jl. Melati 1",
     "3.4", "50", "34", "Negatif", "HB0"],
    ["3201010101250002", "Bayi Bagas", "2025-02-15", "L", "081200000002", "Jl. Melati 2",
     "3.1", "49", "33.5", "Negatif", "HB0"],
    # baris tidak valid: NIK kurang dari 16 digit
    ["32010101", "Bayi Cinta", "2025-03-01", "P", "", "Jl. Melati 3",
     "2.9", "48", "33", "Belum", "-"],
]

# ---------------------------------------------------------------------------
# BALITA -> header baris pertama; tanggal dd/mm/YYYY
# ---------------------------------------------------------------------------
balita_header = ["NIK", "Nama", "Tanggal Lahir", "Jenis Kelamin", "No. HP", "Alamat",
                 "BB (kg)", "TB (cm)", "Lingkar Kepala", "Status Gizi", "Imunisasi", "Perkembangan"]
balita_rows = [
    ["3201010101220001", "Balita Dewi", "12/03/2022", "P", "081300000001", "Jl. Mawar 1",
     "12.5", "88", "47", "Baik", "Lengkap", "Sesuai"],
    ["3201010101210002", "Balita Eko", "25/07/2021", "L", "081300000002", "Jl. Mawar 2",
     "14.0", "95", "48", "Baik", "Lengkap", "Sesuai"],
    ["3201010101200003", "Balita Fitri", "01/01/2020", "P", "081300000003", "Jl. Mawar 3",
     "16.2", "102", "49", "Kurang", "Lengkap", "Meragukan"],
]

# ---------------------------------------------------------------------------
# DEWASA -> jenis kelamin "Laki-laki"/"Perempuan"; tanggal YYYY-mm-dd
# ---------------------------------------------------------------------------
dewasa_header = ["NIK", "Nama", "Tanggal Lahir", "Jenis Kelamin", "No. HP", "Alamat",
                 "BB (kg)", "TB (cm)", "Lingkar Perut", "Tekanan Darah", "Gula Darah",
                 "Kolesterol", "Asam Urat", "Skrining Jiwa", "IVA/HPV"]
dewasa_rows = [
    ["3201010101900001", "Dewasa Gunawan", "1990-05-12", "Laki-laki", "081400000001", "Jl. Anggrek 1",
     "70", "168", "85", "120/80", "95", "190", "5.5", "Normal", "-"],
    ["3201010101850002", "Dewasa Hesti", "1985-11-23", "Perempuan", "081400000002", "Jl. Anggrek 2",
     "58", "157", "78", "130/85", "110", "210", "4.8", "Normal", "Negatif"],
    # baris tidak valid: jenis kelamin kosong
    ["3201010101920003", "Dewasa Irfan", "1992-02-02", "", "081400000003", "Jl. Anggrek 3",
     "82", "175", "95", "140/90", "150", "230", "7.2", "Cemas ringan", "-"],
]

# ---------------------------------------------------------------------------
# LANSIA -> jenis kelamin "L"/"P"; tanggal dd-mm-YYYY
# ---------------------------------------------------------------------------
lansia_header = ["NIK", "Nama", "Tanggal Lahir", "Jenis Kelamin", "No. HP", "Alamat",
                 "BB (kg)", "TB (cm)", "Tekanan Darah", "Gula Darah", "Kolesterol",
                 "Fungsi Kognitif", "Skrining Jiwa", "Kemandirian"]
lansia_rows = [
    ["3201010101550001", "Lansia Joko", "10-08-1955", "L", "081500000001", "Jl. Kenanga 1",
     "65", "163", "150/90", "130", "220", "Normal", "Normal", "Mandiri"],
    ["3201010101600002", "Lansia Kartini", "05-05-1960", "P", "081500000002", "Jl. Kenanga 2",
     "60", "150", "145/85", "140", "240", "Gangguan ringan", "Normal", "Ketergantungan ringan"],
]


def main():
    print("Membuat file contoh Excel di folder:", OUT_DIR)
    _tulis(os.path.join(OUT_DIR, "contoh_bayi.xlsx"), bayi_header, bayi_rows,
           judul="DATA SKRINING BAYI - PUSKESMAS CONTOH (header di baris 2)")
    _tulis(os.path.join(OUT_DIR, "contoh_balita.xlsx"), balita_header, balita_rows)
    _tulis(os.path.join(OUT_DIR, "contoh_dewasa.xlsx"), dewasa_header, dewasa_rows)
    _tulis(os.path.join(OUT_DIR, "contoh_lansia.xlsx"), lansia_header, lansia_rows)
    print("Selesai. Saat upload:")
    print("  - contoh_bayi.xlsx   -> kelompok 'bayi',   Baris Header = 1")
    print("  - contoh_balita.xlsx -> kelompok 'balita', Baris Header = 0")
    print("  - contoh_dewasa.xlsx -> kelompok 'dewasa', Baris Header = 0")
    print("  - contoh_lansia.xlsx -> kelompok 'lansia', Baris Header = 0")


if __name__ == "__main__":
    main()
