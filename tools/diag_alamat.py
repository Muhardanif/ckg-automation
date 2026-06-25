"""
DIAGNOSTIK picker Alamat Domisili (cascade lokasi) di Step 2.

Membuka/menelaah overlay 'Pilih Lokasi': header level (Daftar Provinsi/Kab/Kec/
Kelurahan), placeholder kotak cari, dan beberapa item daftar + markup-nya.

PAKAI:  venv\\Scripts\\python.exe tools\\diag_alamat.py
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from playwright.async_api import async_playwright          # noqa: E402
from app.automation import selectors as S                  # noqa: E402


async def main():
    pw = await async_playwright().start()
    b = await pw.chromium.connect_over_cdp(S.CDP_URL)
    c = b.contexts[0]
    p = next((x for x in c.pages if S.URL_CKG_BERISI in (x.url or "")), c.pages[0])
    await p.bring_to_front()

    # buka picker bila belum: klik kontrol 'Alamat Domisili'
    if await p.get_by_placeholder("__x__").count() == 0:
        pass
    ctrl = p.get_by_text("Alamat Domisili", exact=False)
    print("[DIAG] label 'Alamat Domisili' count:", await ctrl.count())

    info = await p.evaluate("""() => {
        const vis = el => { const r=el.getBoundingClientRect(); const s=getComputedStyle(el);
            return r.width>0&&r.height>0&&s.visibility!=='hidden'&&s.display!=='none'; };
        // header level: teks mengandung 'Daftar ' / 'Pilih Lokasi'
        const headers = Array.from(document.querySelectorAll('*')).filter(e =>
            vis(e) && e.children.length<=2 &&
            /^(Pilih Lokasi|Daftar (Provinsi|Kabupaten|Kota|Kecamatan|Kelurahan|Desa).*)$/i
              .test((e.textContent||'').trim())).map(e=>(e.textContent||'').trim());
        // semua input cari yang terlihat
        const inputs = Array.from(document.querySelectorAll('input')).filter(vis)
            .map(i=>({ph:i.placeholder, id:i.id, name:i.name, val:i.value}));
        // item daftar lokasi: elemen daun ber-cursor-pointer di overlay
        const items = Array.from(document.querySelectorAll("div[class*='cursor-pointer'],li,[role=option]"))
            .filter(vis).map(e=>({tag:e.tagName.toLowerCase(),
                cls:(e.className||'').toString().slice(0,120),
                txt:(e.textContent||'').trim().slice(0,50)}))
            .filter(o=>o.txt && o.txt.length<50);
        return {headers, inputs, items: items.slice(0,14)};
    }""")
    print("[DIAG] HEADERS level:", info["headers"])
    print("[DIAG] INPUTS terlihat:")
    for i in info["inputs"]:
        print("   ", i)
    print("[DIAG] ITEM daftar (sampel):")
    for it in info["items"]:
        print(f"    <{it['tag']}> txt={it['txt']!r} cls={it['cls'][:80]!r}")
    await p.screenshot(path="data/output/screenshots/DIAG_alamat.png")
    print("[DIAG] screenshot: data/output/screenshots/DIAG_alamat.png")
    await pw.stop()


if __name__ == "__main__":
    asyncio.run(main())
