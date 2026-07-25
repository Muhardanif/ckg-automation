"""
Runner tahap CDP (Konfirmasi Hadir & Pelayanan) untuk web UI.

Berbeda dari runner.py (pendaftaran, login in-process), tahap ini memakai tool
CLI di tools/ yg menyetir Chrome via CDP (port 9222, login manual). Web UI cukup
MEMICU tool tsb sebagai subprocess lalu men-stream stdout-nya ke halaman (log live).
Hanya satu proses tahap yg boleh jalan pada satu waktu.
"""
import os
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


class StageState:
    def __init__(self):
        self.running = False
        self.label = ""
        self.cmd = ""
        self.mulai = ""
        self.returncode = None
        self.log = deque(maxlen=MAX_LOG)
        self._proc = None
        self.run_id = None       # baris audit trail yang sedang terbuka
        self.dihentikan = False  # dibedakan dari gagal: operator yang menekan Hentikan

    def snapshot(self):
        return {
            "running": self.running, "label": self.label, "cmd": self.cmd,
            "mulai": self.mulai, "returncode": self.returncode,
            "log": list(self.log), "run_id": self.run_id,
        }


STAGE = StageState()


def _stream(proc):
    try:
        for line in proc.stdout:
            STAGE.log.append(line.rstrip("\n"))
    except Exception as e:
        STAGE.log.append(f"[error baca output] {e}")
    proc.wait()
    STAGE.returncode = proc.returncode
    STAGE.running = False
    STAGE.log.append(f"[SELESAI] kode keluar = {proc.returncode}")

    # Proses yang di-terminate keluar dengan kode != 0; itu bukan kegagalan
    # tool, melainkan keputusan operator. Bedakan supaya riwayat jujur.
    if STAGE.dihentikan:
        status, ringkasan = "dihentikan", "Dihentikan oleh operator."
    elif proc.returncode == 0:
        status, ringkasan = "sukses", "Selesai tanpa error."
    else:
        status, ringkasan = "gagal", f"Tool keluar dengan kode {proc.returncode}."
    db.akhiri_run(STAGE.run_id, status, returncode=proc.returncode,
                  ringkasan=ringkasan)
    STAGE.run_id = None


def mulai_stage(label, args, jenis="lain", parameter=None):
    """Jalankan `PY <args...>` sbg subprocess (cwd = root proyek). args = list
    diawali path skrip relatif, mis. ['tools/pelayanan.py','--excel',...]."""
    if STAGE.running:
        return False, "Masih ada proses berjalan. Tunggu selesai atau Hentikan dulu."
    STAGE.running = True
    STAGE.dihentikan = False
    STAGE.label = label
    STAGE.cmd = "python " + " ".join(args)
    STAGE.mulai = datetime.now().isoformat(timespec="seconds")
    STAGE.returncode = None
    STAGE.log.clear()
    STAGE.log.append(f"[MULAI] {label} — {STAGE.mulai}")
    STAGE.log.append(f"[CMD] {STAGE.cmd}")

    STAGE.run_id = db.mulai_run(jenis, label, perintah=STAGE.cmd,
                                parameter=parameter or {})
    try:
        proc = subprocess.Popen(
            [PY] + args, cwd=ROOT,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace", bufsize=1)
    except Exception as e:
        STAGE.running = False
        STAGE.log.append(f"[ERROR] gagal start: {e}")
        db.akhiri_run(STAGE.run_id, "gagal", ringkasan=f"Gagal start: {e}")
        STAGE.run_id = None
        return False, f"Gagal start: {e}"
    STAGE._proc = proc
    threading.Thread(target=_stream, args=(proc,), daemon=True).start()
    return True, f"Dimulai: {label}"


def stop_stage():
    if STAGE._proc and STAGE.running:
        try:
            STAGE.dihentikan = True
            STAGE._proc.terminate()
            STAGE.log.append("[DIHENTIKAN] oleh pengguna.")
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
