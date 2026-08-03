# Cara Memulai / Melanjutkan Pendaftaran CKG

Semua tahap dijalankan dari **aplikasi web** (halaman Operasi). Bot menempel ke
Chrome yang **login manual** — jadi Chrome-nya harus dibuka & di-login dulu.

Tiga tahap, urut: **Pendaftaran → Konfirmasi Hadir → Pelayanan**.

---

## 1. Buka aplikasi

Klik dua kali **`4_buka_aplikasi.bat`**.

Browser terbuka ke <http://127.0.0.1:8000/operasi>. **Biarkan jendela hitam
(server) tetap terbuka** selama memakai aplikasi; Ctrl+C untuk berhenti.

## 2. Persiapan (kartu paling atas)

1. Klik **Buka Chrome (port 9222)** — jendela Chrome khusus otomasi terbuka
   (profil `C:\chrome-ckg-debug`).
2. Di jendela itu: **login manual** ke <https://sehatindonesiaku.kemkes.go.id>
   (termasuk CAPTCHA), lalu buka menu CKG:
   - tahap 1 & 2 → **CKG Umum › Cari/Daftarkan Individu**
   - tahap 3 → halaman **Pelayanan**
3. **Tutup file Excel** `data\input\template_pendaftaran.xlsx`. Skrip
   menulis-balik ke file ini; kalau terbuka, gagal simpan.

Parameter di kartu ini dipakai **ketiga tahap**:

| Field | Isi |
|-------|-----|
| **File Excel** | bawaan `data/input/template_pendaftaran.xlsx` |
| **Kelompok usia** | mis. `lansia` — menentukan field & form yang dipakai |
| **NIK** | kosong = semua baris; diisi = **satu peserta saja** (dipakai untuk uji coba) |
| **Jeda antar-aksi (ms)** | kosong = bawaan (800 daftar/hadir, 600 pelayanan). Turunkan = lebih cepat, naikkan bila portal sering gagal merespons |

> Jalankan satu tahap pada satu waktu — aplikasi menolak tahap kedua selama ada
> proses berjalan. Log live & tombol **Hentikan** ada di kolom kanan.

## 3. Tahap 1 — Pendaftaran

Tombol **Jalankan Pendaftaran**. Baris yang **sudah punya No. Tiket dilewati**
(anti-dobel). Hasil → kolom **No. Tiket / Status Daftar / Waktu Daftar**
(`SUKSES`, `SUDAH CKG`, `DATA TIDAK VALID`, atau `GAGAL: …`).

Opsi:
- **Paksa** — tetap daftarkan walau NIK tak cocok Tgl Lahir/Jenis Kelamin.
- **Koreksi Tgl Lahir & Jenis Kelamin dari NIK** (aktif bawaan) — dibetulkan
  otomatis dari NIK, bukan dilewati.

## 4. Tahap 2 — Konfirmasi Hadir

Dikerjakan **di hari pemeriksaan**. Tombol **Jalankan Konfirmasi Hadir**. Hanya
baris **Status Daftar = SUKSES**; yang sudah `HADIR` dilewati saat diulang.

Per baris: set filter tanggal = `Waktu Daftar` baris itu → cari NIK → klik
**Konfirmasi Hadir** → centang persetujuan → **Hadir**. Hasil → kolom
**Status Hadir / Waktu Hadir**.

## 5. Tahap 3 — Pelayanan (isi form skrining)

**Selalu jalankan mode uji coba dulu**, dan pertama kali cukup **satu peserta**
(isi field NIK) untuk memeriksa pemetaan jawaban.

- **Mode**: *Uji coba* (isi form, tidak mengirim) / *Kirim sungguhan ke portal*.
- **Lanjutkan peserta yang belum selesai** (aktif bawaan) — teruskan yang
  terputus di tengah.
- **Paksa "Mulai Pemeriksaan"** — hanya bila peserta masih di tab *Belum
  Pemeriksaan* dan pemeriksaannya belum dimulai. Mode uji coba **tidak** memulai
  pemeriksaan.
- **Selesaikan + Konfirmasi — mengunci data.** Tidak bisa diedit lagi setelah
  ini. Baru centang kalau semua form sudah dipastikan benar.
- **Tab portal**: *Auto* mengikuti status di Excel; pilih manual bila perlu.

Hasil → kolom **Status Layanan / Waktu Layanan / Tanggal Pemeriksaan /
Waktu Mulai Periksa / Waktu Selesai Periksa**. `Status Layanan = SELESAI`
dilewati saat diulang.

## 6. Riwayat

Menu **Riwayat**: catatan tiap proses yang pernah dijalankan (parameter, waktu,
sukses/gagal, log). Berguna untuk mengecek apa yang dipakai run kemarin.

---

## Kalau perlu terminal (opsi yang belum ada di UI)

```
venv\Scripts\python.exe tools\cek_data.py --excel data\input\template_pendaftaran.xlsx
venv\Scripts\python.exe tools\jalankan_batch.py --excel … --mulai 5 --jumlah 10
venv\Scripts\python.exe tools\konfirmasi_hadir.py --excel … --tanggal 2026-06-12
venv\Scripts\python.exe tools\pelayanan.py --excel … --forms "Merokok"
```

`1_mulai_chrome.bat` / `2_jalankan_batch.bat` / `3_konfirmasi_hadir.bat` masih
ada dan mengerjakan hal yang sama tanpa UI.

## Catatan penting

- **Tanggal Lahir di Excel: `YYYY-MM-DD`** (mis. `1964-04-08`) dan **cocok
  dengan NIK** — portal memvalidasi ke Dukcapil.
- Kolom **Provinsi / Kabupaten-Kota / Kecamatan / Kelurahan** ditulis **persis**
  seperti di portal (mis. `Kab. Gresik`, bukan `Kabupaten Gresik`).
- Excel adalah sumber kebenaran hasil. Semua status ditulis-balik ke file yang
  sama; jangan buka file itu selagi proses jalan.
