"""
INVESTIGASI logika kondisional SurveyJS: form yg memunculkan pertanyaan baru
setelah dijawab. Untuk tiap form target: buka -> dump pertanyaan AWAL -> isi
jawaban default (dry, tanpa Kirim) -> dump pertanyaan SETELAH -> laporkan sq baru.

PAKAI (Chrome 9222 + login, SUMIATI 'Sedang Pemeriksaan'):
  venv\\Scripts\\python.exe tools\\diag_kondisional.py --nik 3525084710630003 --tab "Sedang Pemeriksaan" \
     --forms "Perilaku Merokok,Penapisan Risiko Kanker Paru,Tingkat Aktivitas Fisik"
"""
import argparse
import asyncio
import io
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.automation.ckg_bot import CKGBot          # noqa: E402
from app.automation import selectors as S          # noqa: E402

import diag_pelayanan as dp                         # noqa: E402
import pelayanan as pl                              # noqa: E402


async def _snapshot(page):
    """{sq:int -> {'judul','tipe','opsi'[]}} dari pertanyaan yg TERLIHAT sekarang."""
    form = await page.evaluate(dp.JS_DUMP_FORM)
    qt = await page.evaluate(dp.JS_QTITLE)
    import re
    qs = {}
    for i in form["inputs"]:
        if i["type"] == "button":
            continue
        m = re.search(r"sq_(\d+)i(?:_(\d+))?", i["id"])
        if not m:
            continue
        sq = int(m.group(1))
        q = qs.setdefault(sq, {"tipe": None, "opsi": []})
        if i["type"] == "radio":
            q["tipe"] = "radio"
            q["opsi"].append(i["label"])
        elif i["type"] == "number":
            q["tipe"] = "number"
        elif i["type"] == "text":
            q["tipe"] = "dropdown"
    for sq, q in qs.items():
        q["judul"] = qt.get(str(sq), "")
    return qs


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--nik", required=True)
    ap.add_argument("--tab", default="Sedang Pemeriksaan")
    ap.add_argument("--aksi", default="Mulai")
    ap.add_argument("--excel", default="data/input/template_pendaftaran.xlsx")
    ap.add_argument("--kelompok", default="lansia")
    ap.add_argument("--forms", required=True)
    ap.add_argument("--cdp", default=S.CDP_URL)
    args = ap.parse_args()

    forms_cfg = {f["nama"]: f for f in pl.baca_config(pl.PEMETAAN)}
    # nama peserta dari excel
    from app.readers import baca_excel
    from app.schema import KelompokUsia
    ps = baca_excel(args.excel, KelompokUsia(args.kelompok))
    p = next((x for x in ps if (x.nik or "") == args.nik), None)
    nama = p.nama if p else None
    pvals = pl._peserta_values(p) if p else {}

    bot = CKGBot(headless=False, cdp_url=args.cdp)
    await bot.connect_to_browser()
    page = bot._page
    fh = io.StringIO()

    if not (page.url or "").rstrip("/").endswith("/ckg-pelayanan"):
        await page.goto(dp.URL_PELAYANAN)
        await page.wait_for_timeout(1500)
    await dp._pilih_tab(page, fh, args.tab)
    await dp._set_dropdown_filter(page, fh, "Nama")
    await dp._cari(page, fh, nama)
    if not await dp._klik_mulai(page, fh, nama, aksi=args.aksi):
        print("Gagal buka detail.")
        return
    detail_url = page.url

    daftar = list(forms_cfg) if args.forms.strip().upper() == "ALL" \
        else [s.strip() for s in args.forms.split(",") if s.strip()]
    for nm in daftar:
        form = next((forms_cfg[k] for k in forms_cfg if nm.lower() in k.lower()), None)
        print("\n" + "=" * 70)
        print("FORM:", nm)
        if not await dp._buka_form(page, fh, nm):
            print("  tak bisa buka.")
            continue
        before = await _snapshot(page)
        print("  AWAL sq:", sorted(before))
        if form:
            await pl.isi_satu_form(page, form, pvals, dry=True, log=lambda *a, **k: None)
        await page.wait_for_timeout(800)
        after = await _snapshot(page)
        baru = sorted(set(after) - set(before))
        print("  SETELAH sq:", sorted(after))
        print("  >>> sq BARU (kondisional):", baru)
        for sq in baru:
            q = after[sq]
            print(f"      sq_{sq} [{q['tipe']}] {q['judul'][:70]!r} opsi={q['opsi']}")
        await page.goto(detail_url)
        await page.wait_for_timeout(1500)

    await bot.stop()


if __name__ == "__main__":
    asyncio.run(main())
