# Cara Memulai / Melanjutkan Pendaftaran CKG

Panduan singkat untuk menjalankan otomasi pendaftaran CKG (mode tempel ke Chrome
yang login manual). Lakukan langkah ini tiap kali mau menjalankan/ melanjutkan.

## A. Melanjutkan obrolan dengan Claude (opsional)
Buka terminal di folder ini lalu:
```
claude --continue      # lanjutkan percakapan terakhir
# atau
claude --resume        # pilih dari daftar sesi sebelumnya
```

## B. Menyiapkan & menjalankan pendaftaran (wajib tiap hari)

1. **Buka Chrome khusus otomasi** — klik dua kali:
   ```
   1_mulai_chrome.bat
   ```
   (Membuka Chrome dengan remote-debugging port 9222 & profil `C:\chrome-ckg-debug`.)

2. **Login manual** di jendela Chrome itu ke https://sehatindonesiaku.kemkes.go.id
   (termasuk CAPTCHA), lalu buka menu **CKG Umum › Cari/Daftarkan Individu**.
   Biarkan halaman ini terbuka.

3. **Tutup file Excel** `data\input\template_pendaftaran.xlsx` di aplikasi Excel
   (skrip menulis-balik No. Tiket ke file ini; kalau terbuka, gagal disimpan).

4. **Jalankan batch** — klik dua kali:
   ```
   2_jalankan_batch.bat
   ```
   Skrip akan: melewati baris yang **sudah** punya No. Tiket, lalu mendaftarkan
   sisanya, dan menulis **No. Tiket / Status Daftar / Waktu Daftar** ke Excel.

## B2. Konfirmasi Hadir (tahap setelah pendaftaran)

Mengonfirmasi kehadiran peserta yang **sudah terdaftar** (Status Daftar = SUKSES).
Dilakukan di **hari pemeriksaan**.

1. Buka Chrome otomasi (`1_mulai_chrome.bat`), **login**, lalu buka
   **CKG Umum › Cari/Daftarkan Individu** (halaman `ckg-pendaftaran-individu`).
2. **Tutup** file Excel `data\input\template_pendaftaran.xlsx`.
3. **Uji 1 peserta dulu** (disarankan), ganti NIK dengan salah satu peserta SUKSES:
   ```
   venv\Scripts\python.exe tools\konfirmasi_hadir.py --excel data\input\template_pendaftaran.xlsx --nik 3515xxxxxxxxxxxx
   ```
4. Bila sukses, jalankan semua — klik dua kali **`3_konfirmasi_hadir.bat`**.

Skrip per baris **Status Daftar = SUKSES**: **set filter tanggal** = `Waktu Daftar`
baris itu → pilih dropdown filter **NIK** → ketik NIK → klik **Konfirmasi Hadir** →
di popup *Tandai Hadir* centang persetujuan → klik **Hadir** → **Tutup** dialog →
tulis **Status Hadir / Waktu Hadir** ke Excel. Baris yang sudah **HADIR** (atau
portal **SUDAH HADIR**) otomatis dilewati saat diulang. Override tanggal semua
baris: tambahkan `--tanggal YYYY-MM-DD`.

## C. Tool lain (jalankan dari terminal di folder ini)

- **Pra-cek data sebelum jalan** (cek NIK vs Tgl Lahir/JK, field wajib):
  ```
  venv\Scripts\python.exe tools\cek_data.py --excel data\input\template_pendaftaran.xlsx
  ```
- **Uji SATU peserta saja** (tidak menulis flag, tidak loop — untuk debug):
  ```
  venv\Scripts\python.exe tools\trial_daftar.py --excel data\input\template_pendaftaran.xlsx --baris 1
  ```
- **Batch sebagian** (mis. 10 baris mulai baris ke-5):
  ```
  venv\Scripts\python.exe tools\jalankan_batch.py --excel data\input\template_pendaftaran.xlsx --mulai 5 --jumlah 10
  ```

## Catatan penting
- **Format Tanggal Lahir di Excel: `YYYY-MM-DD`** (mis. `1964-04-08`) supaya tidak
  tertukar hari/bulan. Tanggal lahir HARUS cocok dgn NIK (portal validasi Dukcapil).
- Kolom alamat **Provinsi / Kabupaten-Kota / Kecamatan / Kelurahan** harus ditulis
  **persis** seperti nama di portal (mis. `Kab. Gresik`, bukan `Kabupaten Gresik`).
- Baris yang kolom **No. Tiket**-nya sudah terisi otomatis **dilewati** (anti-dobel) —
  berlaku untuk `jalankan_batch.py` MAUPUN `trial_daftar.py`.
- Saat sukses, **No. Tiket / Status / Waktu ditulis-balik** ke Excel oleh kedua skrip.
- Beda keduanya: `jalankan_batch.py` memproses **semua baris** otomatis; `trial_daftar.py`
  hanya **1 baris** (`--baris N`) untuk uji/debug. Override anti-dobel: `--paksa`.
