"""
PROBE kotak cari NIK di listing Pelayanan (CDP) — diagnosis error
'NIK hanya bisa angka'.

Menyambung ke Chrome (port 9222) yang SUDAH login & terbuka di portal, lalu:
  1) buka /ckg-pelayanan, set filter dropdown -> NIK,
  2) dump SEMUA input teks yang terlihat (placeholder/value/atribut/outerHTML),
  3) coba isi NIK uji (default: fill; --type utk ketik per-karakter), lalu
  4) dump value akhir + SEMUA elemen yang memuat teks 'angka'/'hanya' (pesan error).

TIDAK menekan tombol aksi apa pun (tak mengubah data). Hanya mengisi kotak cari.

PAKAI:
  venv\\Scripts\\python.exe tools\\diag_nik_box.py --nik 3525084710630003
  # --type : ketik per-karakter (delay) alih-alih fill sekaligus
"""
import argparse
import asyncio
import io
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.automation.ckg_bot import CKGBot          # noqa: E402
from app.automation import selectors as S          # noqa: E402
import diag_pelayanan as dp                         # noqa: E402

URL = dp.URL_PELAYANAN

# JS: dump semua <input> terlihat + atribut relevan + outerHTML singkat.
JS_DUMP_INPUTS = r"""() => {
  const vis = (e) => { const r = e.getBoundingClientRect(); return r.width>0 && r.height>0; };
  return Array.from(document.querySelectorAll('input,textarea')).filter(vis).map(e => ({
    tag: e.tagName.toLowerCase(),
    type: e.getAttribute('type'),
    placeholder: e.getAttribute('placeholder'),
    value: e.value,
    inputmode: e.getAttribute('inputmode'),
    pattern: e.getAttribute('pattern'),
    maxlength: e.getAttribute('maxlength'),
    name: e.getAttribute('name'),
    cls: (e.getAttribute('class')||'').slice(0,80),
    html: (e.outerHTML||'').slice(0,300),
  }));
}"""

# JS: semua elemen yang memuat teks pesan error (angka/hanya/valid/NIK ...).
JS_DUMP_ERR = r"""() => {
  const txt = (e) => (e.textContent||'').replace(/\s+/g,' ').trim();
  const vis = (e) => { const r = e.getBoundingClientRect(); return r.width>0 && r.height>0; };
  const out = [];
  document.querySelectorAll('*').forEach(e => {
    const t = txt(e);
    if (!t || t.length > 80) return;
    if (!/angka|hanya bisa|harus|valid|digit/i.test(t)) return;
    if (e.children.length > 0) return;   // hanya leaf (hindari duplikat induk)
    if (!vis(e)) return;
    out.push({text: t, cls: (e.getAttribute('class')||'').slice(0,80),
              html: (e.outerHTML||'').slice(0,200)});
  });
  return out;
}"""


def show(judul, items):
    print(f"\n===== {judul} ({len(items)}) =====", flush=True)
    for i, it in enumerate(items):
        print(f"[{i}] {it}", flush=True)


async def jalankan(args):
    bot = CKGBot(headless=False, delay_ms=300, cdp_url=args.cdp)
    await bot.connect_to_browser()
    page = bot._page
    fh = io.StringIO()

    if not (page.url or "").rstrip("/").endswith("/ckg-pelayanan"):
        await page.goto(URL)
        try:
            await page.wait_for_load_state("networkidle", timeout=10000)
        except Exception:
            pass
    await page.wait_for_timeout(3000)

    print("URL:", page.url, flush=True)
    # 1) set filter -> NIK
    hasil = await dp._set_dropdown_filter(page, fh, "NIK")
    print("set_dropdown_filter -> NIK :", hasil, flush=True)
    print(fh.getvalue(), flush=True)
    await page.wait_for_timeout(3000)

    # 2) dump input SEBELUM diisi
    inputs = await page.evaluate(JS_DUMP_INPUTS)
    show("INPUT terlihat (sebelum isi)", inputs)

    # 3) isi NIK uji
    box = page.get_by_placeholder(re.compile(r"Masukkan|cari|nik|nama", re.I)).first
    if await box.count() == 0:
        box = page.get_by_role("textbox").last
    print("\n>> mengisi NIK:", repr(args.nik), "mode:", "type" if args.type else "fill", flush=True)
    try:
        await box.click(timeout=6000)
        await box.fill("", timeout=3000)
        if args.type:
            await box.type(str(args.nik), delay=120)
        else:
            await box.fill(str(args.nik), timeout=6000)
        await page.wait_for_timeout(800)
    except Exception as e:
        print("  gagal isi:", type(e).__name__, str(e)[:120], flush=True)

    # 4) dump value akhir + pesan error
    try:
        val = await box.input_value(timeout=2000)
    except Exception:
        val = "(?)"
    print(">> value kotak setelah diisi:", repr(val), flush=True)
    await page.wait_for_timeout(400)
    show("INPUT terlihat (setelah isi)", await page.evaluate(JS_DUMP_INPUTS))
    show("PESAN ERROR/teks validasi", await page.evaluate(JS_DUMP_ERR))

    await bot.stop()
    return 0


def main():
    ap = argparse.ArgumentParser(description="Probe kotak cari NIK listing Pelayanan.")
    ap.add_argument("--nik", default="3525084710630003")
    ap.add_argument("--type", action="store_true", help="ketik per-karakter (delay) bukan fill.")
    ap.add_argument("--cdp", default=S.CDP_URL)
    args = ap.parse_args()
    sys.exit(asyncio.run(jalankan(args)))


if __name__ == "__main__":
    main()
