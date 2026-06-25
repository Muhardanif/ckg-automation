"""
Mapping field -> selector elemen di portal CKG.

>>> PENTING <<<
Nilai selector di bawah masih PLACEHOLDER. Anda harus menggantinya dengan
selector asli dari portal CKG. Cara mendapatkannya:
  1. Buka portal CKG di Chrome, login.
  2. Buka halaman form pendaftaran / pelayanan.
  3. Klik kanan pada field -> Inspect.
  4. Salin atribut id / name / atau buat CSS selector / XPath.

Gunakan selector yang stabil. Prioritas: id > name > atribut data-* > CSS path.
Hindari XPath panjang berbasis posisi (mudah rusak saat UI berubah).
"""

# URL portal (ganti dengan URL asli)
URL_LOGIN = "https://portal-ckg.contoh.go.id/login"
URL_FORM_PENDAFTARAN = "https://portal-ckg.contoh.go.id/pendaftaran/baru"

# ===========================================================================
# PORTAL SATUSEHAT / SEHAT INDONESIAKU  (mode connect_over_cdp)
# ===========================================================================
# URL Chrome remote-debugging tempat Playwright menempel ke sesi login manual.
CDP_URL = "http://localhost:9222"
# Substring URL halaman CKG, dipakai memilih tab yang sudah login.
URL_CKG_BERISI = "kemkes.go.id"

# Pendekatan selector: berbasis TEKS LABEL / ROLE (tahan-banting), bukan id/class.
# Ganti string di bawah bila teks di portal berbeda. Tiap pemakaian diberi
# komentar "# TODO verifikasi selector" di ckg_bot.py.
SATUSEHAT = {
    # tombol
    "btn_daftar_baru":   "Daftar Baru",
    "btn_cek_nik":       "Cek NIK",          # TIDAK dipakai di jalur manual
    "btn_selanjutnya":   "Selanjutnya",
    "btn_lanjutkan":     "Lanjutkan",      # popup "Data peserta valid" setelah Step 1
    "btn_daftarkan_nik": "Daftarkan dengan NIK",
    "btn_daftarkan_tanpa_nik": "Daftarkan tanpa NIK",  # TODO verifikasi nama persis
    "btn_tutup":         "Tutup",

    # checkbox bypass Dukcapil: dicocokkan dgn regex "Tidak ... NIK"
    # (teks asli mungkin "Tidak punya NIK" / "Tidak ada NIK" / "Tidak memiliki NIK")
    "chk_tidak_punya_nik": r"Tidak.*NIK",    # TODO verifikasi teks & efek bypass

    # placeholder dropdown (untuk membuka dropdown custom Vue)
    "ph_jk": "Pilih jenis kelamin",

    # checkbox "Daftarkan tanpa data wali" (muncul utk balita/lansia/tanpa NIK).
    # Bila section data wali muncul, centang ini agar field wali tak wajib diisi.
    "chk_tanpa_wali": "Daftarkan tanpa data wali",

    # Step 1 - identitas (teks label terlihat)
    "label_nik":        "NIK",
    "label_nama":       "Nama Lengkap",
    "label_tgl_lahir":  "Tanggal Lahir",
    "label_jk":         "Jenis Kelamin",
    "label_wa":         "WhatsApp",          # "No. WhatsApp Aktif"
    "label_tgl_periksa": "Tanggal Pemeriksaan",

    # Step 2 - data pendukung (dropdown + textarea)
    "label_status_nikah":    "Status Pernikahan",
    "label_disabilitas":     "disabilitas",     # "Penyandang disabilitas"
    "label_pekerjaan":       "Pekerjaan",
    "label_alamat_domisili": "Alamat Domisili",
    "label_detail_alamat":   "Detail Alamat Domisili",

    # Teks penanda dialog sukses & kata kunci pencari nomor tiket
    "teks_berhasil": "Berhasil Daftar",
    "teks_tiket":    "Tiket",

    # Individu sudah pernah CKG -> portal menolak dgn notif ini (bukan error data)
    "teks_sudah_layanan": "sudah menerima layanan",

    # Popup hasil validasi Dukcapil setelah klik 'Selanjutnya' (Step 1)
    "teks_valid":       "Data peserta valid",
    "teks_tidak_valid": "Data peserta tidak valid",

    # Popup gagal proses di form Isi identitas (Step 1):
    # 'Terjadi kesalahan - Belum bisa memproses data. Silakan coba lagi.'
    # -> dicatat & dilewati (tidak diulang), bukan kegagalan teknis bot.
    "teks_belum_proses": "Belum bisa memproses data",

    # Teks penanda dialog GAGAL (mis. Cek NIK ditolak Dukcapil)
    "teks_error":    "Terjadi kesalahan",
    "teks_error2":   "Gagal memproses",
}

# ===========================================================================
# KONFIRMASI HADIR  (halaman /ckg-pendaftaran-individu, mode CDP)
# ===========================================================================
# Tahap setelah pendaftaran: peserta yang SUDAH terdaftar (punya No. Tiket)
# dikonfirmasi kehadirannya pada hari pemeriksaan.
#
# Alur halaman:
#   filter [Tanggal] [dropdown: Nomor Tiket/NIK/Nama] [textbox cari]
#   -> tabel "Data Individu Terdaftar" (kolom: No, Tanggal Pemeriksaan, Nama
#      Peserta, Tanggal Lahir, Jenis Kelamin, Aksi, No. WhatsApp ...).
#   Kolom Aksi tiap baris: tombol "Konfirmasi Hadir" (+ "Ganti Tanggal").
#   Baris yang sudah dikonfirmasi menampilkan teks "Sudah Hadir" (bukan tombol).
#
# Selector berbasis TEKS (tahan-banting). Ganti string bila teks portal berbeda.
# Halaman "Cari/Daftarkan Individu" — dipakai untuk PENDAFTARAN & KONFIRMASI HADIR.
URL_PENDAFTARAN_INDIVIDU = "https://sehatindonesiaku.kemkes.go.id/ckg-pendaftaran-individu"
URL_KONFIRMASI_HADIR = URL_PENDAFTARAN_INDIVIDU   # halaman yang sama
KONFIRMASI = {
    "url": URL_KONFIRMASI_HADIR,
    # opsi dropdown filter pencarian yang dipakai (cocokkan/cari berdasarkan NIK)
    "opsi_filter": "NIK",
    # teks opsi dropdown yang mungkin sedang terpilih (untuk membuka dropdown)
    "opsi_filter_semua": ("Nomor Tiket", "NIK", "Nama"),
    # placeholder textbox cari (berubah mengikuti dropdown: "Masukkan NIK", dst).
    "ph_cari": r"Masukkan",
    # tombol konfirmasi pada baris peserta -> memunculkan popup 'Tandai Hadir?'
    "btn_konfirmasi": "Konfirmasi Hadir",
    # penanda baris yang SUDAH dikonfirmasi hadir (terminal: lewati saat rerun)
    "teks_sudah_hadir": "Sudah Hadir",
    # penanda tabel kosong / NIK tak ketemu (cek tanggal filter / status daftar)
    "teks_kosong": r"Tidak ada data|tidak ditemukan|belum ada data|data kosong",

    # --- POPUP 'Tandai Hadir?' (muncul setelah klik 'Konfirmasi Hadir') ---
    # Isinya: Tanggal Kehadiran (default HARI INI, tak perlu diubah) + checkbox
    # persetujuan + tombol 'Hadir' (nonaktif sampai checkbox dicentang).
    "teks_popup": "Tandai Hadir",
    "chk_persetujuan": r"memahami.*bersedia|menjalani prosedur CKG",
    # PERSIS 'Hadir' saja (jangan substring - 'Konfirmasi Hadir' di tabel ikut kena).
    "btn_hadir": r"^\s*Hadir\s*$",

    # penanda berhasil konfirmasi (status baris berubah / toast). JANGAN pakai
    # 'kehadiran' - bentrok dgn judul 'Tanggal Kehadiran' di popup.
    "teks_berhasil": r"Sudah Hadir|berhasil dikonfirmasi|Berhasil ditandai|Berhasil",

    # dialog sukses 'Berhasil Hadir' (No. Tiket ...) -> tombol 'Tutup' WAJIB
    # diklik agar dialog menutup sebelum lanjut ke peserta berikutnya.
    "btn_tutup": r"^\s*Tutup\s*$",
}

# --- Halaman login ---
LOGIN = {
    "username": "#username",          # ganti
    "password": "#password",          # ganti
    "tombol_login": "button[type=submit]",
    "indikator_sukses": ".dashboard", # elemen yang muncul setelah login berhasil
    # Elemen yang HANYA muncul saat belum/ sudah ter-logout (mis. field username
    # di halaman login). Dipakai untuk deteksi session-timeout & auto re-login.
    "indikator_perlu_login": "#username",
}

# --- Form pendaftaran (identitas) ---
PENDAFTARAN = {
    "nik": "#nik",
    "nama": "#nama",
    "tgl_lahir": "#tanggal_lahir",
    "jenis_kelamin": "#jenis_kelamin",   # bila dropdown, lihat util select
    "no_hp": "#no_hp",
    "alamat": "#alamat",
    "tombol_simpan": "#btn-simpan-pendaftaran",
    "indikator_sukses": ".alert-success",
}

# --- Form pelayanan / hasil pemeriksaan, per kelompok usia ---
# Kunci dict = field standar (lihat schema.FIELD_PEMERIKSAAN)
PELAYANAN = {
    "dewasa": {
        "berat_badan": "#bb",
        "tinggi_badan": "#tb",
        "lingkar_perut": "#lingkar_perut",
        "tekanan_darah": "#tekanan_darah",
        "gula_darah": "#gula_darah",
        "kolesterol": "#kolesterol",
        "asam_urat": "#asam_urat",
        "skrining_jiwa": "#skrining_jiwa",
        "iva_hpv": "#iva_hpv",
        "tombol_simpan": "#btn-simpan-pelayanan",
        "indikator_sukses": ".alert-success",
    },
    "lansia": {
        "berat_badan": "#bb",
        "tinggi_badan": "#tb",
        "tekanan_darah": "#tekanan_darah",
        "gula_darah": "#gula_darah",
        "kolesterol": "#kolesterol",
        "fungsi_kognitif": "#fungsi_kognitif",
        "skrining_jiwa": "#skrining_jiwa",
        "kemandirian": "#kemandirian",
        "tombol_simpan": "#btn-simpan-pelayanan",
        "indikator_sukses": ".alert-success",
    },
    "balita": {
        "berat_badan": "#bb",
        "tinggi_badan": "#tb",
        "lingkar_kepala": "#lingkar_kepala",
        "status_gizi": "#status_gizi",
        "imunisasi": "#imunisasi",
        "perkembangan": "#perkembangan",
        "tombol_simpan": "#btn-simpan-pelayanan",
        "indikator_sukses": ".alert-success",
    },
    "bayi": {
        "berat_badan": "#bb",
        "panjang_badan": "#pb",
        "lingkar_kepala": "#lingkar_kepala",
        "skrining_hipotiroid": "#skrining_hipotiroid",
        "imunisasi": "#imunisasi",
        "tombol_simpan": "#btn-simpan-pelayanan",
        "indikator_sukses": ".alert-success",
    },
}
