"""
Cek logika tunggu-render kartu form pelayanan (tools/pelayanan_core.py).

Ini yang bikin 5 peserta mandek di status MULAI pada batch 2026-08-10: halaman
detail render bertahap, tool memotret kartu terlalu cepat, kartu Nakes terbaca
'tak ada' → form tak diisi → 'Selesaikan Layanan' ditolak gate.

JALANKAN:  venv\\Scripts\\python.exe test_pelayanan.py
Tanpa framework — cukup assert. Keluar kode 0 = semua lolos.
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "tools"))

from pelayanan import _peserta_terkunci  # noqa: E402
from pelayanan_core import _baris_transaksi_selesai, _tunggu_kartu_stabil  # noqa: E402


class _FakeLoc:
    """count() mengembalikan angka berikutnya dari `urut` (yg terakhir menetap)."""

    def __init__(self, urut):
        self.urut = list(urut)
        self.i = 0

    async def count(self):
        n = self.urut[min(self.i, len(self.urut) - 1)]
        self.i += 1
        return n


class _FakePage:
    def __init__(self, urut):
        self.loc = _FakeLoc(urut)
        self.tidur_ms = 0

    def get_by_role(self, role, name=None):
        return self.loc

    async def wait_for_timeout(self, ms):
        self.tidur_ms += ms


def test_tunggu_sampai_jumlah_kartu_berhenti_bertambah():
    # Mandiri render duluan (8), kartu Nakes menyusul (20), lengkap (44).
    page = _FakePage([8, 20, 44, 44, 44])
    assert asyncio.run(_tunggu_kartu_stabil(page)) == 44


def test_jeda_render_panjang_masih_bisa_lolos_terlalu_cepat():
    """Batas heuristik yg diketahui: render yg MANDEK >1,5 dtk terbaca stabil.
    Pengaman lapis kedua ada di _buka_form (pindaian diulang bila kartu belum
    ketemu), jadi ini dicatat sbg batas, bukan dianggap benar."""
    page = _FakePage([8, 8, 8, 30, 44, 44, 44])
    assert asyncio.run(_tunggu_kartu_stabil(page)) == 8


def test_halaman_kosong_menyerah_setelah_timeout_bukan_menggantung():
    page = _FakePage([0])
    assert asyncio.run(_tunggu_kartu_stabil(page, timeout_ms=2000)) == 0
    assert page.tidur_ms <= 2000


class _FakeBaris:
    """Berperan sbg locator baris sekaligus `.first`-nya."""

    def __init__(self, teks):
        self.teks = teks

    async def count(self):
        return 0 if self.teks is None else 1

    @property
    def first(self):
        return self

    async def inner_text(self):
        return self.teks


class _FakeListing:
    def __init__(self, teks):
        self.baris = _FakeBaris(teks)

    def locator(self, selector):
        return self

    def filter(self, has_text=None):
        return self.baris


def _terkunci(teks):
    return asyncio.run(_baris_transaksi_selesai(_FakeListing(teks), "HARLIK"))


def test_baris_terkunci_walau_mandiri_belum_lengkap_dianggap_terminal():
    # Petugas menekan 'Selesaikan Layanan' manual saat form Mandiri masih kosong.
    # Dulu terbaca BUKAN terminal -> tool cari tombol aksi yg tak ada -> GAGAL.
    assert _terkunci("1 HARLIK 3518104403830002 Belum Lengkap Selesai Pemeriksaan")


def test_baris_terkunci_dan_lengkap_dianggap_terminal():
    assert _terkunci("1 HARLIK 3518104403830002 Lengkap Selesai Pemeriksaan Lihat")


def test_baris_belum_terkunci_bukan_terminal():
    assert not _terkunci("1 HARLIK 3518104403830002 Lengkap Sedang Pemeriksaan Lanjutkan")
    assert not _terkunci("1 HARLIK 3518104403830002 Belum Lengkap Belum Pemeriksaan Mulai")


def test_baris_tak_ada_bukan_terminal():
    assert not _terkunci(None)


def test_baris_terkunci_dilewati_termasuk_saat_resume():
    """--resume berarti "lanjutkan yg belum selesai", jadi baris terkunci HARUS
    tetap dilewati. Dulu resume mengabaikan aturan ini dan men-search ulang
    tiap peserta yg sudah tuntas — belasan detik per orang, nol form bertambah,
    dan rincian 'SELESAI (isi=69, ...)' tertimpa jadi 'SUDAH SELESAI'."""
    assert _peserta_terkunci("SELESAI (isi=69, lewat=5, tak-berlaku=25)")
    assert _peserta_terkunci("SUDAH SELESAI")
    # Belum terkunci: justru inilah yg dimaksud "lanjutkan yg belum selesai".
    assert not _peserta_terkunci("MULAI (isi=31, lewat=7, tak-berlaku=28)")
    assert not _peserta_terkunci("DRAFT (dry-run)")
    assert not _peserta_terkunci("GAGAL: tak bisa buka detail")
    assert not _peserta_terkunci(None)


if __name__ == "__main__":
    for nama, fn in sorted(globals().items()):
        if nama.startswith("test_"):
            fn()
            print("OK", nama)
    print("Semua lolos.")
