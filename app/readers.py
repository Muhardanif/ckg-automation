"""
Reader Excel -> format standar (Peserta).

Tiap kelompok usia punya file Excel dengan kolom berbeda. Modul ini berisi
satu fungsi reader per kelompok usia. Tugasnya: membaca file, lalu memetakan
nama kolom asli Anda ke field standar.

>>> CARA MENYESUAIKAN <<<
Ubah dictionary `MAPPING_*` di bawah agar cocok dengan nama kolom (header)
di file Excel Anda yang sebenarnya. Kiri = field standar, kanan = nama kolom
di Excel Anda.
"""
import os
import pandas as pd
from datetime import datetime, timedelta
from typing import List, Optional

from .schema import (
    Peserta, KelompokUsia, FIELD_PEMERIKSAAN, DEFAULT_DATA_PENDUKUNG,
)


# ---------------------------------------------------------------------------
# MAPPING KOLOM: field_standar -> "Nama Kolom di Excel Anda"
# Sesuaikan sisi kanan dengan header asli file Excel masing-masing.
# ---------------------------------------------------------------------------
MAPPING_IDENTITAS_UMUM = {
    "nik": "NIK",
    "nama": "Nama",
    "tgl_lahir": "Tanggal Lahir",
    "jenis_kelamin": "Jenis Kelamin",
    "no_hp": "No. HP",
    "no_wa": "No. WhatsApp",
    "alamat": "Alamat",
}

# Kolom "data pendukung" (Step 2 portal). Boleh dibiarkan; bila kolomnya tidak
# ada di Excel, nilai default dari DEFAULT_DATA_PENDUKUNG (schema.py) dipakai.
MAPPING_DATA_PENDUKUNG = {
    "status_pernikahan": "Status Pernikahan",
    "disabilitas":       "Disabilitas",
    "pekerjaan":         "Pekerjaan",
    # Alamat Domisili = cascade wilayah (overlay "Pilih Lokasi") di portal.
    # Isi PERSIS seperti nama wilayah di portal.
    "provinsi":          "Provinsi",
    "kabupaten_kota":    "Kabupaten/Kota",
    "kecamatan":         "Kecamatan",
    "kelurahan":         "Kelurahan",
    "detail_alamat":     "Detail Alamat",
}

MAPPING_PEMERIKSAAN = {
    KelompokUsia.BAYI: {
        "berat_badan": "BB (kg)",
        "panjang_badan": "PB (cm)",
        "lingkar_kepala": "Lingkar Kepala",
        "skrining_hipotiroid": "Skrining Hipotiroid",
        "imunisasi": "Imunisasi",
    },
    KelompokUsia.BALITA: {
        "berat_badan": "BB (kg)",
        "tinggi_badan": "TB (cm)",
        "lingkar_kepala": "Lingkar Kepala",
        "status_gizi": "Status Gizi",
        "imunisasi": "Imunisasi",
        "perkembangan": "Perkembangan",
    },
    KelompokUsia.DEWASA: {
        "berat_badan": "BB (kg)",
        "tinggi_badan": "TB (cm)",
        "lingkar_perut": "Lingkar Perut",
        "tekanan_darah": "Tekanan Darah",
        "gula_darah": "Gula Darah",
        "kolesterol": "Kolesterol",
        "asam_urat": "Asam Urat",
        "skrining_jiwa": "Skrining Jiwa",
        "iva_hpv": "IVA/HPV",
    },
    KelompokUsia.LANSIA: {
        "berat_badan": "BB (kg)",
        "tinggi_badan": "TB (cm)",
        "tekanan_darah": "Tekanan Darah",
        "gula_darah": "Gula Darah",
        "kolesterol": "Kolesterol",
        "fungsi_kognitif": "Fungsi Kognitif",
        "skrining_jiwa": "Skrining Jiwa",
        "kemandirian": "Kemandirian",
    },
}


def _bersihkan(nilai):
    """Bersihkan nilai sel: NaN -> None, strip spasi, float bulat -> int."""
    if pd.isna(nilai):
        return None
    if isinstance(nilai, str):
        return nilai.strip()
    # angka bulat dari Excel (mis. 70.0) -> "70" agar rapi
    if isinstance(nilai, float) and nilai.is_integer():
        return str(int(nilai))
    return nilai


def _format_tanggal(nilai):
    """Normalisasi tanggal ke ISO YYYY-MM-DD."""
    if nilai is None:
        return None
    if isinstance(nilai, (datetime, pd.Timestamp)):
        return nilai.strftime("%Y-%m-%d")
    # coba beberapa format umum Indonesia
    for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d", "%d %b %Y"):
        try:
            return datetime.strptime(str(nilai).strip(), fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    # Insurance: bila tanggal tersimpan sbg nomor seri Excel (mis. "23201")
    s = str(nilai).strip()
    if s.replace(".0", "").isdigit() and 10000 <= int(float(s)) <= 80000:
        return (datetime(1899, 12, 30)
                + timedelta(days=int(float(s)))).strftime("%Y-%m-%d")
    return s  # biarkan apa adanya, ditandai saat validasi


def _normalisasi_jk(nilai):
    """Samakan jenis kelamin ke 'L'/'P'."""
    if nilai is None:
        return None
    v = str(nilai).strip().upper()
    if v in ("L", "LAKI-LAKI", "LAKI", "PRIA", "M", "MALE"):
        return "L"
    if v in ("P", "PEREMPUAN", "WANITA", "F", "FEMALE"):
        return "P"
    return v


def baca_excel(path: str, kelompok: KelompokUsia,
               header_row: int = 0, sheet_name=0) -> List[Peserta]:
    """
    Baca satu file Excel dan kembalikan list Peserta dalam format standar.

    Parameters
    ----------
    path : lokasi file .xlsx
    kelompok : KelompokUsia (menentukan mapping pemeriksaan yang dipakai)
    header_row : indeks baris header (0-based). File CKG sering punya
                 beberapa baris judul di atas, sesuaikan angkanya.
    sheet_name : nama/indeks sheet yang dibaca
    """
    # Paksa STRING hanya untuk kolom yang rawan (NIK & nomor telepon) agar 16
    # digit / 0 di depan tidak rusak. Kolom lain dibiarkan apa adanya supaya
    # sel TANGGAL terbaca sebagai tanggal (bukan nomor seri Excel).
    kolom_teks = [MAPPING_IDENTITAS_UMUM[k] for k in ("nik", "no_hp", "no_wa")]
    dtype_map = {c: str for c in kolom_teks}
    df = pd.read_excel(path, sheet_name=sheet_name, header=header_row,
                       dtype=dtype_map, engine="openpyxl")
    df.columns = [str(c).strip() for c in df.columns]

    map_pem = MAPPING_PEMERIKSAAN[kelompok]
    peserta_list: List[Peserta] = []

    for idx, row in df.iterrows():
        nik = _bersihkan(row.get(MAPPING_IDENTITAS_UMUM["nik"]))
        nama = _bersihkan(row.get(MAPPING_IDENTITAS_UMUM["nama"]))

        # lewati baris kosong
        if not nik and not nama:
            continue

        pemeriksaan = {}
        for field_std, kolom_excel in map_pem.items():
            pemeriksaan[field_std] = _bersihkan(row.get(kolom_excel))

        # data pendukung (Step 2): dari Excel bila ada, jika tidak pakai default
        pendukung = {}
        for field_std, kolom_excel in MAPPING_DATA_PENDUKUNG.items():
            nilai = _bersihkan(row.get(kolom_excel))
            if nilai is None:
                nilai = DEFAULT_DATA_PENDUKUNG.get(field_std)
            pendukung[field_std] = nilai

        peserta = Peserta(
            nik=str(nik) if nik else "",
            nama=str(nama) if nama else "",
            tgl_lahir=_format_tanggal(_bersihkan(
                row.get(MAPPING_IDENTITAS_UMUM["tgl_lahir"]))),
            jenis_kelamin=_normalisasi_jk(_bersihkan(
                row.get(MAPPING_IDENTITAS_UMUM["jenis_kelamin"]))),
            kelompok_usia=kelompok,
            no_hp=_bersihkan(row.get(MAPPING_IDENTITAS_UMUM["no_hp"])),
            no_wa=_bersihkan(row.get(MAPPING_IDENTITAS_UMUM["no_wa"])),
            alamat=_bersihkan(row.get(MAPPING_IDENTITAS_UMUM["alamat"])),
            pemeriksaan=pemeriksaan,
            status_pernikahan=pendukung["status_pernikahan"],
            disabilitas=pendukung["disabilitas"],
            pekerjaan=pendukung["pekerjaan"],
            provinsi=pendukung["provinsi"],
            kabupaten_kota=pendukung["kabupaten_kota"],
            kecamatan=pendukung["kecamatan"],
            kelurahan=pendukung["kelurahan"],
            detail_alamat=pendukung["detail_alamat"],
            # idx sudah relatif terhadap baris data (setelah header).
            # Nomor baris Excel asli = idx + header_row + 2 (1 utk header, 1 utk 1-based).
            baris_sumber=int(idx) + header_row + 2,
            file_sumber=os.path.basename(path),  # lintas-platform (Windows pakai \)
        )
        peserta_list.append(peserta)

    return peserta_list


def validasi(peserta: Peserta) -> List[str]:
    """Cek data wajib sebelum dikirim ke portal. Kembalikan list error."""
    errors = []
    if not peserta.nik or len(peserta.nik) != 16 or not peserta.nik.isdigit():
        errors.append("NIK harus 16 digit angka")
    if not peserta.nama:
        errors.append("Nama kosong")
    if not peserta.tgl_lahir:
        errors.append("Tanggal lahir kosong")
    if peserta.jenis_kelamin not in ("L", "P"):
        errors.append("Jenis kelamin tidak valid")
    return errors


def _tgl_dari_nik(nik: str):
    """
    Bongkar tanggal lahir & jenis kelamin yang ter-encode di NIK.

    NIK 16 digit: PPKKCC DDMMYY SSSS. Digit 7-12 = tanggal lahir (DDMMYY);
    untuk PEREMPUAN, DD ditambah 40. Kembalikan (day, month, yy, jk) atau None
    bila NIK tak valid. `yy` = 2 digit tahun (abad tak bisa dipastikan dari NIK).
    """
    if not nik or len(nik) != 16 or not nik.isdigit():
        return None
    dd = int(nik[6:8])
    mm = int(nik[8:10])
    yy = int(nik[10:12])
    perempuan = dd > 40
    day = dd - 40 if perempuan else dd
    if not (1 <= day <= 31 and 1 <= mm <= 12):
        return None
    return day, mm, yy, ("P" if perempuan else "L")


def cek_konsistensi_nik(peserta: Peserta) -> List[str]:
    """
    Bandingkan Tanggal Lahir & Jenis Kelamin di data dengan yang ter-encode di
    NIK. Kembalikan daftar PERINGATAN (bukan error fatal) - berguna agar data
    yang tidak cocok ketahuan SEBELUM dijalankan, supaya tidak ditolak portal
    ('Data peserta tidak valid') satu per satu.
    """
    peringatan = []
    info = _tgl_dari_nik(peserta.nik or "")
    if info is None:
        return peringatan   # NIK invalid -> ditangani validasi()
    day, mm, yy, jk_nik = info

    # Tanggal lahir: cocokkan day, month, & 2-digit tahun (abaikan abad)
    if peserta.tgl_lahir:
        try:
            d = datetime.strptime(peserta.tgl_lahir, "%Y-%m-%d")
            if (d.day, d.month, d.year % 100) != (day, mm, yy):
                peringatan.append(
                    f"Tanggal lahir '{peserta.tgl_lahir}' TIDAK cocok dengan NIK "
                    f"(NIK meng-encode {day:02d}-{mm:02d}-'{yy:02d}). "
                    f"Cek KTP - portal memvalidasi ke Dukcapil.")
        except ValueError:
            pass  # format tgl ditangani di tempat lain

    # Jenis kelamin: ganjil/genap day di NIK menentukan L/P
    if peserta.jenis_kelamin in ("L", "P") and peserta.jenis_kelamin != jk_nik:
        peringatan.append(
            f"Jenis kelamin '{peserta.jenis_kelamin}' TIDAK cocok dengan NIK "
            f"(NIK menunjukkan '{jk_nik}').")
    return peringatan


def koreksi_tgl_dari_nik(peserta: Peserta) -> Optional[str]:
    """
    Kembalikan Tanggal Lahir (ISO 'YYYY-MM-DD') hasil koreksi dari NIK bila
    `peserta.tgl_lahir` saat ini TIDAK cocok dengan tanggal yang ter-encode di
    NIK. NIK adalah kunci pencocokan portal ke Dukcapil, jadi tanggal dari NIK
    lebih mungkin cocok daripada tanggal di Excel. Kembalikan None bila:
      - NIK tidak valid (tak bisa diturunkan),
      - tanggal sudah cocok (tak perlu dikoreksi), atau
      - hasil koreksi bukan tanggal valid (mis. 31-02) -> biarkan dilewati.

    Abad (digit pertama tahun) tidak tersimpan di NIK. Bila hanya hari/bulan yang
    beda (2-digit tahun sudah sama), abad dari Excel dipertahankan. Bila 2-digit
    tahun pun beda, abad ditebak: 20yy bila <= tahun sekarang, selain itu 19yy.
    """
    info = _tgl_dari_nik(peserta.nik or "")
    if info is None:
        return None
    day, mm, yy, _jk = info

    tahun = None
    if peserta.tgl_lahir:
        try:
            d = datetime.strptime(peserta.tgl_lahir, "%Y-%m-%d")
            if (d.day, d.month, d.year % 100) == (day, mm, yy):
                return None                 # sudah cocok
            if d.year % 100 == yy:
                tahun = d.year              # abad benar, hanya hari/bulan beda
        except ValueError:
            pass                            # format tgl ditangani validasi()

    if tahun is None:
        skrg = datetime.now().year
        tahun = 2000 + yy if 2000 + yy <= skrg else 1900 + yy

    try:
        return datetime(tahun, mm, day).strftime("%Y-%m-%d")
    except ValueError:
        return None                         # tanggal mustahil -> jangan koreksi


def koreksi_jk_dari_nik(peserta: Peserta) -> Optional[str]:
    """
    Kembalikan Jenis Kelamin ('L'/'P') sesuai NIK bila `peserta.jenis_kelamin`
    saat ini TIDAK cocok dengan NIK (digit DD > 40 = perempuan). NIK = kunci
    pencocokan Dukcapil, jadi JK dari NIK lebih mungkin benar. Kembalikan None
    bila NIK tak valid, JK bukan 'L'/'P', atau sudah cocok (tak perlu dikoreksi).
    """
    info = _tgl_dari_nik(peserta.nik or "")
    if info is None:
        return None
    _day, _mm, _yy, jk_nik = info
    if peserta.jenis_kelamin in ("L", "P") and peserta.jenis_kelamin != jk_nik:
        return jk_nik
    return None
