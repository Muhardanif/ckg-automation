"""
DIAGNOSTIK tombol berdasarkan teks (mis. 'Selanjutnya', 'Daftar Baru').

Melaporkan SEMUA elemen yang teksnya == nama tombol: tag, class, apakah
<button>/<div>, disabled?, visible?, dan apakah ber-class disabled/cursor-not-allowed.

PAKAI:  venv\\Scripts\\python.exe tools\\diag_tombol.py "Selanjutnya"
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from playwright.async_api import async_playwright          # noqa: E402
from app.automation import selectors as S                  # noqa: E402

NAMA = sys.argv[1] if len(sys.argv) > 1 else "Selanjutnya"


async def main():
    pw = await async_playwright().start()
    b = await pw.chromium.connect_over_cdp(S.CDP_URL)
    c = b.contexts[0]
    page = next((x for x in c.pages if S.URL_CKG_BERISI in (x.url or "")), c.pages[0])
    await page.bring_to_front()
    print(f"[DIAG] Tab: {page.url}")

    info = await page.evaluate(
        """(nama) => {
            const out = [];
            const all = Array.from(document.querySelectorAll('*'));
            for (const el of all) {
                // hanya elemen yang teks LANGSUNG-nya == nama (leaf-ish)
                const t = (el.textContent || '').trim();
                if (t !== nama) continue;
                // lewati container besar: hanya ambil yang anak elemennya sedikit
                const r = el.getBoundingClientRect();
                const st = getComputedStyle(el);
                const cls = (el.className || '').toString();
                out.push({
                    tag: el.tagName.toLowerCase(),
                    cls: cls.slice(0, 200),
                    disabledAttr: el.disabled === true,
                    ariaDisabled: el.getAttribute('aria-disabled'),
                    pointerEvents: st.pointerEvents,
                    cursor: st.cursor,
                    visible: r.width > 0 && r.height > 0 && st.visibility !== 'hidden' && st.display !== 'none',
                    rect: [Math.round(r.x), Math.round(r.y), Math.round(r.width), Math.round(r.height)],
                    looksDisabled: /disabled|cursor-not-allowed/i.test(cls),
                    outer: el.outerHTML.slice(0, 300)
                });
            }
            return out;
        }""", NAMA)

    print(f"[DIAG] Elemen ber-teks '{NAMA}': {len(info)}")
    print("-" * 70)
    for it in info:
        print(f"  <{it['tag']}> visible={it['visible']} looksDisabled={it['looksDisabled']} "
              f"disabledAttr={it['disabledAttr']} aria-disabled={it['ariaDisabled']!r} "
              f"cursor={it['cursor']!r} pe={it['pointerEvents']!r} rect={it['rect']}")
        print(f"      class={it['cls']!r}")
        print(f"      html={it['outer']}")
    print("-" * 70)
    await pw.stop()


if __name__ == "__main__":
    asyncio.run(main())
