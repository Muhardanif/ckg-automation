"""
DIAGNOSTIK penuh picker Alamat Domisili (cascade Provinsi->Kab->Kec->Kelurahan).

Menjalankan Step 1 -> Lanjutkan -> Step 2 (status/disabilitas/pekerjaan), lalu
membuka kontrol 'Alamat Domisili' dan menelusuri cascade: dump header level +
placeholder cari + markup item; ketik 'Jawa Timur' -> pilih -> lihat level
berikutnya. TANPA submit.

PAKAI:  venv\\Scripts\\python.exe tools\\diag_alamat_full.py --excel data/input/template_pendaftaran.xlsx --baris 1
"""
import argparse
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.automation.ckg_bot import CKGBot                  # noqa: E402
from app.automation import selectors as S                  # noqa: E402
from app.schema import KelompokUsia                        # noqa: E402

DUMP_JS = r"""() => {
    const vis = el => { const r=el.getBoundingClientRect(); const s=getComputedStyle(el);
        return r.width>0&&r.height>0&&s.visibility!=='hidden'&&s.display!=='none'; };
    const headers = Array.from(document.querySelectorAll('*')).filter(e =>
        vis(e) && e.children.length<=2 &&
        /(Pilih Lokasi|Daftar (Provinsi|Kabupaten|Kota|Kecamatan|Kelurahan|Desa))/i
          .test((e.textContent||'').trim()) && (e.textContent||'').trim().length<40)
        .map(e=>(e.textContent||'').trim());
    const inputs = Array.from(document.querySelectorAll('input')).filter(vis)
        .map(i=>({ph:i.placeholder}));
    const items = Array.from(document.querySelectorAll("div[class*='cursor-pointer'],li,[role=option]"))
        .filter(vis).map(e=>({tag:e.tagName.toLowerCase(),
            cls:(e.className||'').toString().slice(0,110),
            txt:(e.textContent||'').trim().slice(0,40),
            html:(e.outerHTML||'').slice(0,200)}))
        .filter(o=>o.txt && o.txt.length<40);
    return {headers, inputs:[...new Set(inputs.map(x=>x.ph))], items: items.slice(0,12)};
}"""


def muat(args):
    from app.readers import baca_excel
    ps = baca_excel(args.excel, KelompokUsia(args.kelompok), header_row=args.header_row)
    return ps[args.baris - 1]


async def dump(p, tag):
    info = await p.evaluate(DUMP_JS)
    print(f"\n===== {tag} =====")
    print("  HEADERS:", info["headers"])
    print("  SEARCH ph:", info["inputs"])
    print("  ITEMS:")
    for it in info["items"]:
        print(f"    <{it['tag']}> {it['txt']!r}  cls={it['cls'][:70]!r}")
        if it['txt'] and ('jawa' in it['txt'].lower() or 'gresik' in it['txt'].lower()):
            print("       html=", it['html'])


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--excel", required=True)
    ap.add_argument("--baris", type=int, default=1)
    ap.add_argument("--kelompok", default="dewasa")
    ap.add_argument("--header-row", dest="header_row", type=int, default=0)
    args = ap.parse_args()
    p_data = muat(args)

    bot = CKGBot(headless=False, delay_ms=700)
    page = await bot.connect_to_browser()
    L = S.SATUSEHAT

    if await page.get_by_text(L["ph_jk"], exact=False).count() == 0:
        await bot._klik_tombol(L["btn_daftar_baru"])
        await page.wait_for_load_state("networkidle"); await page.wait_for_timeout(800)

    print("[D] STEP 1")
    await bot._ketik_label(L["label_nik"], p_data.nik, wajib=True)
    await bot._ketik_label(L["label_nama"], p_data.nama, wajib=True)
    await bot._isi_tanggal(L["label_tgl_lahir"], p_data.tgl_lahir, wajib=True)
    await bot._ketik_label(L["label_wa"], p_data.no_wa or p_data.no_hp, wajib=True)
    await bot._centang_tanpa_wali()
    jk = "Laki-laki" if (p_data.jenis_kelamin or "").upper() == "L" else "Perempuan"
    await bot._pilih_dropdown(L["label_jk"], jk, placeholder=L["ph_jk"], wajib=True)
    await bot._pilih_tgl_pemeriksaan(p_data.tanggal_pemeriksaan, wajib=True)
    await bot._klik_tombol(L["btn_selanjutnya"])
    await page.wait_for_load_state("networkidle"); await page.wait_for_timeout(800)

    if await page.get_by_text(L["teks_tidak_valid"], exact=False).count() > 0:
        print("[D] DITOLAK tidak valid"); await bot.stop(); return
    await bot._klik_tombol(L["btn_lanjutkan"], timeout=10000)
    await page.wait_for_load_state("networkidle"); await page.wait_for_timeout(1000)

    print("[D] STEP 2 dropdowns")
    await bot._pilih_dropdown(L["label_status_nikah"], p_data.status_pernikahan)
    await bot._pilih_dropdown(L["label_disabilitas"], p_data.disabilitas)
    await bot._pilih_dropdown(L["label_pekerjaan"], p_data.pekerjaan)

    print("[D] buka kontrol 'Alamat Domisili'")
    ctrl = await bot._kontrol_dropdown("Alamat Domisili", None)
    await ctrl.click(timeout=6000)
    await page.wait_for_timeout(900)
    await dump(page, "LEVEL 1 (setelah buka)")
    await page.screenshot(path="data/output/screenshots/DA_1.png")

    # ketik provinsi
    print("[D] ketik 'Jawa Timur' di kotak cari level-1")
    s = page.get_by_placeholder(__import__("re").compile(r"^\s*Cari", __import__("re").I)).first
    if await s.count() > 0:
        await s.fill("Jawa Timur"); await page.wait_for_timeout(900)
        await dump(page, "LEVEL 1 setelah cari 'Jawa Timur'")
        # klik item Jawa Timur
        opt = page.get_by_text("Jawa Timur", exact=True).locator("visible=true").first
        if await opt.count() > 0:
            await opt.click(); await page.wait_for_timeout(1200)
            await dump(page, "LEVEL 2 (setelah pilih Jawa Timur)")
            await page.screenshot(path="data/output/screenshots/DA_2.png")
        else:
            print("[D] item 'Jawa Timur' tak ketemu")
    else:
        print("[D] tak ada kotak cari di level-1")

    print("[D] selesai (tanpa submit). Screenshots: DA_1.png, DA_2.png")
    await bot.stop()


if __name__ == "__main__":
    asyncio.run(main())
