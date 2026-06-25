"""
Aplikasi web CKG Automation.

Fitur:
  - Upload file Excel per kelompok usia
  - Preview hasil normalisasi (cek data sebelum submit)
  - Simpan peserta ke DB (SQLite, persisten)
  - Mulai proses automation + retry baris gagal
  - Dashboard progress real-time
  - Unduh log hasil
"""
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


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()       # buat tabel saat startup bila belum ada
    yield


app = FastAPI(title="CKG Automation", lifespan=lifespan)

BASE = os.path.dirname(__file__)
templates = Jinja2Templates(directory=os.path.join(BASE, "templates"))

# Pastikan folder static ada agar StaticFiles tidak menggagalkan startup.
STATIC_DIR = os.path.join(BASE, "static")
os.makedirs(STATIC_DIR, exist_ok=True)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

INPUT_DIR = "data/input"


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

    return templates.TemplateResponse(request, "preview.html", {
        "preview": preview,
        "kelompok": kelompok,
        "nama_file": file.filename,
        "total": len(peserta),
        "valid": sum(1 for x in preview if not x["errors"]),
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
    ok, pesan = mulai_stage("Pendaftaran (Batch)", args)
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
    ok, pesan = mulai_stage("Konfirmasi Hadir", args)
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
    ok, pesan = mulai_stage("Pelayanan", args)
    return JSONResponse({"ok": ok, "pesan": pesan})


@app.get("/stage/status")
def stage_status():
    return JSONResponse(STAGE.snapshot())


@app.post("/stage/stop")
def stage_stop():
    return JSONResponse({"ok": stop_stage()})


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
