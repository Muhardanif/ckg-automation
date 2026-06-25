"""
Format standar internal CKG.

Semua file Excel (bayi/anak/dewasa/lansia) dengan format berbeda-beda
akan dinormalisasi menjadi struktur ini, sehingga modul automation hanya
perlu memahami SATU format, bukan empat.
"""
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Optional


class KelompokUsia(str, Enum):
    BAYI = "bayi"          # 0 - 2 hari / neonatus
    BALITA = "balita"      # 1 - 6 tahun (balita & prasekolah)
    DEWASA = "dewasa"      # 18 - 59 tahun
    LANSIA = "lansia"      # 60 tahun ke atas


class StatusSubmit(str, Enum):
    BELUM = "belum"        # belum dikirim ke portal
    PROSES = "proses"      # sedang dikirim
    SUKSES = "sukses"      # berhasil submit
    GAGAL = "gagal"        # gagal, lihat keterangan


@dataclass
class Peserta:
    """Satu baris peserta CKG dalam format standar."""

    # --- Identitas (wajib untuk semua kelompok usia) ---
    nik: str
    nama: str
    tgl_lahir: str                 # format ISO: YYYY-MM-DD
    jenis_kelamin: str             # "L" / "P"
    kelompok_usia: KelompokUsia

    # --- Kontak & alamat (opsional) ---
    no_hp: Optional[str] = None        # nomor telepon umum (bila ada)
    no_wa: Optional[str] = None        # No. WhatsApp Aktif (+62) untuk portal CKG
    alamat: Optional[str] = None

    # --- Data pendaftaran portal SATUSEHAT (Step 2 wizard "Isi data pendukung") ---
    # Opsional; hanya dipakai modul automation saat mendaftarkan ke portal.
    tanggal_pemeriksaan: Optional[str] = None   # None = pakai default kalender (hari ini)
    status_pernikahan: Optional[str] = None     # mis. "Belum Kawin" / "Kawin"
    disabilitas: Optional[str] = None           # mis. "Tidak"
    pekerjaan: Optional[str] = None
    # Alamat Domisili = cascade wilayah (overlay "Pilih Lokasi"). Nilai HARUS sama
    # persis dgn nama wilayah di portal (mis. "Jawa Timur", "Kabupaten Gresik").
    provinsi: Optional[str] = None
    kabupaten_kota: Optional[str] = None
    kecamatan: Optional[str] = None
    kelurahan: Optional[str] = None
    alamat_domisili: Optional[str] = None        # (lama) tidak dipakai lagi utk cascade
    detail_alamat: Optional[str] = None          # textarea detail (RT/RW, jalan)

    # --- Hasil pemeriksaan (bervariasi per kelompok usia) ---
    # Disimpan sebagai dict fleksibel agar tiap kelompok bisa punya
    # field berbeda tanpa mengubah struktur utama.
    # contoh dewasa: {"tekanan_darah": "120/80", "gula_darah": "95", ...}
    # contoh bayi:   {"berat_badan": "3.2", "panjang_badan": "49", ...}
    pemeriksaan: dict = field(default_factory=dict)

    # --- Metadata proses automation ---
    baris_sumber: Optional[int] = None     # nomor baris di excel asal
    file_sumber: Optional[str] = None      # nama file asal
    status_submit: StatusSubmit = StatusSubmit.BELUM
    keterangan: Optional[str] = None       # alasan gagal / pesan error
    waktu_submit: Optional[str] = None      # timestamp ISO
    bukti_screenshot: Optional[str] = None  # path screenshot bukti

    def to_dict(self) -> dict:
        d = asdict(self)
        d["kelompok_usia"] = self.kelompok_usia.value
        d["status_submit"] = self.status_submit.value
        return d


# Nilai DEFAULT untuk "data pendukung" (Step 2 wizard) bila tidak tersedia di
# Excel. Ubah di SATU tempat ini saja. Pastikan teksnya PERSIS sama dengan opsi
# dropdown di portal (mis. "Belum Kawin", "Tidak ada", "Lainnya").
DEFAULT_DATA_PENDUKUNG = {
    "status_pernikahan": "Belum Kawin",
    "disabilitas":       "Tidak ada",
    "pekerjaan":         "Lainnya",
    # Cascade wilayah: tidak ada default (harus dari Excel; nama wajib persis portal).
    "provinsi":          None,
    "kabupaten_kota":    None,
    "kecamatan":         None,
    "kelurahan":         None,
    "detail_alamat":     "-",
}


# Daftar field pemeriksaan yang diharapkan per kelompok usia.
# Ini jadi acuan reader saat normalisasi & acuan bot saat mengisi form.
# SESUAIKAN dengan field asli di portal CKG setelah Anda cek halamannya.
FIELD_PEMERIKSAAN = {
    KelompokUsia.BAYI: [
        "berat_badan",          # kg
        "panjang_badan",        # cm
        "lingkar_kepala",       # cm
        "skrining_hipotiroid",  # ya/tidak/hasil
        "imunisasi",
    ],
    KelompokUsia.BALITA: [
        "berat_badan",
        "tinggi_badan",
        "lingkar_kepala",
        "status_gizi",
        "imunisasi",
        "perkembangan",         # sesuai/tidak (KPSP)
    ],
    KelompokUsia.DEWASA: [
        "berat_badan",
        "tinggi_badan",
        "lingkar_perut",
        "tekanan_darah",        # mmHg, contoh "120/80"
        "gula_darah",           # mg/dL
        "kolesterol",
        "asam_urat",
        "skrining_jiwa",        # SRQ
        "iva_hpv",              # khusus perempuan
    ],
    KelompokUsia.LANSIA: [
        "berat_badan",
        "tinggi_badan",
        "tekanan_darah",
        "gula_darah",
        "kolesterol",
        "fungsi_kognitif",      # mini-cog / AMT
        "skrining_jiwa",
        "kemandirian",          # ADL
    ],
}
