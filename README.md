# CKG Automation

Aplikasi web untuk mengotomatiskan input data peserta CKG (Cek Kesehatan Gratis)
dari file Excel ke portal CKG. Membaca Excel (format berbeda per kelompok usia),
menormalisasi ke format standar, menyimpan ke database, lalu mengisi & submit form
portal satu per satu secara otomatis menggunakan Playwright.

## Alur Kerja

```
Excel (bayi/balita/dewasa/lansia)
        │  readers.py  (normalisasi -> format standar)
        ▼
   Preview & Validasi  (cek data sebelum kirim)
        │  db.py  (simpan ke SQLite, deteksi duplikat NIK)
        ▼
   Playwright Bot  (login -> isi form pendaftaran -> isi form pelayanan -> submit)
        │  runner.py  (batch + progress + retry baris gagal)
        ▼
   Log hasil (.xlsx) + screenshot bukti + dashboard progress
```

## Struktur

| File | Fungsi |
|------|--------|
| `app/schema.py` | Format standar (Peserta) & daftar field per kelompok usia |
| `app/readers.py` | Baca Excel & normalisasi. **Sesuaikan MAPPING di sini** |
| `app/db.py` | Database SQLite (SQLAlchemy): model, simpan, status, dedup NIK |
| `app/automation/selectors.py` | Selector elemen portal. **Ganti placeholder dengan selektor asli** |
| `app/automation/ckg_bot.py` | Bot Playwright (login, OTP, re-login, isi form, submit) |
| `app/runner.py` | Orkestrasi batch + progress + retry + log |
| `app/main.py` | Web app (upload, preview, dashboard, retry) |
| `tools/buat_contoh_excel.py` | Generator file Excel contoh untuk uji reader |

## Setup (Windows / PowerShell)

Mesin ini memakai **Python 3.14**, sehingga dependency dipasang dari wheel terbaru
(lihat `requirements.txt`). Dari folder project:

```powershell
# 1. (venv sudah ada di folder ini; bila membuat ulang:)
#    py -3.14 -m venv venv

# 2. Install dependency (pakai wheel, jangan compile dari source)
venv\Scripts\python.exe -m pip install --only-binary=:all: -r requirements.txt

# 3. Unduh browser Chromium untuk Playwright
venv\Scripts\python.exe -m playwright install chromium

# 4. (opsional) salin kredensial ke .env
copy .env.example .env

# 5. Jalankan aplikasi
venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

Buka http://localhost:8000

## File Excel Contoh (untuk uji coba)

Hasilkan 4 file dummy berformat berbeda per kelompok usia:

```powershell
venv\Scripts\python.exe tools\buat_contoh_excel.py
```

File muncul di `contoh_excel/`. Saat upload, pilih kelompok & **Baris Header**:

| File | Kelompok | Baris Header | Keunikan format |
|------|----------|--------------|------------------|
| `contoh_bayi.xlsx`   | bayi   | **1** | ada baris judul di atas header |
| `contoh_balita.xlsx` | balita | 0 | tanggal `dd/mm/YYYY` |
| `contoh_dewasa.xlsx` | dewasa | 0 | JK ditulis "Laki-laki"/"Perempuan" |
| `contoh_lansia.xlsx` | lansia | 0 | tanggal `dd-mm-YYYY` |

Beberapa baris sengaja dibuat tidak valid agar kolom **Status Validasi** di preview terlihat bekerja.

## Fitur

- **Database SQLite** (`data/ckg.db`): data peserta & status submit persisten lintas restart.
- **Deteksi duplikat NIK**: NIK yang sudah ada (di file yang sama maupun di DB) dilewati saat upload.
- **Retry**: tombol "Ulangi yang Gagal" di dashboard memproses ulang peserta berstatus `gagal`.
- **OTP/2FA**: isi "Tunggu OTP (detik)" + matikan headless → bot memberi jeda agar Anda
  memasukkan kode OTP manual di jendela browser.
- **Anti session-timeout**: sebelum tiap submit, bot memastikan sesi masih login; bila
  ter-logout, otomatis re-login.
- **Rate limiting**: `delay_ms` (default 800ms) memberi jeda antar aksi.

## Yang HARUS Disesuaikan Sebelum Produksi

### 1. `readers.py` → `MAPPING_*` (kolom Excel Anda)

Sisi **kiri** = field standar (jangan diubah), sisi **kanan** = nama header di Excel Anda.

```python
MAPPING_IDENTITAS_UMUM = {
    "nik": "NIK",                 # <- ganti "NIK" dgn nama kolom di file Anda
    "nama": "Nama",
    "tgl_lahir": "Tanggal Lahir",
    ...
}
```

Cara cepat memastikan benar: jalankan upload + preview pada file asli (data sedikit dulu).
Jika kolom NIK/Nama tampil kosong, berarti nama header di MAPPING belum cocok.

### 2. `selectors.py` (selector & URL portal)

Semua selector masih placeholder (`#nik`, dll). Cara mengisinya:

1. Buka portal CKG di Chrome, **login** manual.
2. Buka halaman form pendaftaran / pelayanan.
3. Klik kanan pada sebuah field → **Inspect**.
4. Pada elemen yang ter-highlight, cari atribut `id`, `name`, atau `data-*`.
   - Bila ada `id="nik_peserta"` → selector = `#nik_peserta`
   - Bila ada `name="nik"` → selector = `[name='nik']`
   - Hindari XPath panjang berbasis posisi (mudah rusak saat UI berubah).
5. Tempel ke `selectors.py` menggantikan placeholder.
6. Isi juga `URL_LOGIN` dan `URL_FORM_PENDAFTARAN`.
7. `indikator_sukses` = elemen yang muncul SETELAH aksi berhasil (mis. `.alert-success`).
8. `indikator_perlu_login` = elemen yang HANYA ada di halaman login (mis. `#username`);
   dipakai untuk mendeteksi session-timeout.

Prioritas selector yang stabil: **id > name > data-\* > CSS path**.

### 3. `ckg_bot.py` → urutan langkah

Sesuaikan alur `submit_peserta()` bila portal punya langkah berbeda (mis. cari peserta
dulu by NIK sebelum isi pelayanan, atau wizard multi-step).

## Catatan Penting

- **Legalitas & ToS**: pastikan automation diizinkan pengelola portal. Bila tersedia,
  integrasi API resmi (SatuSehat) lebih stabil & aman daripada RPA.
- **Data pribadi**: NIK & data kesehatan wajib dikelola sesuai UU PDP. `data/ckg.db`,
  file Excel, log, dan `.env` sudah masuk `.gitignore` — jangan commit.
- **Mulai kecil**: uji dengan 2-3 data dummy & `headless=false` agar bisa melihat proses,
  sebelum batch besar.
```
