"""
DIAGNOSTIK kelengkapan form Step 1 -> kenapa 'Selanjutnya' masih disabled.

Melaporkan: nilai tiap <input>, status checkbox (tanpa data wali / tidak punya
NIK), teks sel tanggal terpilih di kalender Tanggal Pemeriksaan, dan teks
validasi/error yang terlihat.

PAKAI:  venv\\Scripts\\python.exe tools\\diag_form.py
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
    page = next((x for x in c.pages if S.URL_CKG_BERISI in (x.url or "")), c.pages[0])
    await page.bring_to_front()
    print(f"[DIAG] Tab: {page.url}")

    data = await page.evaluate("""() => {
        const inputs = Array.from(document.querySelectorAll('input')).map(i => ({
            id: i.id, name: i.name, type: i.type,
            value: i.value, checked: i.checked,
            placeholder: i.placeholder
        }));
        // sel kalender yang tampak terpilih (cari class warna/selected pada button hari)
        const dayBtns = Array.from(document.querySelectorAll('button')).filter(b => /^\\d{1,2}$/.test((b.textContent||'').trim()));
        const selectedDays = dayBtns.filter(b => {
            const cls = (b.className||'');
            const st = getComputedStyle(b);
            return /selected|active|bg-\\[#|bg-primary|text-white/i.test(cls);
        }).map(b => ({text:(b.textContent||'').trim(), cls:(b.className||'').slice(0,160)}));
        // teks validasi/error merah
        const errs = Array.from(document.querySelectorAll('*')).filter(el => {
            const cls=(el.className||'').toString();
            const t=(el.textContent||'').trim();
            return t && t.length<120 && el.children.length===0 && /text-error|text-red|text-danger/i.test(cls);
        }).map(el => (el.textContent||'').trim());
        return {inputs, selectedDays, errs};
    }""")

    print("[DIAG] INPUTS:")
    for i in data["inputs"]:
        print(f"   id={i['id']!r} name={i['name']!r} type={i['type']!r} "
              f"checked={i['checked']} value={i['value']!r} ph={i['placeholder']!r}")
    print("[DIAG] Hari kalender tampak TERPILIH:")
    for d in data["selectedDays"]:
        print(f"   {d['text']}  class={d['cls']!r}")
    if not data["selectedDays"]:
        print("   (tidak ada hari yang tampak terpilih)")
    print("[DIAG] Teks validasi/error (text-error/red):")
    for e in data["errs"]:
        print(f"   - {e!r}")
    if not data["errs"]:
        print("   (tidak ada)")
    await pw.stop()


if __name__ == "__main__":
    asyncio.run(main())
