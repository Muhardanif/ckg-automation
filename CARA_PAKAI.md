# Cara Pakai — Otomasi CKG

Otomasi 2 tahap di portal **sehatindonesiaku.kemkes.go.id** (mode tempel ke Chrome
yang login manual):
1. **Pendaftaran** — daftarkan peserta dari Excel → dapat **No. Tiket**.
2. **Konfirmasi Hadir** — tandai hadir peserta yang sudah SUKSES daftar.

File data: `data\input\template_pendaftaran.xlsx`.

---

## Persiapan (setiap kali mau jalan)

1. **Buka Chrome otomasi** — klik dua kali **`1_mulai_chrome.bat`**
   (Chrome dengan remote-debugging port 9222, profil `C:\chrome-ckg-debug`).
2. **Login manual** di Chrome itu ke https://sehatindonesiaku.kemkes.go.id
   (termasuk CAPTCHA), buka menu **CKG Umum › Cari/Daftarkan Individu**. Biarkan terbuka.
3. **Tutup file Excel** `data\input\template_pendaftaran.xlsx` (skrip menulis-balik ke
   file ini; kalau terbuka, gagal menyimpan).

---

## Tahap 1 — Pendaftaran

Klik dua kali **`2_jalankan_batch.bat`**.

- Memproses semua baris; **baris yang sudah punya No. Tiket dilewati** (anti-dobel).
- Hasil ditulis ke kolom **`No. Tiket` / `Status Daftar` / `Waktu Daftar`**.
- Status: `SUKSES`, `SUDAH CKG` (sudah pernah CKG), `DATA TIDAK VALID`
  (NIK/Nama/Tgl Lahir tak cocok Dukcapil), atau `GAGAL: …`.

**Uji 1 baris dulu (opsional):**
```
venv\Scripts\python.exe tools\trial_daftar.py --excel data\input\template_pendaftaran.xlsx --baris 1
```

---

## Tahap 2 — Konfirmasi Hadir

Dilakukan di **hari pemeriksaan**, setelah peserta SUKSES daftar.
Klik dua kali **`3_konfirmasi_hadir.bat`**.

- Hanya memproses baris **`Status Daftar = SUKSES`**.
- Per baris otomatis: **set filter tanggal** = `Waktu Daftar` baris itu → cari **NIK**
  → klik **Konfirmasi Hadir** → di popup *Tandai Hadir* centang persetujuan → klik
  **Hadir** → tutup dialog.
- Hasil ditulis ke kolom **`Status Hadir` / `Waktu Hadir`** (`HADIR`, `SUDAH HADIR`,
  `TIDAK DITEMUKAN`, atau `GAGAL: …`).
- Baris yang sudah `HADIR` otomatis dilewati saat diulang (anti-dobel).

**Uji 1 peserta dulu (disarankan):**
```
venv\Scripts\python.exe tools\konfirmasi_hadir.py --excel data\input\template_pendaftaran.xlsx --nik <NIK_peserta_SUKSES>
```

---

## Opsi berguna (jalankan dari terminal di folder ini)

| Kebutuhan | Perintah |
|-----------|----------|
| Pra-cek data (NIK vs Tgl Lahir/JK) | `venv\Scripts\python.exe tools\cek_data.py --excel data\input\template_pendaftaran.xlsx` |
| Daftar sebagian | `tools\jalankan_batch.py --excel … --mulai 5 --jumlah 10` |
| Konfirmasi sebagian | `tools\konfirmasi_hadir.py --excel … --mulai 5 --jumlah 10` |
| Override tanggal filter (semua baris) | `tools\konfirmasi_hadir.py --excel … --tanggal 2026-06-12` |
| Lebih cepat (jeda antar-aksi lebih kecil) | tambahkan `--delay 300` |

> Semua perintah `tools\…` diawali `venv\Scripts\python.exe`.

---

## Catatan penting

- **Format Tanggal Lahir di Excel: `YYYY-MM-DD`** (mis. `1964-04-08`) dan **cocok dengan
  NIK** (portal validasi Dukcapil).
- Kolom alamat **Provinsi / Kabupaten-Kota / Kecamatan / Kelurahan** ditulis **persis**
  seperti di portal (mis. `Kab. Gresik`).
- Urutan benar: **Pendaftaran dulu** (dapat No. Tiket) → **baru Konfirmasi Hadir**.
- Kalau muncul error "file Excel sedang dibuka" → **tutup Excel**, jalankan ulang
  (baris yang sudah sukses/hadir tidak akan diulang).
- Bukti tiap aksi tersimpan di `data\output\screenshots\`.
