"""
Aplikasi web CKG Automation.

Fitur:
  - Upload file Excel per kelompok usia
  - Preview hasil normalisasi (cek data sebelum submit)
  - Simpan peserta ke DB (SQLite, persisten)
  - Mulai proses automation + retry baris gagal
  - Dashboard progress real-time
  - Riwayat run (audit trail) + drill-down data peserta
  - Unduh log hasil
"""
import glob
import logging
import os
import shutil
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, UploadFile, File, Form
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

from .readers import baca_excel, validasi
from .schema import KelompokUsia, StatusSubmit
from .runner import jalankan, simpan_log, STATE, LOG_PATH
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
    sumber = glob.glob(os.path.join(BASE, "templates", "*.html"))
    sumber.append(os.path.join(ROOT, "design-system", "theme.css"))
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

INPUT_DIR = "data/input"

# Batas baris yang dirender di halaman Preview. Excel bisa berisi ribuan
# peserta; merender semuanya membuat halaman berat tanpa memberi informasi
# tambahan. Baris bermasalah selalu ditampilkan lebih dulu karena itu yang
# perlu ditindak.
PREVIEW_MAKS = 100


@app.get("/", response_class=HTMLResponse)
def beranda(request: Request):
    return templates.TemplateResponse(request, "index.html", {
        "kelompok": [k.value for k in KelompokUsia],
        "jumlah_siap": db.jumlah_belum(),
    })


@app.post("/upload", response_class=HTMLResponse)
async def upload(request: Request,
                 file: UploadFile = File(...),
                 kelompok: str = Form(...),
                 header_row: int = Form(0)):
    os.makedirs(INPUT_DIR, exist_ok=True)
    dest = os.path.join(INPUT_DIR, file.filename)
    with open(dest, "wb") as f:
        shutil.copyfileobj(file.file, f)

    try:
        peserta = baca_excel(dest, KelompokUsia(kelompok), header_row=header_row)
    except Exception as e:
        return templates.TemplateResponse(request, "index.html", {
            "kelompok": [k.value for k in KelompokUsia],
            "jumlah_siap": db.jumlah_belum(),
            "error": f"Gagal baca Excel: {e}",
        })

    # validasi untuk preview
    preview = []
    for p in peserta:
        err = validasi(p)
        preview.append({"peserta": p, "errors": err})

    # simpan ke DB (deteksi duplikat NIK terhadap data yang sudah ada)
    hasil = db.simpan_batch(peserta, file.filename, KelompokUsia(kelompok))

    valid = sum(1 for x in preview if not x["errors"])
    # Baris bermasalah dulu — itu yang butuh keputusan operator.
    terurut = sorted(preview, key=lambda x: not x["errors"])

    return templates.TemplateResponse(request, "preview.html", {
        "preview": terurut[:PREVIEW_MAKS],
        "ditampilkan": min(len(terurut), PREVIEW_MAKS),
        "kelompok": kelompok,
        "nama_file": file.filename,
        "total": len(peserta),
        "valid": valid,
        "disimpan": hasil["disimpan"],
        "duplikat": hasil["duplikat"],
        "jumlah_siap": db.jumlah_belum(),
    })


@app.post("/mulai")
def mulai(headless: bool = Form(True),
          username: str = Form(...),
          password: str = Form(...),
          delay_ms: int = Form(800),
          otp_wait_s: int = Form(0)):
    ok, pesan = jalankan(username, password, headless=headless,
                         delay_ms=delay_ms, otp_wait_s=otp_wait_s,
                         statuses=[StatusSubmit.BELUM.value])
    return JSONResponse({"ok": ok, "pesan": pesan})


@app.post("/retry")
def retry(headless: bool = Form(True),
          username: str = Form(...),
          password: str = Form(...),
          delay_ms: int = Form(800),
          otp_wait_s: int = Form(0)):
    """Ulangi submit untuk peserta yang berstatus GAGAL."""
    ok, pesan = jalankan(username, password, headless=headless,
                         delay_ms=delay_ms, otp_wait_s=otp_wait_s,
                         statuses=[StatusSubmit.GAGAL.value])
    return JSONResponse({"ok": ok, "pesan": pesan})


@app.get("/status")
def status():
    return JSONResponse(STATE.snapshot())


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request):
    return templates.TemplateResponse(request, "dashboard.html", {
        "notif": request.query_params.get("notif"),
    })


@app.post("/reset")
def reset():
    db.hapus_belum()
    return RedirectResponse("/", status_code=303)


# ----------------------------------------------------------------------------
# Tahap CDP: Konfirmasi Hadir & Pelayanan (memicu tools/ sbg subprocess).
# ----------------------------------------------------------------------------
EXCEL_DEFAULT = "data/input/template_pendaftaran.xlsx"


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
                 paksa: str = Form("false"),
                 koreksi_nik: str = Form("true")):
    args = ["tools/jalankan_batch.py", "--excel", excel, "--kelompok", kelompok]
    if paksa == "true":
        args += ["--paksa"]
    if koreksi_nik != "true":
        args += ["--no-koreksi-tgl", "--no-koreksi-jk"]
    ok, pesan = mulai_stage(
        "Pendaftaran (Batch)", args, jenis="daftar",
        parameter={"excel": excel, "kelompok": kelompok,
                   "paksa": paksa == "true", "koreksi_nik": koreksi_nik == "true"})
    return JSONResponse({"ok": ok, "pesan": pesan})


@app.post("/stage/hadir")
def stage_hadir(excel: str = Form(EXCEL_DEFAULT),
                kelompok: str = Form("lansia"),
                nik: str = Form(""),
                tanggal: str = Form("")):
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
def stage_status():
    return JSONResponse(STAGE.snapshot())


@app.post("/stage/stop")
def stage_stop():
    return JSONResponse({"ok": stop_stage()})


# ----------------------------------------------------------------------------
# Riwayat (audit trail) & drill-down peserta
# ----------------------------------------------------------------------------
RUN_PER_HALAMAN = 20
PESERTA_PER_HALAMAN = 25


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
        "jenis_pilihan": ["daftar", "daftar-login", "hadir", "pelayanan"],
    })


@app.get("/riwayat/{run_id}", response_class=HTMLResponse)
def riwayat_detail(request: Request, run_id: int):
    run = db.ambil_run(run_id)
    if run is None:
        return RedirectResponse("/riwayat?notif=tidak-ada", status_code=303)
    return templates.TemplateResponse(request, "riwayat_detail.html", {"run": run})


@app.get("/peserta", response_class=HTMLResponse)
def peserta(request: Request, q: str = "", status: str = "", halaman: int = 1):
    total = db.cari_peserta(q=q, status=status, limit=1, offset=0)[1]
    p = _paginasi(total, halaman, PESERTA_PER_HALAMAN)
    rows, _ = db.cari_peserta(q=q, status=status,
                              limit=p["per_halaman"], offset=p["offset"])
    return templates.TemplateResponse(request, "peserta.html", {
        "rows": rows, "p": p, "q": q, "status": status,
        "status_pilihan": [s.value for s in StatusSubmit],
    })


@app.get("/unduh-log")
def unduh_log():
    # regenerasi log dari DB agar selalu mutakhir
    try:
        simpan_log()
    except Exception:
        pass
    if os.path.exists(LOG_PATH):
        return FileResponse(LOG_PATH, filename="log_submit.xlsx")
    # Hindari dead-end JSON mentah: kembalikan pengguna ke Dashboard dgn notif.
    return RedirectResponse("/dashboard?notif=log-kosong", status_code=303)
