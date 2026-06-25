"""
DIAGNOSTIK dropdown "Jenis Kelamin" (Vue + Tailwind) portal SATUSEHAT.

Self-contained: menempel ke Chrome (CDP) di halaman "Cari/Daftarkan Individu",
membuka modal "Daftar Baru" sendiri, lalu memeriksa kontrol Jenis Kelamin:
  1. ambil HTML wrapper komponen (untuk tahu cara buka dropdown)
  2. pasang MutationObserver -> klik kontrol -> laporkan node yang BARU muncul

Tidak men-submit data apa pun (hanya membuka modal & klik dropdown).

PAKAI:
   venv\\Scripts\\python.exe tools\\diag_dropdown.py
"""
import argparse
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from playwright.async_api import async_playwright          # noqa: E402
from app.automation import selectors as S                  # noqa: E402


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--placeholder", default=S.SATUSEHAT["ph_jk"])
    ap.add_argument("--cdp", default=S.CDP_URL)
    args = ap.parse_args()

    pw = await async_playwright().start()
    browser = await pw.chromium.connect_over_cdp(args.cdp)
    ctx = browser.contexts[0]
    page = None
    for pg in ctx.pages:
        if S.URL_CKG_BERISI in (pg.url or ""):
            page = pg
            break
    page = page or ctx.pages[0]
    await page.bring_to_front()
    print(f"[DIAG] Tab: {page.url}")

    # 0) buka modal "Daftar Baru" bila placeholder belum ada
    if await page.get_by_text(args.placeholder, exact=False).count() == 0:
        print("[DIAG] Membuka modal 'Daftar Baru'...")
        await page.get_by_role("button", name="Daftar Baru").first.click()
        await page.wait_for_timeout(1200)

    ctrls = page.get_by_text(args.placeholder, exact=False)
    n = await ctrls.count()
    print(f"[DIAG] jumlah kontrol '{args.placeholder}': {n}")
    if n == 0:
        print("[DIAG] Kontrol gender tak ada. Pastikan modal terbuka di Step 1.")
        await pw.stop()
        return

    # 1) HTML wrapper komponen gender pertama (naik 5 level)
    target = ctrls.first
    try:
        wrap = await target.evaluate(
            "el => { let w = el; for (let i=0;i<5 && w.parentElement;i++) w = w.parentElement; "
            "return w.outerHTML.slice(0, 3000); }")
        print("[DIAG] WRAPPER komponen Jenis Kelamin (5 level di atas teks):")
        print(" ".join(wrap.split()))
    except Exception as e:
        print(f"[DIAG] gagal ambil wrapper: {type(e).__name__}: {e}")

    # 2) observer -> klik -> node baru
    await page.evaluate("""
      () => {
        window.__newNodes = [];
        window.__obs = new MutationObserver(muts => {
          for (const m of muts) for (const nd of m.addedNodes) {
            if (nd.nodeType === 1) window.__newNodes.push({
              tag: nd.tagName.toLowerCase(),
              cls: (nd.className||'').toString().slice(0,180),
              text: (nd.textContent||'').trim().slice(0,140),
              html: (nd.outerHTML||'').slice(0,800)
            });
          }
        });
        window.__obs.observe(document.body, {childList:true, subtree:true});
      }
    """)

    print("[DIAG] Meng-klik kontrol gender (div cursor-pointer terdekat)...")
    clickable = target.locator(
        "xpath=ancestor-or-self::*[contains(@class,'cursor-pointer')][1]")
    if await clickable.count() == 0:
        clickable = target
    await clickable.first.scroll_into_view_if_needed()
    await clickable.first.click()
    await page.wait_for_timeout(900)

    new_nodes = await page.evaluate(
        "() => { window.__obs.disconnect(); return window.__newNodes; }")
    print(f"[DIAG] Node BARU setelah klik: {len(new_nodes)}")
    print("-" * 70)
    for nd in new_nodes:
        print(f"  <{nd['tag']}> text={nd['text']!r}")
        print(f"      class={nd['cls']!r}")
        low = nd['text'].lower()
        if 'laki' in low or 'perempuan' in low or 'pilih' in low:
            print(f"      HTML={nd['html']}")
    print("-" * 70)
    if not new_nodes:
        print("[DIAG] TIDAK ada node baru -> klik tak membuka dropdown.")

    await pw.stop()


if __name__ == "__main__":
    asyncio.run(main())
