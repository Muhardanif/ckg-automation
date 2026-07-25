"""
Runner: orkestrasi proses submit batch (berbasis DB).

Mengelola antrian peserta dari SQLite, menjalankan bot, melacak progress,
dan menulis hasil kembali ke DB (persisten). Counter dashboard dihitung dari
DB, sedangkan JobState hanya melacak status job yang sedang berjalan
(running / pesan / waktu mulai).
"""
import asyncio
import threading
from datetime import datetime
from typing import List, Dict, Optional

import openpyxl

from .automation.ckg_bot import CKGBot
from .schema import StatusSubmit
from .readers import validasi
from . import db

LOG_PATH = "data/output/log_submit.xlsx"


class JobState:
    """State job yang sedang berjalan (counter sebenarnya dari DB)."""
    def __init__(self):
        self.running = False
        self.pesan = "Idle"
        self.mulai: str = ""
        # progress job berjalan (untuk pembeda dari total DB historis)
        self.job_total = 0
        self.job_selesai = 0
        self.job_sukses = 0
        self.job_gagal = 0
        self.run_id: Optional[int] = None  # baris audit trail yang sedang terbuka

    def snapshot(self) -> Dict:
        stat = db.hitung_status()
        selesai = stat["sukses"] + stat["gagal"]
        total = stat["total"]
        return {
            "running": self.running,
            "pesan": self.pesan,
            "mulai": self.mulai,
            "total": total,
            "selesai": selesai,
            "sukses": stat["sukses"],
            "gagal": stat["gagal"],
            "belum": stat["belum"],
            "persen": round(selesai / total * 100, 1) if total else 0,
            "job_total": self.job_total,
            "job_selesai": self.job_selesai,
        }


# instance global state
STATE = JobState()


def simpan_log():
    """Ekspor seluruh peserta di DB ke Excel sebagai log/bukti."""
    import os
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    rows = []
    for row in db.semua_peserta():
        d = row.to_dataclass().to_dict()
        pem = d.pop("pemeriksaan", {}) or {}
        for k, v in pem.items():
            d[f"pem_{k}"] = v
        rows.append(d)

    # Kolom = gabungan key semua baris, urut kemunculan pertama (field
    # pem_* berbeda antar kelompok usia, jadi tidak semua baris punya key sama).
    kolom = list(dict.fromkeys(k for d in rows for k in d))
    wb = openpyxl.Workbook(write_only=True)
    ws = wb.create_sheet("Log")
    ws.append(kolom)
    for d in rows:
        ws.append([d.get(k) for k in kolom])
    wb.save(LOG_PATH)


async def _proses_async(ids: List[int], username: str, password: str,
                        headless: bool, delay_ms: int, otp_wait_s: int):
    bot = CKGBot(username, password, headless=headless,
                 delay_ms=delay_ms, otp_wait_s=otp_wait_s)
    await bot.start()
    try:
        STATE.pesan = "Login ke portal..."
        if not await bot.login():
            STATE.pesan = "GAGAL LOGIN - cek kredensial / selector login / OTP"
            db.akhiri_run(STATE.run_id, "gagal",
                          ringkasan="Gagal login ke portal.")
            STATE.run_id = None
            return

        STATE.pesan = "Memproses peserta..."
        with db.SessionLocal() as s:
            for pid in ids:
                row = s.get(db.PesertaRow, pid)
                if row is None:
                    continue

                # tandai proses
                row.status_submit = StatusSubmit.PROSES.value
                row.percobaan = (row.percobaan or 0) + 1
                s.commit()

                p = row.to_dataclass()
                err = validasi(p)
                if err:
                    p.status_submit = StatusSubmit.GAGAL
                    p.keterangan = "Validasi gagal: " + "; ".join(err)
                    p.waktu_submit = datetime.now().isoformat(timespec="seconds")
                else:
                    # cek sesi masih login; bila tidak, coba re-login
                    if not await bot.pastikan_login():
                        STATE.pesan = "Sesi habis & gagal re-login. Job dihentikan."
                        row.status_submit = StatusSubmit.BELUM.value
                        s.commit()
                        break
                    await bot.submit_peserta(p)

                row.update_from_dataclass(p)
                s.commit()

                STATE.job_selesai += 1
                if p.status_submit == StatusSubmit.SUKSES:
                    STATE.job_sukses += 1
                else:
                    STATE.job_gagal += 1

        # Tidak ada ekspor inkremental: DB sudah persisten per peserta, dan
        # /unduh-log meregenerasi Excel dari DB tiap kali diunduh. Ekspor di
        # tengah job hanya menulis ulang seluruh tabel & menahan event loop.
        simpan_log()
        stat = db.hitung_status()
        STATE.pesan = (f"Selesai. Total sukses {stat['sukses']}, "
                       f"gagal {stat['gagal']}, belum {stat['belum']}.")
        db.akhiri_run(
            STATE.run_id,
            "sukses" if STATE.job_gagal == 0 else "gagal",
            ringkasan=(f"{STATE.job_selesai}/{STATE.job_total} peserta diproses; "
                       f"{STATE.job_sukses} sukses, {STATE.job_gagal} gagal."),
            sukses=STATE.job_sukses, gagal=STATE.job_gagal)
        STATE.run_id = None
    finally:
        await bot.stop()
        STATE.running = False
        # Jaring pengaman: bila keluar lewat jalur `break` (sesi habis) atau
        # exception, baris audit belum tertutup dan akan tampak 'berjalan'
        # selamanya di halaman Riwayat.
        db.akhiri_run(STATE.run_id, "gagal",
                      ringkasan=STATE.pesan or "Job berhenti sebelum selesai.",
                      sukses=STATE.job_sukses, gagal=STATE.job_gagal)
        STATE.run_id = None


def _mulai_thread(ids: List[int], username: str, password: str,
                  headless: bool, delay_ms: int, otp_wait_s: int,
                  label: str, parameter: Dict):
    STATE.running = True
    STATE.job_total = len(ids)
    STATE.job_selesai = 0
    STATE.job_sukses = 0
    STATE.job_gagal = 0
    STATE.mulai = datetime.now().isoformat(timespec="seconds")
    STATE.pesan = "Memulai..."
    # Kredensial TIDAK ikut tercatat — hanya parameter non-rahasia.
    STATE.run_id = db.mulai_run("daftar-login", label, parameter=parameter,
                                jumlah_total=len(ids))

    def runner():
        try:
            asyncio.run(_proses_async(
                ids, username, password, headless, delay_ms, otp_wait_s))
        except Exception as e:  # jaga-jaga agar flag running selalu dilepas
            STATE.pesan = f"Job berhenti karena error: {type(e).__name__}: {e}"
            STATE.running = False
            db.akhiri_run(STATE.run_id, "gagal", ringkasan=STATE.pesan,
                          sukses=STATE.job_sukses, gagal=STATE.job_gagal)
            STATE.run_id = None

    threading.Thread(target=runner, daemon=True).start()


def jalankan(username: str, password: str, headless: bool = True,
             delay_ms: int = 800, otp_wait_s: int = 0,
             statuses: Optional[List[str]] = None):
    """
    Mulai job submit untuk peserta dengan status tertentu.

    statuses: daftar status yang diproses. Default = ['belum'] (peserta baru).
              Untuk retry, panggil dengan ['gagal'].
    """
    if STATE.running:
        return False, "Job lain sedang berjalan"

    if statuses is None:
        statuses = [StatusSubmit.BELUM.value]

    ids = db.ambil_id_untuk_proses(statuses)
    if not ids:
        return False, "Tidak ada peserta untuk diproses (cek status data)."

    ulang = statuses == [StatusSubmit.GAGAL.value]
    label = "Ulangi yang Gagal" if ulang else "Pendaftaran (via Login)"
    parameter = {"headless": headless, "delay_ms": delay_ms,
                 "otp_wait_s": otp_wait_s, "status_diproses": statuses}
    _mulai_thread(ids, username, password, headless, delay_ms, otp_wait_s,
                  label, parameter)
    return True, f"Job dimulai untuk {len(ids)} peserta"
