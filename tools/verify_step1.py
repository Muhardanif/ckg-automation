"""
VERIFIKASI Step 1 end-to-end (TANPA submit / TANPA membuat pendaftaran).

Membuka modal 'Daftar Baru' baru, menjalankan seluruh urutan Step 1 memakai
method CKGBot (NIK, Nama, Tgl Lahir, WA, tanpa-wali, Jenis Kelamin, Tanggal
Pemeriksaan), lalu klik 'Selanjutnya' dan memeriksa apakah sudah sampai Step 2.
BERHENTI di Step 2 (tidak klik 'Daftarkan tanpa NIK').

PAKAI:
   venv\\Scripts\\python.exe tools\\verify_step1.py --excel data\\input\\template_pendaftaran.xlsx --baris 1
"""
import argparse
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.automation.ckg_bot import CKGBot                  # noqa: E402
from app.automation import selectors as S                  # noqa: E402
from app.schema import KelompokUsia                        # noqa: E402


def muat(args):
    from app.readers import baca_excel
    ps = baca_excel(args.excel, KelompokUsia(args.kelompok), header_row=args.header_row)
    return ps[args.baris - 1]


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--excel", required=True)
    ap.add_argument("--baris", type=int, default=1)
    ap.add_argument("--kelompok", default="dewasa")
    ap.add_argument("--header-row", dest="header_row", type=int, default=0)
    args = ap.parse_args()

    p = muat(args)
    print(f"[V] Peserta: {p.nik} | {p.nama} | {p.tgl_lahir} | JK={p.jenis_kelamin}")

    bot = CKGBot(headless=False, delay_ms=800)
    page = await bot.connect_to_browser()
    L = S.SATUSEHAT

    # modal fresh
    if await page.get_by_text(L["ph_jk"], exact=False).count() == 0:
        print("[V] buka 'Daftar Baru'")
        await bot._klik_tombol(L["btn_daftar_baru"])
        await page.wait_for_load_state("networkidle")
        await page.wait_for_timeout(800)

    print("[V] isi NIK / Nama / Tgl Lahir / WA")
    await bot._ketik_label(L["label_nik"], p.nik, wajib=True)
    await bot._ketik_label(L["label_nama"], p.nama, wajib=True)
    await bot._isi_tanggal(L["label_tgl_lahir"], p.tgl_lahir, wajib=True)
    await bot._ketik_label(L["label_wa"], p.no_wa or p.no_hp, wajib=True)

    print("[V] centang tanpa-wali")
    await bot._centang_tanpa_wali()

    print("[V] pilih Jenis Kelamin")
    jk = "Laki-laki" if (p.jenis_kelamin or "").upper() == "L" else "Perempuan"
    await bot._pilih_dropdown(L["label_jk"], jk, placeholder=L["ph_jk"], wajib=True)

    print("[V] pilih Tanggal Pemeriksaan")
    await bot._pilih_tgl_pemeriksaan(p.tanggal_pemeriksaan, wajib=True)

    print("[V] klik 'Selanjutnya'")
    await bot._klik_tombol(L["btn_selanjutnya"])
    await page.wait_for_load_state("networkidle")
    await page.wait_for_timeout(1200)

    s2 = await page.get_by_text("Status Pernikahan", exact=False).count()
    s2b = await page.get_by_text("Pekerjaan", exact=False).count()
    os.makedirs("data/output/screenshots", exist_ok=True)
    await page.screenshot(path="data/output/screenshots/VERIFY_step2.png")
    print(f"[V] Step 2 indikator -> Status Pernikahan={s2} Pekerjaan={s2b}")
    if s2 or s2b:
        print("[V] SUKSES: Step 1 selesai & sudah di Step 2. (BERHENTI, tidak submit)")
    else:
        print("[V] PERHATIAN: belum terlihat indikator Step 2. Cek VERIFY_step2.png")
    print("[V] screenshot: data/output/screenshots/VERIFY_step2.png")
    await bot.stop()


if __name__ == "__main__":
    asyncio.run(main())
