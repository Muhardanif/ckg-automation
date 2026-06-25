"""
EKSPERIMEN: cari cara meng-ENABLE 'Selanjutnya' di Step 1.
  - target A: centang checkbox 'Daftarkan tanpa data wali' (#noWali)
  - target B: pilih Tanggal Pemeriksaan hari ini di kalender

Mencoba beberapa strategi klik dan melaporkan is_checked + status disabled
'Selanjutnya' setelah tiap aksi. TIDAK men-submit.

PAKAI:  venv\\Scripts\\python.exe tools\\diag_step1_fix.py
"""
import asyncio
import os
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from playwright.async_api import async_playwright          # noqa: E402
from app.automation import selectors as S                  # noqa: E402


async def selanjutnya_disabled(page):
    return await page.evaluate("""() => {
        const els = Array.from(document.querySelectorAll('div')).filter(
            d => (d.textContent||'').trim() === 'Selanjutnya' &&
                 /cursor-not-allowed|bg-disabled/i.test(d.className||''));
        return els.length > 0;  // true bila masih ada div Selanjutnya yg disabled
    }""")


async def main():
    pw = await async_playwright().start()
    b = await pw.chromium.connect_over_cdp(S.CDP_URL)
    c = b.contexts[0]
    page = next((x for x in c.pages if S.URL_CKG_BERISI in (x.url or "")), c.pages[0])
    await page.bring_to_front()
    print(f"[DIAG] disabled awal? {await selanjutnya_disabled(page)}")

    # ---- A. checkbox 'Daftarkan tanpa data wali' ----
    cb = page.locator("input[name='noWali']")
    print(f"[A] #noWali ada? {await cb.count()}  checked={await cb.is_checked() if await cb.count() else 'n/a'}")
    # dump struktur sekitar
    if await cb.count() > 0:
        html = await cb.evaluate(
            "el => { let w=el; for(let i=0;i<3&&w.parentElement;i++) w=w.parentElement; "
            "return w.outerHTML.slice(0,700); }")
        print("[A] wrapper:", " ".join(html.split()))

    async def cek_centang(label):
        st = await cb.is_checked() if await cb.count() else None
        print(f"[A] setelah {label}: noWali checked={st} | Selanjutnya disabled={await selanjutnya_disabled(page)}")
        return st

    # strategi 1: check(force) langsung pada input
    try:
        await cb.check(force=True, timeout=3000)
    except Exception as e:
        print(f"[A] check(force) error: {type(e).__name__}")
    if not await cek_centang("check(force)"):
        # strategi 2: klik styled overlay '.check' sibling
        try:
            overlay = cb.locator("xpath=following-sibling::*[contains(@class,'check')][1]")
            if await overlay.count() == 0:
                overlay = cb.locator("xpath=..").locator("div.check")
            await overlay.first.click(timeout=3000)
        except Exception as e:
            print(f"[A] klik overlay error: {type(e).__name__}")
        if not await cek_centang("klik overlay .check"):
            # strategi 3: klik label teks
            try:
                await page.get_by_text("Daftarkan tanpa data wali", exact=False).first.click(timeout=3000)
            except Exception as e:
                print(f"[A] klik label error: {type(e).__name__}")
            await cek_centang("klik label teks")

    # ---- B. Tanggal Pemeriksaan: pilih hari ini ----
    today = date.today().day
    print(f"[B] hari ini = {today}")
    # tombol hari: <button> yang teks-nya diawali angka hari & TIDAK cursor-not-allowed
    btn = page.locator("button").filter(
        has_text=__import__("re").compile(rf"^\s*{today}(\D|$)"))
    # lebih spesifik: cari via evaluate untuk hindari salah angka
    clicked = await page.evaluate("""(hari) => {
        const btns = Array.from(document.querySelectorAll('button'));
        for (const b of btns) {
            const t = (b.textContent||'').trim();
            // hari kalender: diawali angka 'hari', kelas kalender (border rounded), enabled
            if (new RegExp('^'+hari+'(\\\\D|$)').test(t) &&
                /border/.test(b.className||'') &&
                !/cursor-not-allowed/.test(b.className||'')) {
                const r=b.getBoundingClientRect();
                b.scrollIntoView({block:'center'});
                return {found:true, text:t, cls:(b.className||'').slice(0,160), rect:[Math.round(r.x),Math.round(r.y)]};
            }
        }
        return {found:false};
    }""", today)
    print(f"[B] kandidat tombol hari ini: {clicked}")
    if clicked.get("found"):
        try:
            # klik via koordinat tengah tombol yang cocok
            await page.evaluate("""(hari) => {
                const btns = Array.from(document.querySelectorAll('button'));
                for (const b of btns) {
                    const t=(b.textContent||'').trim();
                    if (new RegExp('^'+hari+'(\\\\D|$)').test(t) &&
                        /border/.test(b.className||'') && !/cursor-not-allowed/.test(b.className||'')) {
                        b.click(); return;
                    }
                }
            }""", today)
            await page.wait_for_timeout(600)
            print(f"[B] setelah klik tanggal: Selanjutnya disabled={await selanjutnya_disabled(page)}")
        except Exception as e:
            print(f"[B] klik tanggal error: {type(e).__name__}: {e}")

    print(f"[DIAG] disabled akhir? {await selanjutnya_disabled(page)}")
    await page.screenshot(path="data/output/screenshots/DIAG_step1_after.png")
    print("[DIAG] screenshot: data/output/screenshots/DIAG_step1_after.png")
    await pw.stop()


if __name__ == "__main__":
    asyncio.run(main())
