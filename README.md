# CKG Automation

Otomasi input data peserta CKG (Cek Kesehatan Gratis) dari Excel ke portal
**sehatindonesiaku.kemkes.go.id**, memakai Playwright yang **menempel ke Chrome
milik petugas** lewat CDP.

**Login dilakukan MANUAL oleh petugas** — termasuk CAPTCHA. Program tidak pernah
menyimpan, meminta, atau mengirim kredensial portal. Bot hanya menempel ke tab
yang sudah login dan mengisi form.

## Alur Kerja

```
data/input/template_pendaftaran.xlsx
        │  app/readers.py  (normalisasi -> dataclass Peserta)
        ▼
   Chrome (login manual, --remote-debugging-port=9222)
        │  app/automation/ckg_bot.py  (menempel via CDP, isi wizard portal)
        ▼
   3 tahap: Pendaftaran -> Konfirmasi Hadir -> Pelayanan
        │  app/excel_hasil.py  (tulis-balik + warnai baris)
        ▼
   Excel yang sama: No. Tiket / Status Daftar / Status Hadir / Status Layanan
```

Excel adalah **sumber kebenaran hasil**, bukan database. SQLite (`data/ckg.db`)
hanya menyimpan audit trail: siapa menjalankan tahap apa, kapan, hasilnya.

## Struktur

| File | Fungsi |
|------|--------|
| `app/schema.py` | Format standar (Peserta) & daftar field per kelompok usia |
| `app/readers.py` | Baca Excel & normalisasi. **Sesuaikan MAPPING di sini** |
| `app/excel_hasil.py` | Tulis-balik hasil ke Excel + status terminal (anti-dobel) |
| `app/automation/selectors.py` | Teks label / regex elemen portal |
| `app/automation/ckg_bot.py` | Bot Playwright: menempel via CDP, isi wizard pendaftaran |
| `app/db.py` | SQLite: tabel `run` (audit trail) |
| `app/stages.py` | Memicu tool di `tools/` sebagai subprocess & men-stream log |
| `app/main.py` | Web UI: halaman Operasi & Riwayat |
| `tools/jalankan_batch.py` | Tahap 1 — pendaftaran batch |
| `tools/konfirmasi_hadir.py` | Tahap 2 — konfirmasi kehadiran |
| `tools/pelayanan.py` | Tahap 3 — isi form skrining (pakai `pelayanan_core.py`) |

## Setup (Windows / PowerShell)

Mesin ini memakai **Python 3.14**, jadi dependency dipasang dari wheel terbaru.

```powershell
# 1. (venv sudah ada; bila membuat ulang:)  py -3.14 -m venv venv

# 2. Dependency (wheel saja, jangan compile dari source)
venv\Scripts\python.exe -m pip install --only-binary=:all: -r requirements.txt

# 3. Build CSS (wajib setelah mengubah template)
npm install
npm run build:css

# 4. Jalankan aplikasi
venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

Buka http://localhost:8000 → langsung ke halaman **Operasi**.

Playwright **tidak** perlu `playwright install`: bot menempel ke Chrome yang
sudah terpasang di komputer, tidak meluncurkan Chromium sendiri.

## Cara Menjalankan

Panduan operator: **`MULAI.md`**. Intinya tiap kali mau jalan:

1. `4_buka_aplikasi.bat` — web UI di http://127.0.0.1:8000/operasi
2. Tombol **Buka Chrome (port 9222)**, login manual + CAPTCHA, buka menu CKG
3. **Tutup** file Excel (skrip menulis-balik ke file itu)
4. Jalankan tahap 1 → 2 → 3 dari halaman Operasi

## Anti-dobel

Baris yang **No. Tiket**-nya sudah terisi dilewati. Begitu juga baris berstatus
terminal: `SUDAH CKG`, `DATA TIDAK VALID`, `GAGAL DUKCAPIL` — mengulanginya tidak
akan berhasil karena masalahnya di data sumber, bukan di koneksi.

Untuk memaksa satu baris diproses ulang (mis. setelah data Dukcapil dibetulkan):
**kosongkan sel `Status Daftar`** baris itu.

## Yang Perlu Disesuaikan

### `readers.py` → `MAPPING_*`

Sisi **kiri** = field standar (jangan diubah), sisi **kanan** = nama header di
Excel Anda.

```python
MAPPING_IDENTITAS_UMUM = {
    "nik": "NIK",                 # <- ganti dgn nama kolom di file Anda
    "nama": "Nama",
    "tgl_lahir": "Tanggal Lahir",
    ...
}
```

Cek cepat tanpa menyentuh portal:

```powershell
venv\Scripts\python.exe tools\cek_data.py --excel data\input\template_pendaftaran.xlsx
venv\Scripts\python.exe test_readers.py
```

### `selectors.py`

Berbasis **teks label / role**, bukan `id`/`class` — portal ini SPA Vue tanpa id
stabil. Kalau teks di portal berubah, ganti string di sini.

## Catatan Penting

- **Legalitas & ToS**: pastikan otomasi diizinkan pengelola portal. Bila tersedia,
  integrasi API resmi (SATUSEHAT) lebih stabil & aman daripada RPA.
- **Data pribadi**: NIK & data kesehatan wajib dikelola sesuai UU PDP.
  `data/`, log, dan screenshot sudah masuk `.gitignore` — jangan commit.
- **Mulai kecil**: uji `trial_daftar.py --baris 1` sebelum batch besar.
- **Tahap Pelayanan default DRY-RUN**: form diisi tapi tidak dikirim. Tambahkan
  `--submit` bila sudah yakin.
