"""
Runner tahap CDP (Konfirmasi Hadir & Pelayanan) untuk web UI.

Semua tahap memakai tool CLI di tools/ yg menyetir Chrome via CDP
(port 9222, login manual oleh petugas). Web UI cukup
MEMICU tool tsb sebagai subprocess lalu men-stream stdout-nya ke halaman (log live).
Hanya satu proses tahap yg boleh jalan pada satu waktu.
"""
import os
import re
import subprocess
import sys
import threading
from collections import deque
from datetime import datetime

from . import db

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_VENV_PY = os.path.join(ROOT, "venv", "Scripts", "python.exe")
PY = _VENV_PY if os.path.exists(_VENV_PY) else sys.executable
MAX_LOG = 600

# Menjaga transisi mulai/selesai: tanpa ini `if STAGE.running` di mulai_stage
# adalah check-then-set tanpa kunci, dan dua request bersamaan (dobel-klik,
# dua tab) sama-sama lolos lalu men-spawn dua subprocess yang menyetir Chrome
# yang sama — yang satu tak bisa dihentikan lagi.
_GERBANG = threading.Lock()

# Baris ringkasan tiap tool: "Selesai. Sukses=3  Gagal=1  Dilewati=0"
# (label pertama beda-beda: Sukses / Hadir / OK).
_RE_RINGKAS = re.compile(r"Selesai\.\s*\w+=(\d+)\s+Gagal=(\d+)")


class StageState:
    def __init__(self):
        self.running = False
        self.label = ""
        self.cmd = ""
        self.mulai = ""
        self.returncode = None
        self.log = deque(maxlen=MAX_LOG)
        self.log_n = 0           # jumlah baris yang PERNAH masuk (kursor absolut)
        self._proc = None
        self.run_id = None       # baris audit trail yang sedang terbuka
        self.dihentikan = False  # dibedakan dari gagal: operator yang menekan Hentikan

    def catat(self, baris):
        """Tambah 1 baris log. Semua penambahan WAJIB lewat sini: deque membuang
        baris tertua diam-diam, jadi log_n-lah satu-satunya cara tahu posisi
        absolut sebuah baris — dan itu kursor yang dipakai /stage/status."""
        self.log.append(baris)
        self.log_n += 1

    def snapshot(self, sejak=0):
        """`sejak` = indeks absolut baris pertama yang BELUM dipegang klien.
        Hanya baris setelahnya yang dikirim, supaya poll 1,5 detik tidak
        mengangkut ulang seluruh buffer 600 baris sepanjang run."""
        log = list(self.log)
        mulai = self.log_n - len(log)      # indeks absolut baris tertua di buffer
        if sejak > mulai:
            log = log[min(sejak - mulai, len(log)):]
            mulai = min(sejak, self.log_n)
        return {
            "running": self.running, "label": self.label, "cmd": self.cmd,
            "mulai": self.mulai, "returncode": self.returncode,
            "log": log, "log_mulai": mulai, "log_n": self.log_n,
            "run_id": self.run_id,
        }


STAGE = StageState()


def _stream(proc):
    try:
        for line in proc.stdout:
            STAGE.catat(line.rstrip("\n"))
    except Exception as e:
        STAGE.catat(f"[error baca output] {e}")
    proc.wait()
    dihentikan = STAGE.dihentikan
    # Ambil run_id ke variabel lokal SEBELUM melepas gerbang: menulis audit ke
    # SQLite makan puluhan milidetik, cukup lama bagi operator utk memulai tahap
    # berikutnya dan menimpa STAGE.run_id. Tanpa ini run baru ditutup dengan
    # hasil run lama, dan run lama tertinggal "berjalan" selamanya.
    with _GERBANG:
        run_id, STAGE.run_id = STAGE.run_id, None
        STAGE.returncode = proc.returncode
        STAGE.running = False
        STAGE.catat(f"[SELESAI] kode keluar = {proc.returncode}")
        baris_log = list(STAGE.log)

    # Proses yang di-terminate keluar dengan kode != 0; itu bukan kegagalan
    # tool, melainkan keputusan operator. Bedakan supaya riwayat jujur.
    sukses, gagal, ringkas = _hitung(baris_log)
    if dihentikan:
        status, ringkasan = "dihentikan", "Dihentikan oleh operator."
    elif proc.returncode == 0:
        # Pakai baris ringkasan tool apa adanya: ia memuat 'Dilewati=N' yang tak
        # punya kolom sendiri di tabel run, dan itu justru angka yang menjelaskan
        # run di mana tak ada satu pun peserta diproses.
        status, ringkasan = "sukses", ringkas or "Selesai tanpa error."
    else:
        status, ringkasan = "gagal", f"Tool keluar dengan kode {proc.returncode}."
    db.akhiri_run(run_id, status, returncode=proc.returncode,
                  ringkasan=ringkasan, sukses=sukses, gagal=gagal)


def _hitung(baris):
    """(sukses, gagal, baris_ringkasan) dari log tool. Angkanya sudah dicetak
    tool ke stdout; tanpa diparse, tiap baris audit tersimpan 0/0/0 dan riwayat
    tak bisa menjawab 'berapa peserta berhasil kemarin'."""
    for b in reversed(baris):
        m = _RE_RINGKAS.search(b)
        if m:
            return int(m.group(1)), int(m.group(2)), b[m.start():].strip()
    return 0, 0, ""


def mulai_stage(label, args, jenis="lain", parameter=None):
    """Jalankan `PY <args...>` sbg subprocess (cwd = root proyek). args = list
    diawali path skrip relatif, mis. ['tools/pelayanan.py','--excel',...]."""
    with _GERBANG:
        if STAGE.running:
            return False, "Masih ada proses berjalan. Tunggu selesai atau Hentikan dulu."
        STAGE.running = True
        STAGE.dihentikan = False
        STAGE.label = label
        STAGE.cmd = "python " + " ".join(args)
        STAGE.mulai = datetime.now().isoformat(timespec="seconds")
        STAGE.returncode = None
        STAGE.log.clear()
        STAGE.log_n = 0
        STAGE.catat(f"[MULAI] {label} — {STAGE.mulai}")
        STAGE.catat(f"[CMD] {STAGE.cmd}")

        STAGE.run_id = None
        try:
            # Di dalam try bersama Popen: kalau DB gagal (file terkunci / disk
            # penuh), STAGE.running WAJIB kembali False, kalau tidak seluruh app
            # terkunci di "masih ada proses berjalan" sampai server di-restart.
            STAGE.run_id = db.mulai_run(jenis, label, perintah=STAGE.cmd,
                                        parameter=parameter or {})
            proc = subprocess.Popen(
                [PY] + args, cwd=ROOT,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, encoding="utf-8", errors="replace", bufsize=1)
        except Exception as e:
            STAGE.running = False
            STAGE.catat(f"[ERROR] gagal start: {e}")
            run_id, STAGE.run_id = STAGE.run_id, None
            db.akhiri_run(run_id, "gagal", ringkasan=f"Gagal start: {e}")
            return False, f"Gagal start: {e}"
        STAGE._proc = proc
    threading.Thread(target=_stream, args=(proc,), daemon=True).start()
    return True, f"Dimulai: {label}"


def stop_stage():
    if STAGE._proc and STAGE.running:
        try:
            STAGE.dihentikan = True
            STAGE._proc.terminate()
            STAGE.catat("[DIHENTIKAN] oleh pengguna.")
            return True
        except Exception:
            STAGE.dihentikan = False
            return False
    return False


def buka_chrome():
    """Jalankan 1_mulai_chrome.bat (buka Chrome remote-debugging 9222)."""
    bat = os.path.join(ROOT, "1_mulai_chrome.bat")
    if not os.path.exists(bat):
        return False, "1_mulai_chrome.bat tak ditemukan."
    try:
        subprocess.Popen([bat], cwd=ROOT, shell=True)
        return True, "Chrome (port 9222) dibuka. Login portal lalu buka menu CKG."
    except Exception as e:
        return False, f"Gagal buka Chrome: {e}"
