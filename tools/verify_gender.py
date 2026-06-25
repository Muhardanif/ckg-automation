"""
VERIFIKASI perbaikan dropdown 'Jenis Kelamin' memakai method bot sungguhan.

Membuka modal 'Daftar Baru' (bila belum), memanggil CKGBot._pilih_dropdown utk
gender, lalu membaca kembali teks kontrol untuk memastikan nilai ter-commit.
TIDAK men-submit / membuat pendaftaran.

PAKAI:  venv\\Scripts\\python.exe tools\\verify_gender.py [Laki-laki|Perempuan]
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.automation.ckg_bot import CKGBot                  # noqa: E402
from app.automation import selectors as S                  # noqa: E402

NILAI = sys.argv[1] if len(sys.argv) > 1 else "Laki-laki"


async def main():
    bot = CKGBot(headless=False, delay_ms=600)
    page = await bot.connect_to_browser()

    # pastikan modal terbuka
    if await page.get_by_text(S.SATUSEHAT["ph_jk"], exact=False).count() == 0:
        print("[VERIFY] Membuka modal 'Daftar Baru'...")
        await page.get_by_role("button", name="Daftar Baru").first.click()
        await page.wait_for_timeout(1200)

    print(f"[VERIFY] Memilih Jenis Kelamin = {NILAI} via _pilih_dropdown ...")
    await bot._pilih_dropdown(S.SATUSEHAT["label_jk"], NILAI,
                              placeholder=S.SATUSEHAT["ph_jk"], wajib=True)
    await page.wait_for_timeout(500)

    # baca kembali teks kontrol gender
    try:
        ctrl = page.locator(
            "xpath=(//*[contains(text(),'Jenis Kelamin')])[1]"
            "/following::*[contains(@class,'cursor-pointer')][1]").first
        txt = (await ctrl.inner_text()).strip()
    except Exception as e:
        txt = f"(gagal baca: {type(e).__name__})"
    print(f"[VERIFY] Teks kontrol gender sekarang: {txt!r}")
    if NILAI.lower() in txt.lower():
        print("[VERIFY] SUKSES: nilai ter-set dengan benar.")
    else:
        print("[VERIFY] PERHATIAN: teks kontrol belum mencerminkan pilihan.")

    await bot.stop()


if __name__ == "__main__":
    asyncio.run(main())
