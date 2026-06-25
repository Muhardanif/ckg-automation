"""
VERIFIKASI alur sampai HALAMAN KONFIRMASI (TANPA submit final).

Step 1 -> popup 'Lanjutkan' -> Step 2 (data pendukung) -> 'Selanjutnya' Step 2
-> BERHENTI di halaman konfirmasi. Meng-screenshot & men-dump tombol yang ada
(mis. 'Daftarkan dengan NIK' / 'Daftarkan tanpa NIK') supaya langkah submit
final bisa dipastikan benar SEBELUM membuat pendaftaran nyata.

PAKAI:
   venv\\Scripts\\python.exe tools\\verify_full.py --excel data/input/template_pendaftaran.xlsx --baris 1
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
    print(f"[V] {p.nik} | {p.nama} | {p.tgl_lahir} | JK={p.jenis_kelamin} | "
          f"Nikah={p.status_pernikahan} | Disab={p.disabilitas} | Kerja={p.pekerjaan}")

    bot = CKGBot(headless=False, delay_ms=800)
    page = await bot.connect_to_browser()
    L = S.SATUSEHAT

    if await page.get_by_text(L["ph_jk"], exact=False).count() == 0:
        print("[V] buka 'Daftar Baru'")
        await bot._klik_tombol(L["btn_daftar_baru"])
        await page.wait_for_load_state("networkidle"); await page.wait_for_timeout(800)

    # --- STEP 1 ---
    print("[V] STEP 1")
    await bot._ketik_label(L["label_nik"], p.nik, wajib=True)
    await bot._ketik_label(L["label_nama"], p.nama, wajib=True)
    await bot._isi_tanggal(L["label_tgl_lahir"], p.tgl_lahir, wajib=True)
    await bot._ketik_label(L["label_wa"], p.no_wa or p.no_hp, wajib=True)
    await bot._centang_tanpa_wali()
    jk = "Laki-laki" if (p.jenis_kelamin or "").upper() == "L" else "Perempuan"
    await bot._pilih_dropdown(L["label_jk"], jk, placeholder=L["ph_jk"], wajib=True)
    await bot._pilih_tgl_pemeriksaan(p.tanggal_pemeriksaan, wajib=True)
    await bot._klik_tombol(L["btn_selanjutnya"])
    await page.wait_for_load_state("networkidle"); await page.wait_for_timeout(800)

    # --- POPUP validasi ---
    if await page.get_by_text(L["teks_tidak_valid"], exact=False).count() > 0:
        print("[V] DITOLAK: Data peserta tidak valid"); await bot.stop(); return
    print("[V] popup 'Data peserta valid' -> klik Lanjutkan")
    try:
        await bot._klik_tombol(L["btn_lanjutkan"], timeout=10000)
        await page.wait_for_load_state("networkidle"); await page.wait_for_timeout(1000)
    except Exception as e:
        print(f"[V] Lanjutkan tidak ada ({type(e).__name__})")

    # --- STEP 2 ---
    print("[V] STEP 2 (data pendukung)")
    await page.screenshot(path="data/output/screenshots/VF_step2.png")
    await bot._pilih_dropdown(L["label_status_nikah"], p.status_pernikahan)
    await bot._pilih_dropdown(L["label_disabilitas"], p.disabilitas)
    await bot._pilih_dropdown(L["label_pekerjaan"], p.pekerjaan)
    print(f"[V] Alamat: {p.provinsi} / {p.kabupaten_kota} / {p.kecamatan} / {p.kelurahan}")
    await bot._isi_alamat_domisili(p, wajib=True)
    await bot._ketik_label(L["label_detail_alamat"], p.detail_alamat, wajib=False)
    await page.screenshot(path="data/output/screenshots/VF_step2_filled.png")
    print("[V] klik 'Selanjutnya' (Step 2)")
    await bot._klik_tombol(L["btn_selanjutnya"])
    await page.wait_for_load_state("networkidle"); await page.wait_for_timeout(1200)

    # --- KONFIRMASI (BERHENTI, tidak submit) ---
    await page.screenshot(path="data/output/screenshots/VF_konfirmasi.png")
    btns = await page.evaluate("""() => {
        const out = new Set();
        for (const b of document.querySelectorAll('button')) {
            const t=(b.textContent||'').trim();
            if (t && t.length<40) out.add(t);
        }
        // div tombol-tombolan
        for (const d of document.querySelectorAll("div[class*='cursor-pointer'],div[class*='btn']")) {
            const t=(d.textContent||'').trim();
            if (t && t.length<40 && /daftar/i.test(t)) out.add('[div] '+t);
        }
        return Array.from(out);
    }""")
    print("[V] Tombol terlihat di halaman konfirmasi:")
    for b in btns:
        print("    -", b)
    print("[V] BERHENTI sebelum submit. Cek VF_konfirmasi.png")
    await bot.stop()


if __name__ == "__main__":
    asyncio.run(main())
