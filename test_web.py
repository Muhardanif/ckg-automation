"""
Cek cepat lapisan web (app/main.py + app/stages.py).

Dua hal yang pernah menggigit dan tidak kelihatan dari layar:
1. Parameter dari form yang tidak sampai ke argv tool -> UI menjanjikan "hanya
   NIK X" tapi tool mendaftarkan SELURUH isi Excel ke portal.
2. Kegagalan DB saat memulai run -> STAGE.running nyangkut True dan seluruh
   aplikasi terkunci di "masih ada proses berjalan" sampai server di-restart.

JALANKAN:  venv\\Scripts\\python.exe test_web.py
Tanpa framework — cukup assert. Keluar kode 0 = semua lolos.
"""
import threading

from app import main, stages
from app.stages import STAGE

NIK = "3515060804640002"


def _rekam_argv(fn):
    """Panggil endpoint dgn mulai_stage disadap; kembalikan argv & parameter."""
    ditangkap = {}

    def palsu(label, args, jenis="lain", parameter=None):
        ditangkap["args"] = args
        ditangkap["parameter"] = parameter or {}
        return True, "ok"

    asli = main.mulai_stage
    main.mulai_stage = palsu
    try:
        fn()
    finally:
        main.mulai_stage = asli
    return ditangkap


def test_nik_sampai_ke_argv():
    """Ketiga tahap menghormati field NIK yang sama (satu field di halaman,
    dipakai bertiga). Pendaftaran dulu diam-diam membuangnya, jadi run yang
    dikonfirmasi sbg 'hanya NIK X' memproses seluruh file.

    Endpoint dipanggil langsung, bukan lewat HTTP (httpx tidak terpasang), jadi
    cek ini menangkap parameter yang hilang dari signature — bukan Form() yang
    lupa dipasang."""
    # Endpoint dipanggil langsung: setiap parameter harus disebut, kalau tidak
    # yang tersisa adalah objek Form() bawaan FastAPI, bukan string.
    umum = dict(excel="x.xlsx", kelompok="lansia", nik="  " + NIK + "  ", delay="")
    for panggil, skrip in (
            (lambda: main.stage_daftar(paksa="false", koreksi_nik="true", **umum),
             "tools/jalankan_batch.py"),
            (lambda: main.stage_hadir(tanggal="", **umum),
             "tools/konfirmasi_hadir.py"),
            (lambda: main.stage_pelayanan(mode="dry", resume="false",
                                          selesaikan="false",
                                          mulai_pemeriksaan="false", tab="", **umum),
             "tools/pelayanan.py")):
        d = _rekam_argv(panggil)
        args = d["args"]
        assert args[0] == skrip, args
        assert "--nik" in args, f"{skrip}: NIK dibuang diam-diam -> {args}"
        # spasi dari copy-paste tidak boleh ikut jadi filter
        assert args[args.index("--nik") + 1] == NIK, args
        # audit trail ikut mencatat, kalau tidak riwayat berbohong soal cakupan
        assert d["parameter"]["nik"] == NIK, d["parameter"]

    # NIK kosong = semua peserta; jangan kirim '--nik ""' (tak ada yang cocok)
    d = _rekam_argv(lambda: main.stage_daftar(excel="x.xlsx", kelompok="lansia",
                                              nik="   ", paksa="false",
                                              koreksi_nik="true", delay=""))
    assert "--nik" not in d["args"], d["args"]
    assert d["parameter"]["nik"] == "semua"


def test_delay_sampai_ke_argv():
    """Field Jeda dipakai ketiga tahap, seperti NIK. Kosong TIDAK boleh jadi
    '--delay ""' (argparse mati) dan tidak boleh diseragamkan: bawaan tiap tool
    berbeda (800/800/600 ms). Nilai ngawur dibuang, tapi audit trail harus
    mencatat yang BENAR-BENAR dipakai — kalau tidak riwayat mengklaim 4000 ms
    untuk run yang sebenarnya berjalan di bawaan."""
    umum = dict(excel="x.xlsx", kelompok="lansia", nik="")
    panggil = {
        "daftar": lambda d: main.stage_daftar(paksa="false", koreksi_nik="true",
                                              delay=d, **umum),
        "hadir": lambda d: main.stage_hadir(tanggal="", delay=d, **umum),
        "pelayanan": lambda d: main.stage_pelayanan(
            mode="dry", resume="false", selesaikan="false",
            mulai_pemeriksaan="false", tab="", delay=d, **umum),
    }
    for nama, fn in panggil.items():
        d = _rekam_argv(lambda: fn(" 300 "))
        assert "--delay" in d["args"], f"{nama}: jeda dibuang diam-diam -> {d['args']}"
        assert d["args"][d["args"].index("--delay") + 1] == "300", d["args"]
        assert d["parameter"]["delay"] == "300", d["parameter"]

        for buruk in ("", "   ", "cepat", "-100", "99999", "300.5"):
            d = _rekam_argv(lambda: fn(buruk))
            assert "--delay" not in d["args"], f"{nama}: {buruk!r} -> {d['args']}"
            assert d["parameter"]["delay"] == "bawaan", d["parameter"]


def test_hitung_ringkasan_tool():
    """Tiap tool memakai label sukses yang berbeda (Sukses/Hadir/OK); ketiganya
    harus terbaca, kalau tidak audit trail menyimpan 0/0 selamanya."""
    for baris, harap in (
            ("[BATCH] Selesai. Sukses=12  Gagal=3  Dilewati=5", (12, 3)),
            ("[HADIR] Selesai. Hadir=7  Gagal=0  Dilewati=1", (7, 0)),
            ("[YAN] Selesai. OK=4  Gagal=2  Dilewati=0  Durasi=1m", (4, 2))):
        s, g, ringkas = stages._hitung(["bising", baris, "sesudahnya"])
        assert (s, g) == harap, baris
        # ringkasan dipakai apa adanya di riwayat: prefiks tool dibuang, tapi
        # 'Dilewati=N' WAJIB ikut — itu satu-satunya tempat angka itu tersimpan
        assert ringkas.startswith("Selesai."), ringkas
        assert "Dilewati=" in ringkas, ringkas

    # baris ringkasan TERAKHIR yang dipakai (tool bisa mencetak ringkasan
    # antara), dan tanpa ringkasan sama sekali jangan mengarang angka
    assert stages._hitung(["Selesai. Sukses=1  Gagal=1",
                           "Selesai. Sukses=9  Gagal=0"])[:2] == (9, 0)
    assert stages._hitung(["GAGAL connect ke Chrome"]) == (0, 0, "")
    assert stages._hitung([]) == (0, 0, "")


def test_url_tab_saat_page_url_kosong():
    """Playwright kadang melaporkan page.url = '' untuk tab yang sudah terbuka
    sebelum connect_over_cdp (intermiten — tergantung keadaan tab saat menempel).
    Kalau tak ditangani, pencocokan tab portal meleset dan bot menyetir tab
    pertama yang kebetulan ada. Uji dgn page palsu supaya tak bergantung Chrome."""
    import asyncio
    from app.automation.ckg_bot import _url_tab

    class Palsu:
        def __init__(self, url, href=None, meledak=False):
            self.url, self._href, self._meledak = url, href, meledak

        async def evaluate(self, _):
            if self._meledak:
                raise RuntimeError("target closed")
            return self._href

    jalan = lambda pg: asyncio.run(_url_tab(pg))

    # jalur normal: page.url dipakai apa adanya, tanpa evaluate()
    assert jalan(Palsu("https://x.kemkes.go.id/ckg")) == "https://x.kemkes.go.id/ckg"
    # page.url kosong -> tanya halamannya
    assert jalan(Palsu("", "https://x.kemkes.go.id/ckg")) == "https://x.kemkes.go.id/ckg"
    # tab mati saat ditanya: kembalikan "", jangan melempar & membunuh seluruh run
    assert jalan(Palsu("", meledak=True)) == ""
    # evaluate mengembalikan None (tab kosong) -> "" , bukan None
    assert jalan(Palsu("", None)) == ""


def test_kursor_log():
    """snapshot(sejak) hanya mengirim baris baru, dan tetap benar setelah deque
    membuang baris tertua. Simulasikan juga rakit-ulang di sisi klien."""
    st = stages.StageState()
    for i in range(5):
        st.catat(f"baris {i}")

    s = st.snapshot()                       # klien baru: dapat semuanya
    assert (s["log_mulai"], s["log_n"]) == (0, 5)
    assert s["log"] == [f"baris {i}" for i in range(5)]

    assert st.snapshot(5)["log"] == []      # sudah mutakhir: tak ada kiriman
    assert st.snapshot(5)["log_mulai"] == 5
    st.catat("baris 5")
    s = st.snapshot(5)
    assert s["log"] == ["baris 5"] and s["log_mulai"] == 5   # hanya yang baru

    # sejak melebihi log_n (mis. klien menyimpan kursor run sebelumnya) tak
    # boleh melempar; log_n yang lebih kecil = sinyal reset bagi klien
    assert st.snapshot(999)["log"] == []

    # buffer meluap: baris tertua dibuang, tapi indeks absolut tetap benar
    kecil = stages.StageState()
    kecil.log = __import__("collections").deque(maxlen=3)
    for i in range(10):
        kecil.catat(f"b{i}")
    s = kecil.snapshot()
    assert kecil.log_n == 10
    assert (s["log"], s["log_mulai"]) == (["b7", "b8", "b9"], 7)
    # klien yang tertinggal lebih jauh dari buffer dapat apa yang masih ada
    assert kecil.snapshot(2)["log_mulai"] == 7
    assert kecil.snapshot(8)["log"] == ["b8", "b9"]

    # rakit-ulang sisi klien (cerminan gambar() di operasi.html)
    punya, baris = 0, []
    st2 = stages.StageState()
    for putaran in range(3):
        st2.catat(f"x{putaran}")
        s = st2.snapshot(punya)
        if s["log_n"] < punya:
            baris, punya = [], 0
        baris = baris + s["log"] if s["log_mulai"] == punya else list(s["log"])
        punya = s["log_mulai"] + len(s["log"])
    assert baris == ["x0", "x1", "x2"], baris
    assert punya == 3

    # tahap baru: log dikosongkan → log_n mundur, klien harus reset bukan dobel
    st2.log.clear(); st2.log_n = 0
    st2.catat("[MULAI] tahap baru")
    s = st2.snapshot(punya)
    assert s["log_n"] < punya, "klien tak punya sinyal reset"


def test_gagal_db_tidak_mengunci_aplikasi():
    """db.mulai_run() melempar -> mulai_stage harus melepas STAGE.running,
    kalau tidak tombol semua tahap disabled selamanya."""
    assert not STAGE.running, "ada proses lain berjalan; jalankan saat idle"

    asli = stages.db.mulai_run

    def meledak(*a, **kw):
        raise RuntimeError("database is locked")

    stages.db.mulai_run = meledak
    try:
        ok, pesan = stages.mulai_stage("Uji", ["tools/tidak_ada.py"])
    finally:
        stages.db.mulai_run = asli

    assert ok is False
    assert "database is locked" in pesan, pesan
    assert not STAGE.running, "STAGE.running nyangkut True -> app terkunci"
    assert STAGE.run_id is None


def test_run_ditutup_dgn_jumlah_yang_benar():
    """Jalankan subprocess sungguhan lewat mulai_stage dan tangkap apa yang
    ditulis ke audit trail. DB disadap supaya cek ini tidak mengotori riwayat."""
    assert not STAGE.running, "ada proses lain berjalan; jalankan saat idle"
    selesai = threading.Event()
    catat = {}

    def akhiri_palsu(run_id, status, returncode=None, ringkasan="",
                     sukses=0, gagal=0):
        catat.update(run_id=run_id, status=status, returncode=returncode,
                     sukses=sukses, gagal=gagal)
        selesai.set()

    asli_mulai, asli_akhiri = stages.db.mulai_run, stages.db.akhiri_run
    stages.db.mulai_run = lambda *a, **kw: 4242
    stages.db.akhiri_run = akhiri_palsu
    try:
        ok, _ = stages.mulai_stage(
            "Uji", ["-c", "print('Selesai. Sukses=12  Gagal=3  Dilewati=5')"])
        assert ok is True
        assert selesai.wait(30), "subprocess tidak pernah selesai"
    finally:
        stages.db.mulai_run, stages.db.akhiri_run = asli_mulai, asli_akhiri

    assert catat["run_id"] == 4242, catat        # bukan None: run tetap tertutup
    assert catat["status"] == "sukses", catat
    assert catat["returncode"] == 0, catat
    assert (catat["sukses"], catat["gagal"]) == (12, 3), catat
    assert not STAGE.running
    assert STAGE.run_id is None


if __name__ == "__main__":
    for nama, fn in sorted(globals().items()):
        if nama.startswith("test_"):
            fn()
            print(f"OK  {nama}")
    print("\nSemua cek lolos.")
