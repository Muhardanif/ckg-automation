"""
Aplikasi web CKG Automation.

Pemicu untuk tool CDP di tools/ — petugas login MANUAL di Chrome (port 9222),
aplikasi ini hanya menjalankan tahapannya dan mencatat hasilnya.

Fitur:
  - Operasi: jalankan tahap Pendaftaran / Konfirmasi Hadir / Pelayanan
  - Riwayat run (audit trail) + drill-down
"""
import glob
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

from .schema import KelompokUsia
from .stages import STAGE, mulai_stage, stop_stage, buka_chrome
from . import db

log = logging.getLogger("uvicorn.error")

BASE = os.path.dirname(__file__)
ROOT = os.path.dirname(BASE)


def _peringatkan_css_basi() -> None:
    """Teriak bila app.css lebih tua dari sumber kelasnya.

    Tailwind hanya meng-emit class yang dipakai template. Kalau template
    diubah tanpa `npm run build:css`, class barunya diam-diam tidak ada dan
    UI rusak tanpa error apa pun — pernah terjadi: indikator langkah hilang
    di tiga halaman selama seminggu. Gagal-nyaring lebih baik daripada
    gagal-diam.

    Catatan: Tailwind CLI tidak menulis ulang app.css bila hasilnya identik
    byte-per-byte, sehingga mtime-nya tidak maju dan cek ini akan beralarm
    palsu. Karena itu `npm run build:css` selalu diakhiri script `stamp` yang
    memperbarui mtime berkas.
    """
    css = os.path.join(BASE, "static", "app.css")
    if not os.path.exists(css):
        log.warning("app/static/app.css tidak ada. Jalankan: npm run build:css")
        return
    umur_css = os.path.getmtime(css)
    # Semua yang di-@source / di-@import theme.css harus ikut dipantau. ui.js
    # ikut di sini karena markup modal konfirmasi lahir di sana, bukan di template.
    sumber = glob.glob(os.path.join(BASE, "templates", "*.html"))
    sumber.append(os.path.join(BASE, "static", "ui.js"))
    sumber += glob.glob(os.path.join(ROOT, "design-system", "*.css"))
    lebih_baru = [os.path.basename(p) for p in sumber
                  if os.path.exists(p) and os.path.getmtime(p) > umur_css]
    if lebih_baru:
        log.warning(
            "app.css BASI — lebih tua dari: %s. Class baru tidak akan berlaku. "
            "Jalankan: npm run build:css", ", ".join(sorted(lebih_baru)))


# Class varian yang disusun dinamis oleh macro (`btn-{{ variant }}`) dan karena
# itu tak terlihat oleh pemindai Tailwind. Semuanya di-safelist lewat
# `@source inline(...)` di theme.css. Kalau safelist itu hilang, class-nya tidak
# di-emit dan tombol/alert tampil abu-abu polos TANPA error apa pun — persis
# yang pernah terjadi pada `btn-warning` dan `btn-neutral`.
_SENTINEL_CSS = ("btn-warning", "btn-neutral", "btn-success",
                 "alert-warning", "badge-info", "checkbox-sm")


def _peringatkan_varian_hilang() -> None:
    css = os.path.join(BASE, "static", "app.css")
    if not os.path.exists(css):
        return
    with open(css, "r", encoding="utf-8") as f:
        isi = f.read()
    hilang = [c for c in _SENTINEL_CSS if c not in isi]
    if hilang:
        log.warning(
            "Varian DaisyUI tidak ter-emit: %s. Cek `@source inline(...)` di "
            "design-system/theme.css lalu `npm run build:css`.", ", ".join(hilang))


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()       # buat tabel saat startup bila belum ada
    yatim = db.tandai_run_tergantung()
    if yatim:
        log.warning("%d run tergantung dari sesi sebelumnya ditandai gagal.", yatim)
    _peringatkan_css_basi()
    _peringatkan_varian_hilang()
    yield


app = FastAPI(title="CKG Automation", lifespan=lifespan)

templates = Jinja2Templates(directory=os.path.join(BASE, "templates"))

# Pastikan folder static ada agar StaticFiles tidak menggagalkan startup.
STATIC_DIR = os.path.join(BASE, "static")
os.makedirs(STATIC_DIR, exist_ok=True)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


def versi_aset(nama: str) -> int:
    """Cache-buster untuk berkas di app/static (dipakai template sbg ?v=...).

    Tanpa ini browser boleh memakai app.css/ui.js lama dari cache-nya
    berhari-hari (heuristic caching), sehingga sehabis `npm run build:css`
    template baru dirender dengan CSS lama dan tata letak berantakan —
    hanya sembuh dengan Ctrl+F5. Mtime di query string membuat URL berubah
    setiap build, jadi browser pasti mengambil versi baru.

    Dibaca per render (bukan sekali saat startup) supaya rebuild saat server
    masih hidup — mis. `npm run watch:css` — juga langsung terlihat.
    """
    try:
        return int(os.path.getmtime(os.path.join(STATIC_DIR, nama)))
    except OSError:
        return 0


templates.env.globals["versi_aset"] = versi_aset


@app.get("/")
def beranda():
    return RedirectResponse("/operasi", status_code=303)


# ----------------------------------------------------------------------------
# Tahap CDP: Konfirmasi Hadir & Pelayanan (memicu tools/ sbg subprocess).
# ----------------------------------------------------------------------------
EXCEL_DEFAULT = "data/input/template_pendaftaran.xlsx"


def _path(s: str) -> str:
    """Rapikan path yang ditempel operator. "Copy as path" di Windows Explorer
    menyertakan tanda kutip; tanpa dibuang, kutipnya ikut jadi bagian nama file
    (Popen tanpa shell) dan openpyxl gagal dgn pesan yang membingungkan."""
    return s.strip().strip('"')


@app.get("/operasi", response_class=HTMLResponse)
def operasi(request: Request):
    return templates.TemplateResponse(request, "operasi.html", {
        "kelompok": [k.value for k in KelompokUsia],
        "excel_default": EXCEL_DEFAULT,
    })


@app.post("/stage/chrome")
def stage_chrome():
    ok, pesan = buka_chrome()
    return JSONResponse({"ok": ok, "pesan": pesan})


@app.post("/stage/daftar")
def stage_daftar(excel: str = Form(EXCEL_DEFAULT),
                 kelompok: str = Form("lansia"),
                 nik: str = Form(""),
                 paksa: str = Form("false"),
                 koreksi_nik: str = Form("true")):
    excel = _path(excel)
    args = ["tools/jalankan_batch.py", "--excel", excel, "--kelompok", kelompok]
    if nik.strip():
        args += ["--nik", nik.strip()]
    if paksa == "true":
        args += ["--paksa"]
    if koreksi_nik != "true":
        args += ["--no-koreksi-tgl", "--no-koreksi-jk"]
    ok, pesan = mulai_stage(
        "Pendaftaran (Batch)", args, jenis="daftar",
        parameter={"excel": excel, "kelompok": kelompok,
                   "nik": nik.strip() or "semua",
                   "paksa": paksa == "true", "koreksi_nik": koreksi_nik == "true"})
    return JSONResponse({"ok": ok, "pesan": pesan})


@app.post("/stage/hadir")
def stage_hadir(excel: str = Form(EXCEL_DEFAULT),
                kelompok: str = Form("lansia"),
                nik: str = Form(""),
                tanggal: str = Form("")):
    excel = _path(excel)
    args = ["tools/konfirmasi_hadir.py", "--excel", excel, "--kelompok", kelompok]
    if nik.strip():
        args += ["--nik", nik.strip()]
    if tanggal.strip():
        args += ["--tanggal", tanggal.strip()]
    ok, pesan = mulai_stage(
        "Konfirmasi Hadir", args, jenis="hadir",
        parameter={"excel": excel, "kelompok": kelompok,
                   "nik": nik.strip() or "semua", "tanggal": tanggal.strip()})
    return JSONResponse({"ok": ok, "pesan": pesan})


@app.post("/stage/pelayanan")
def stage_pelayanan(excel: str = Form(EXCEL_DEFAULT),
                    kelompok: str = Form("lansia"),
                    mode: str = Form("dry"),            # 'dry' | 'submit'
                    resume: str = Form("false"),
                    selesaikan: str = Form("false"),
                    mulai_pemeriksaan: str = Form("false"),
                    nik: str = Form(""),
                    tab: str = Form("")):
    excel = _path(excel)
    args = ["tools/pelayanan.py", "--excel", excel, "--kelompok", kelompok]
    args += ["--submit"] if mode == "submit" else ["--dry-run"]
    if resume == "true":
        args += ["--resume"]
    if selesaikan == "true":
        args += ["--selesaikan"]
    if mulai_pemeriksaan == "true":
        args += ["--mulai-pemeriksaan"]
    if nik.strip():
        args += ["--nik", nik.strip()]
    if tab.strip():
        args += ["--tab", tab.strip()]
    # `selesaikan` mengunci data peserta secara final — parameter paling
    # penting untuk dicatat di audit trail.
    ok, pesan = mulai_stage(
        "Pelayanan", args, jenis="pelayanan",
        parameter={"excel": excel, "kelompok": kelompok, "mode": mode,
                   "resume": resume == "true",
                   "selesaikan": selesaikan == "true",
                   "mulai_pemeriksaan": mulai_pemeriksaan == "true",
                   "nik": nik.strip() or "semua", "tab": tab.strip() or "auto"})
    return JSONResponse({"ok": ok, "pesan": pesan})


@app.get("/stage/status")
def stage_status(sejak: int = 0):
    # `sejak` = kursor: indeks absolut baris log pertama yang belum dipegang
    # klien. Tanpa ini tiap poll 1,5 detik mengangkut ulang seluruh buffer.
    return JSONResponse(STAGE.snapshot(max(sejak, 0)))


@app.post("/stage/stop")
def stage_stop():
    ok = stop_stage()
    return JSONResponse({"ok": ok, "pesan": "Perintah hentikan dikirim."
                         if ok else "Tidak ada proses yang berjalan."})


# ----------------------------------------------------------------------------
# Riwayat (audit trail)
# ----------------------------------------------------------------------------
RUN_PER_HALAMAN = 20


def _paginasi(total: int, halaman: int, per_halaman: int) -> dict:
    jml_halaman = max(1, -(-total // per_halaman))  # pembulatan ke atas
    halaman = min(max(1, halaman), jml_halaman)
    return {"halaman": halaman, "jml_halaman": jml_halaman, "total": total,
            "offset": (halaman - 1) * per_halaman, "per_halaman": per_halaman}


@app.get("/riwayat", response_class=HTMLResponse)
def riwayat(request: Request, halaman: int = 1, jenis: str = ""):
    total = db.daftar_run(limit=1, offset=0, jenis=jenis)[1]
    p = _paginasi(total, halaman, RUN_PER_HALAMAN)
    rows, _ = db.daftar_run(limit=p["per_halaman"], offset=p["offset"], jenis=jenis)
    return templates.TemplateResponse(request, "riwayat.html", {
        "runs": rows, "p": p, "jenis": jenis,
        "jenis_pilihan": ["daftar", "hadir", "pelayanan"],
    })


@app.get("/riwayat/{run_id}", response_class=HTMLResponse)
def riwayat_detail(request: Request, run_id: int):
    run = db.ambil_run(run_id)
    if run is None:
        return RedirectResponse("/riwayat?notif=tidak-ada", status_code=303)
    return templates.TemplateResponse(request, "riwayat_detail.html", {"run": run})


