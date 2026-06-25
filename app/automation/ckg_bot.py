"""
Bot automation portal CKG menggunakan Playwright.

Alur per peserta:
  1. (sekali di awal) login ke portal
  2. buka form pendaftaran -> isi identitas -> simpan
  3. isi form pelayanan/hasil pemeriksaan -> simpan
  4. ambil screenshot bukti, kembalikan status

CATATAN: selector di selectors.py masih placeholder. Sesuaikan dulu dengan
portal asli sebelum dipakai produksi. Struktur kode ini sudah siap; yang
perlu diubah hanya detail selektor & urutan langkah jika portal berbeda.
"""
import asyncio
import os
import re
from datetime import datetime
from typing import Optional

from playwright.async_api import async_playwright, Page, TimeoutError as PWTimeout

from . import selectors as S
from ..schema import Peserta, StatusSubmit

SCREENSHOT_DIR = "data/output/screenshots"


class LewatiPesertaError(Exception):
    """Penolakan portal yang BUKAN kegagalan teknis: pemanggil sebaiknya tandai
    baris di Excel (pakai `status_prefix`), refresh, lalu lanjut baris berikutnya
    - tidak perlu diproses ulang saat rerun. Subclass menetapkan label statusnya."""
    status_prefix = "DILEWATI"


class SudahMenerimaLayananError(LewatiPesertaError):
    """Individu SUDAH pernah CKG (notif 'Individu sudah menerima layanan')."""
    status_prefix = "SUDAH CKG"


class DataTidakValidError(LewatiPesertaError):
    """Portal menolak: 'Data peserta tidak valid' (NIK/Nama/Tgl Lahir tak cocok
    KTP/KK). Diperlakukan sama seperti sudah-layanan: tandai, refresh, lanjut."""
    status_prefix = "DATA TIDAK VALID"


class KesalahanProsesError(LewatiPesertaError):
    """Portal gagal memproses data di STEP 1 (popup 'Terjadi kesalahan - Belum
    bisa memproses data. Silakan coba lagi.'). Bukan kegagalan teknis bot:
    cukup dicatat di log & lewati - JANGAN diulang prosesnya (tandai terminal
    agar di-skip saat rerun)."""
    status_prefix = "GAGAL PROSES PORTAL"


class DukcapilFetchError(LewatiPesertaError):
    """Portal gagal mengambil data identitas dari Dukcapil saat simpan
    pendaftaran (popup 'Terjadi kesalahan / img-response-fetch - ada kesalahan
    saat mengambil data identitas anda. Silakan perbarui data di Dukcapil.').
    Masalah data sumber di sisi Dukcapil, BUKAN kegagalan teknis bot & tidak
    akan sembuh dengan retry: tandai terminal & lanjut (skip saat rerun)."""
    status_prefix = "GAGAL DUKCAPIL"


class SudahHadirError(LewatiPesertaError):
    """Peserta SUDAH dikonfirmasi hadir (baris menampilkan 'Sudah Hadir').
    Bukan kegagalan: tandai terminal & lanjut (skip saat rerun)."""
    status_prefix = "SUDAH HADIR"


class TidakDitemukanError(LewatiPesertaError):
    """NIK tak muncul di tabel saat difilter (kemungkinan tanggal pemeriksaan
    berbeda dari tanggal filter, atau belum terdaftar di tanggal itu)."""
    status_prefix = "TIDAK DITEMUKAN"


class CKGBot:
    def __init__(self, username: str = "", password: str = "",
                 headless: bool = True, delay_ms: int = 800,
                 otp_wait_s: int = 0, cdp_url: Optional[str] = None):
        self.username = username
        self.password = password
        self.headless = headless
        self.delay_ms = delay_ms       # jeda antar aksi (hindari deteksi bot)
        self.otp_wait_s = otp_wait_s    # detik menunggu input OTP/2FA manual (0 = nonaktif)
        self.cdp_url = cdp_url or S.CDP_URL
        self._pw = None
        self._browser = None
        self._page: Optional[Page] = None
        self._connected = False         # True bila menempel ke Chrome via CDP

    # ----- lifecycle (mode launch sendiri - dipakai web app lama) -----
    async def start(self):
        self._pw = await async_playwright().start()
        self._browser = await self._pw.chromium.launch(headless=self.headless)
        context = await self._browser.new_context()
        self._page = await context.new_page()

    # ----- lifecycle (mode CDP - menempel ke Chrome login manual) -----
    async def connect_to_browser(self, url_contains: Optional[str] = None) -> Page:
        """
        Menempel ke Chrome yang sudah dijalankan dengan --remote-debugging-port.

        TIDAK membuka login sendiri (login + CAPTCHA dilakukan manual oleh petugas).
        Memilih tab yang URL-nya mengandung `url_contains` (default: portal CKG).
        """
        url_contains = url_contains or S.URL_CKG_BERISI
        self._pw = await async_playwright().start()
        self._browser = await self._pw.chromium.connect_over_cdp(self.cdp_url)
        self._connected = True

        if not self._browser.contexts:
            raise RuntimeError(
                "Tidak ada context di Chrome. Pastikan Chrome berjalan dengan "
                "--remote-debugging-port=9222 dan minimal satu tab terbuka.")
        context = self._browser.contexts[0]

        page = None
        for pg in context.pages:
            if url_contains in (pg.url or ""):
                page = pg
                break
        if page is None:
            if context.pages:
                page = context.pages[0]
                print(f"[CKGBot] PERINGATAN: tidak menemukan tab ber-URL "
                      f"'{url_contains}'. Memakai tab pertama: {page.url}")
            else:
                page = await context.new_page()
        self._page = page
        await page.bring_to_front()
        print(f"[CKGBot] Terhubung ke Chrome. Tab aktif: {page.url}")
        return page

    async def stop(self):
        # Bila menempel ke Chrome milik petugas, JANGAN tutup browser-nya.
        try:
            if self._browser and not self._connected:
                await self._browser.close()
        finally:
            if self._pw:
                await self._pw.stop()

    async def _jeda(self):
        await self._page.wait_for_timeout(self.delay_ms)

    async def _settle(self, timeout_ms: int = 2000):
        """Tunggu jaringan tenang TAPI di-cap pendek. Di SPA (portal ini) network
        jarang benar-benar 'networkidle' karena ada polling, sehingga
        wait_for_load_state('networkidle') tanpa batas bisa menggantung ~30 detik.
        Pakai ini agar lanjut begitu idle, atau setelah `timeout_ms` (mana lebih dulu)."""
        try:
            await self._page.wait_for_load_state("networkidle", timeout=timeout_ms)
        except Exception:
            pass

    # ----- login -----
    async def login(self) -> bool:
        page = self._page
        await page.goto(S.URL_LOGIN)
        await page.fill(S.LOGIN["username"], self.username)
        await page.fill(S.LOGIN["password"], self.password)
        await self._jeda()
        await page.click(S.LOGIN["tombol_login"])

        # Portal pakai OTP/2FA? Beri jeda agar petugas memasukkan kode manual.
        # Mode ini hanya berguna saat headless=False (browser terlihat).
        if self.otp_wait_s > 0:
            if self.headless:
                print("[CKGBot] PERINGATAN: OTP diaktifkan tetapi headless=True; "
                      "input manual tidak mungkin. Jalankan dengan headless=False.")
            else:
                print(f"[CKGBot] Menunggu input OTP/2FA manual hingga "
                      f"{self.otp_wait_s} detik. Selesaikan login di jendela browser...")
            timeout_ms = max(self.otp_wait_s, 1) * 1000
        else:
            timeout_ms = 15000

        try:
            await page.wait_for_selector(S.LOGIN["indikator_sukses"], timeout=timeout_ms)
            return True
        except PWTimeout:
            return False

    async def pastikan_login(self) -> bool:
        """
        Pastikan sesi masih aktif sebelum submit (anti session-timeout).

        Bila portal sudah me-logout (form login muncul kembali), lakukan
        re-login otomatis. Kembalikan True bila sesi siap dipakai.
        """
        page = self._page
        try:
            # Jika elemen form login terdeteksi, berarti sesi sudah habis.
            perlu_login = await page.locator(
                S.LOGIN["indikator_perlu_login"]).count()
            if perlu_login > 0:
                print("[CKGBot] Sesi tampaknya habis. Mencoba re-login...")
                return await self.login()
            return True
        except Exception:
            # bila pengecekan gagal, coba re-login defensif
            return await self.login()

    # ----- isi field util -----
    async def _isi(self, selector: str, nilai):
        """Isi field teks. Lewati jika nilai kosong."""
        if nilai is None or nilai == "":
            return
        await self._page.fill(selector, str(nilai))

    async def _pilih(self, selector: str, nilai):
        """Pilih opsi dropdown (label). Lewati jika kosong."""
        if nilai is None or nilai == "":
            return
        try:
            await self._page.select_option(selector, label=str(nilai))
        except Exception:
            # fallback: anggap input teks biasa
            await self._isi(selector, nilai)

    # ----- submit satu peserta -----
    async def submit_peserta(self, p: Peserta) -> Peserta:
        page = self._page
        try:
            # 1. PENDAFTARAN
            await page.goto(S.URL_FORM_PENDAFTARAN)
            await self._isi(S.PENDAFTARAN["nik"], p.nik)
            await self._isi(S.PENDAFTARAN["nama"], p.nama)
            await self._isi(S.PENDAFTARAN["tgl_lahir"], p.tgl_lahir)
            await self._pilih(S.PENDAFTARAN["jenis_kelamin"],
                              "Laki-laki" if p.jenis_kelamin == "L" else "Perempuan")
            await self._isi(S.PENDAFTARAN["no_hp"], p.no_hp)
            await self._isi(S.PENDAFTARAN["alamat"], p.alamat)
            await self._jeda()
            await page.click(S.PENDAFTARAN["tombol_simpan"])
            await page.wait_for_selector(
                S.PENDAFTARAN["indikator_sukses"], timeout=15000)

            # 2. PELAYANAN / HASIL PEMERIKSAAN
            sel_pelayanan = S.PELAYANAN[p.kelompok_usia.value]
            for field_std, nilai in p.pemeriksaan.items():
                selector = sel_pelayanan.get(field_std)
                if selector:
                    await self._isi(selector, nilai)
            await self._jeda()
            await page.click(sel_pelayanan["tombol_simpan"])
            await page.wait_for_selector(
                sel_pelayanan["indikator_sukses"], timeout=15000)

            # 3. BUKTI
            os.makedirs(SCREENSHOT_DIR, exist_ok=True)
            shot = f"{SCREENSHOT_DIR}/{p.nik or 'noNIK'}_{int(datetime.now().timestamp())}.png"
            await page.screenshot(path=shot)

            p.status_submit = StatusSubmit.SUKSES
            p.keterangan = "OK"
            p.bukti_screenshot = shot
        except PWTimeout:
            p.status_submit = StatusSubmit.GAGAL
            p.keterangan = "Timeout menunggu konfirmasi portal"
        except Exception as e:
            p.status_submit = StatusSubmit.GAGAL
            p.keterangan = f"Error: {type(e).__name__}: {e}"

        p.waktu_submit = datetime.now().isoformat(timespec="seconds")
        return p

    # =====================================================================
    # ALUR SATUSEHAT (wizard 2-step) - dipakai trial & batch CDP
    # =====================================================================
    async def _shot(self, nama: str) -> str:
        """Ambil screenshot ber-label langkah, kembalikan path-nya."""
        os.makedirs(SCREENSHOT_DIR, exist_ok=True)
        path = f"{SCREENSHOT_DIR}/{nama}_{int(datetime.now().timestamp())}.png"
        try:
            await self._page.screenshot(path=path)
        except Exception:
            pass
        return path

    async def _klik_tombol(self, nama: str, timeout: int = 15000):
        """Klik tombol berdasarkan accessible name (teks tombol)."""
        # TODO verifikasi selector: pastikan teks tombol cocok di portal.
        btn = self._page.get_by_role("button", name=nama)
        await btn.first.wait_for(state="visible", timeout=timeout)
        await btn.first.click()

    async def _isi_label(self, label_text: str, nilai,
                         hanya_jika_kosong: bool = False,
                         wajib: bool = True, timeout: int = 8000):
        """
        Isi field input berdasarkan teks label.

        hanya_jika_kosong=True: lewati bila field sudah terisi (mis. auto-fill
                                dari hasil 'Cek NIK' / Dukcapil).
        wajib=False           : bila tidak bisa diisi (mis. field auto-fill,
                                read-only, atau date-picker), JANGAN error -
                                cukup beri peringatan & lanjut.
        timeout               : batas tunggu (ms) - sengaja pendek agar tidak
                                menggantung 30 detik bila ada modal yang menutupi.
        """
        if nilai is None or nilai == "":
            return
        # TODO verifikasi selector: field harus terkait label via <label for> / aria.
        field = self._page.get_by_label(label_text).first
        if hanya_jika_kosong:
            try:
                existing = await field.input_value(timeout=3000)
                if existing and existing.strip():
                    return
            except Exception:
                # tak bisa baca nilai (mungkin date-picker / auto-fill)
                if not wajib:
                    print(f"[CKGBot] Lewati '{label_text}' (tak bisa dibaca, "
                          f"anggap sudah terisi).")
                    return
        try:
            await field.fill(str(nilai), timeout=timeout)
        except Exception as e:
            if wajib:
                raise
            print(f"[CKGBot] Lewati '{label_text}' (tak bisa diisi: "
                  f"{type(e).__name__}). Mungkin auto-fill/date-picker.")

    async def _pesan_error_dialog(self) -> Optional[str]:
        """
        Deteksi dialog error portal (mis. 'Terjadi kesalahan / Gagal memproses
        data') setelah sebuah aksi. Kembalikan teksnya bila ada, atau None.
        """
        page = self._page
        for key in ("teks_error", "teks_error2"):
            penanda = S.SATUSEHAT.get(key)
            if not penanda:
                continue
            try:
                loc = page.get_by_text(penanda, exact=False).first
                if await loc.count() > 0 and await loc.is_visible():
                    try:
                        return (await loc.inner_text(timeout=2000)).strip()
                    except Exception:
                        return penanda
            except Exception:
                continue
        return None

    async def _ketik_label(self, label_text: str, nilai, wajib: bool = True,
                           timeout: int = 8000, blur: bool = True):
        """
        Isi field teks ala SPA React: fokus -> kosongkan -> KETIK per-karakter
        (press_sequentially memicu event keyboard/input/change yang dikenali
        React) -> Tab (blur) agar nilai ter-commit.
        """
        if nilai is None or nilai == "":
            return
        # TODO verifikasi selector: pastikan label terhubung ke input-nya.
        field = self._page.get_by_label(label_text).first
        try:
            await field.click(timeout=timeout)
            try:
                await field.fill("", timeout=timeout)        # kosongkan dulu
            except Exception:
                pass
            await field.press_sequentially(str(nilai), delay=35, timeout=timeout)
            if blur:
                await field.press("Tab")
        except Exception as e:
            if wajib:
                raise
            print(f"[CKGBot] Lewati ketik '{label_text}' "
                  f"({type(e).__name__}). Mungkin field tak ada/terkunci.")

    async def _centang(self, teks_regex: str, wajib: bool = True):
        """
        Centang checkbox yang labelnya cocok regex `teks_regex`
        (mis. 'Tidak.*NIK'). Coba role=checkbox -> label -> klik teks.
        """
        page = self._page
        pola = re.compile(teks_regex, re.I)
        try:
            cb = page.get_by_role("checkbox", name=pola).first
            if await cb.count() == 0:
                cb = page.get_by_label(pola).first
            if await cb.count() > 0:
                await cb.check(timeout=8000)
                return
            # fallback: klik elemen teksnya langsung
            await page.get_by_text(pola).first.click(timeout=8000)
        except Exception as e:
            if wajib:
                raise
            print(f"[CKGBot] Lewati centang '{teks_regex}' ({type(e).__name__}).")

    async def _nilai_field(self, field) -> str:
        """Baca nilai sebuah field (input_value / atribut value) seandainya ada."""
        for getter in ("el => el.value || ''", "el => el.getAttribute('value') || ''"):
            try:
                v = await field.evaluate(getter)
                if v and str(v).strip():
                    return str(v)
            except Exception:
                continue
        try:
            v = await field.input_value(timeout=1500)
            if v and v.strip():
                return v
        except Exception:
            pass
        return ""

    async def _diagnostik_elemen(self, label_text: str) -> str:
        """
        Ambil cuplikan HTML field + popup kalender yang sedang terbuka, untuk
        dikirim balik agar navigasi kalender bisa dibuat presisi.
        """
        page = self._page
        out = []
        try:
            field = page.get_by_label(label_text).first
            html = await field.evaluate(
                "el => { const w = el.closest('div') || el; "
                "return (w.outerHTML||'').slice(0,1200); }")
            out.append("FIELD: " + " ".join(html.split()))
        except Exception as e:
            out.append(f"FIELD: (gagal ambil: {type(e).__name__})")
        try:
            # popup vue2-datepicker yang sedang terbuka (di body-level)
            cal = page.locator(
                ".mx-datepicker-main, [class*=calendar], [class*=picker], [role=dialog]")
            n = await cal.count()
            for i in range(min(n, 5)):
                el = cal.nth(i)
                if await el.is_visible():
                    cls = await el.evaluate("el => el.className || ''")
                    snip = await el.evaluate("el => (el.outerHTML||'').slice(0,1200)")
                    out.append(f"POPUP[{cls}]: " + " ".join(snip.split()))
                    break
        except Exception as e:
            out.append(f"POPUP: (gagal: {type(e).__name__})")
        return "\n".join(out)

    async def _picker_root(self, placeholder_regex: str, label_text: str):
        """Locator .mx-datepicker untuk satu field: via teks placeholder (unik),
        fallback ke label diikuti .mx-datepicker."""
        page = self._page
        root = page.locator(".mx-datepicker",
                            has_text=re.compile(placeholder_regex, re.I)).first
        if await root.count() > 0:
            return root
        label = page.get_by_text(label_text, exact=False).first
        return label.locator("xpath=following::div[contains(@class,'mx-datepicker')][1]")

    async def _pilih_tanggal_mx(self, root, d):
        """
        Navigasi kalender vue2-datepicker (kelas mx-*): buka -> panel TAHUN ->
        navigasi dekade -> klik tahun -> klik bulan (urutan Jan..Des) -> klik hari.

        PENTING: vue2-datepicker default appendToBody=true, jadi popup
        (.mx-datepicker-main) ada di <body>, BUKAN di dalam root. Navigasi
        dilakukan pada `popup` level-halaman.
        """
        page = self._page
        # buka popup kalender (klik area input picker ini)
        await root.locator(".mx-input-wrapper, .mx-input").first.click(timeout=6000)
        await self._jeda()
        popup = page.locator(".mx-datepicker-main").first
        await popup.wait_for(state="visible", timeout=8000)

        # 1) buka panel TAHUN (klik tombol tahun di header, mis. "2026")
        await popup.locator(".mx-btn-current-year").first.click(timeout=6000)
        await self._jeda()

        # 2) navigasi dekade (tombol << / >>) sampai tahun target tampak
        for _ in range(40):
            cells = popup.locator(".mx-table-year td.cell")
            texts = [t.strip() for t in await cells.all_inner_texts()]
            nums = [int(t) for t in texts if t.isdigit()]
            if nums and nums[0] <= d.year <= nums[-1]:
                break
            if not nums:
                break
            if d.year < nums[0]:
                await popup.locator(".mx-btn-icon-double-left").first.click()
            else:
                await popup.locator(".mx-btn-icon-double-right").first.click()
            await self._jeda()
        await popup.locator(".mx-table-year td.cell",
                            has_text=re.compile(rf"^\s*{d.year}\s*$")).first.click(timeout=6000)
        await self._jeda()

        # 3) panel BULAN: 12 sel urut Jan..Des -> klik indeks (month-1), tahan locale
        await popup.locator(".mx-table-month td.cell").nth(d.month - 1).click(timeout=6000)
        await self._jeda()

        # 4) panel TANGGAL: klik hari pada bulan berjalan (abaikan sel bulan lain)
        await popup.locator(
            ".mx-table-date td.cell:not(.not-current-month):not(.last-month)"
            ":not(.next-month)",
            has_text=re.compile(rf"^\s*{d.day}\s*$")).first.click(timeout=6000)
        await self._jeda()

        # vue2-datepicker menutup popup setelah tanggal lengkap dipilih
        try:
            await popup.wait_for(state="hidden", timeout=4000)
        except Exception:
            pass
        # baca tampilan via locator stabil (label-following), bukan root placeholder.
        # PENTING: cek count() dulu & pakai timeout pendek - di halaman lain (mis.
        # konfirmasi hadir) teks 'Tanggal Lahir' bisa ada sbg header tabel tanpa
        # datepicker sesudahnya, sehingga inner_text() tanpa batas akan menggantung
        # ~30 detik menunggu elemen yang tak pernah muncul.
        txt = ""
        try:
            disp = self._page.locator(
                "xpath=(//*[contains(text(),'Tanggal Lahir')])[1]"
                "/following::div[contains(@class,'mx-datepicker')][1]").first
            if await disp.count() > 0:
                txt = (await disp.inner_text(timeout=1500)).strip()
        except Exception:
            txt = ""
        if "pilih" in txt.lower():
            raise RuntimeError(f"tanggal belum ter-set (tampilan masih '{txt}')")
        return txt or "(terpilih)"

    async def _isi_tanggal(self, label_text: str, iso_date: Optional[str],
                           wajib: bool = True):
        """
        Isi field tanggal. Portal CKG memakai vue2-datepicker (kelas mx-*) yang
        TIDAK bisa diketik -> harus navigasi kalender. Bila navigasi gagal, buka
        kalender, screenshot, & cetak DIAGNOSTIK DOM untuk penyesuaian lanjutan.
        """
        if not iso_date:
            return
        from datetime import datetime as _dt
        try:
            d = _dt.strptime(iso_date, "%Y-%m-%d")
        except ValueError:
            d = None

        # Picker Tanggal Lahir dikenali dari placeholder "Pilih tanggal lahir".
        root = await self._picker_root("tanggal lahir", label_text)

        if d is not None:
            try:
                hasil = await self._pilih_tanggal_mx(root, d)
                print(f"[CKGBot] Tanggal '{label_text}' dipilih via kalender: {hasil}")
                return
            except Exception as e:
                print(f"[CKGBot] Navigasi kalender gagal: {type(e).__name__}: {e}")

        # fallback: buka kalender, foto, dump diagnostik
        try:
            await root.locator(".mx-input-wrapper, .mx-input").first.click(timeout=4000)
            await self._jeda()
        except Exception:
            pass
        shot = await self._shot("kalender_tgl_lahir")
        diag = await self._diagnostik_elemen(label_text)
        print("[CKGBot][DIAG date-picker]\n" + diag)
        if wajib:
            raise RuntimeError(
                f"Gagal memilih tanggal '{label_text}' = {iso_date} di kalender. "
                f"Screenshot: {shot}. Kirim blok '[DIAG date-picker]' + screenshot "
                f"itu untuk penyesuaian selector kalender.")
        print(f"[CKGBot] Lewati tanggal '{label_text}'.")

    async def _kontrol_dropdown(self, label_text: str, placeholder: Optional[str]):
        """Locator elemen yang harus DIKLIK untuk membuka dropdown custom.

        PENTING: pada dropdown Vue portal CKG, teks placeholder ada di dalam
        <span>/<div> non-interaktif; meng-klik teksnya TIDAK memicu handler buka.
        Naikkan ke div ber-class 'cursor-pointer' terdekat (kontrol sebenarnya).
        """
        page = self._page
        if placeholder:
            loc = page.get_by_text(placeholder, exact=False).first
            if await loc.count() > 0:
                klik = loc.locator(
                    "xpath=ancestor-or-self::*[contains(@class,'cursor-pointer')][1]")
                if await klik.count() > 0:
                    return klik.first
                return loc
        # fallback: elemen interaktif pertama setelah teks label. Termasuk
        # div 'cursor-pointer' agar dropdown custom Vue (Step 2: Status Pernikahan,
        # Disabilitas, Pekerjaan) yang tanpa placeholder tetap bisa dibuka.
        return page.locator(
            f"xpath=(//*[contains(text(),'{label_text}')])[1]/following::*"
            f"[self::button or @role='combobox' or @role='button' "
            f"or contains(@class,'select') or contains(@class,'cursor-pointer')][1]").first

    async def _diagnostik_dropdown(self, label_text: str,
                                   placeholder: Optional[str]) -> str:
        """Cuplikan HTML kontrol dropdown + opsi yang terlihat (untuk debugging)."""
        page = self._page
        out = []
        try:
            kontrol = await self._kontrol_dropdown(label_text, placeholder)
            html = await kontrol.evaluate(
                "el => { const w = el.closest('div')||el; "
                "return (w.outerHTML||'').slice(0,1000);} ")
            out.append("KONTROL: " + " ".join(html.split()))
        except Exception as e:
            out.append(f"KONTROL: (gagal: {type(e).__name__})")
        try:
            opt = page.locator(
                "[role=option], li.dropdown-item, .vs__dropdown-option, "
                "ul[role=listbox] li, .el-select-dropdown__item, "
                "div[class*='shadow-standard'] div[class*='cursor-pointer']")
            n = await opt.count()
            sample = []
            for i in range(min(n, 8)):
                sample.append((await opt.nth(i).inner_text()).strip())
            out.append(f"OPSI terlihat ({n}): {sample}")
        except Exception as e:
            out.append(f"OPSI: (gagal: {type(e).__name__})")
        return "\n".join(out)

    async def _pilih_dropdown(self, label_text: str, nilai,
                              placeholder: Optional[str] = None,
                              wajib: bool = True):
        """
        Pilih opsi dropdown. Coba <select> native dulu (dekat label), lalu
        dropdown custom Vue (klik kontrol -> klik opsi). Bila gagal & wajib,
        cetak DIAGNOSTIK DOM lalu error.
        """
        if nilai is None or nilai == "":
            return
        page = self._page
        try:
            # A) <select> native pertama setelah label
            sel = page.locator(
                f"xpath=(//*[contains(text(),'{label_text}')])[1]"
                f"/following::select[1]").first
            if await sel.count() > 0:
                for how in (dict(label=str(nilai)), dict(value=str(nilai)),
                            dict(label=str(nilai).upper())):
                    try:
                        await sel.select_option(**how, timeout=4000)
                        print(f"[CKGBot] Dropdown '{label_text}' (select) -> {nilai}")
                        return
                    except Exception:
                        continue

            # B) dropdown custom: buka via placeholder/label lalu klik opsi
            kontrol = await self._kontrol_dropdown(label_text, placeholder)
            await kontrol.click(timeout=6000)
            await self._jeda()

            # B1) Dropdown SEARCHABLE (mis. Pekerjaan): muncul kotak "Cari ...".
            # Opsi hanya ter-render setelah mengetik -> ketik nilai untuk memfilter.
            try:
                search = page.get_by_placeholder(re.compile(r"^\s*Cari", re.I)).first
                if await search.count() > 0 and await search.is_visible():
                    await search.fill(str(nilai))
                    await self._jeda()
            except Exception:
                pass

            pola = re.compile(re.escape(str(nilai)), re.I)
            # cocok PERSIS (anti-salah-target, mis. sel tabel "Laki-Laki")
            exact = re.compile(rf"^\s*{re.escape(str(nilai))}\s*$", re.I)
            for loc in (
                # dropdown custom Vue portal CKG: opsi = <div class="...cursor-pointer
                # ...hover:bg-gray-1"> di panel mengambang (z-2000/shadow-standard).
                page.locator(
                    "div[class*='cursor-pointer'][class*='hover:bg-gray-1']"
                ).filter(has_text=exact),
                # cadangan: panel mengambang -> div opsi apa pun yang teksnya persis
                page.locator(
                    "div[class*='shadow-standard'] div[class*='cursor-pointer']"
                ).filter(has_text=exact),
                # catch-all utk panel ber-markup lain (mis. dropdown SEARCHABLE
                # Pekerjaan): teks opsi PERSIS tapi CASE-INSENSITIVE (data Excel
                # bisa 'PEGAWAI SWASTA' sedang portal 'Pegawai Swasta'). Pakai
                # regex anchored di get_by_text (menerima nilai ber-'/'). Visible-
                # only agar tak kena elemen tersembunyi.
                page.get_by_text(exact).locator("visible=true"),
                page.locator(
                    "li,[role=option],.dropdown-item,.vs__dropdown-option,"
                    ".el-select-dropdown__item").filter(has_text=pola),
                page.get_by_role("option", name=pola),
            ):
                # Per-kandidat di-try: selector tertentu bisa InvalidSelectorError
                # untuk nilai ber-'/' (mis. 'Petani / Pekebun') -> jangan gagalkan
                # kandidat lain. Cocokkan teks PERSIS dulu (div), baru fallback.
                try:
                    if await loc.count() > 0:
                        await loc.first.click(timeout=5000)
                        print(f"[CKGBot] Dropdown '{label_text}' (custom) -> {nilai}")
                        return
                except Exception:
                    continue
            raise RuntimeError(f"opsi '{nilai}' tak ditemukan setelah dropdown dibuka")
        except Exception as e:
            if not wajib:
                print(f"[CKGBot] Lewati dropdown '{label_text}' "
                      f"({type(e).__name__}). Mungkin sudah terisi otomatis.")
                return
            diag = await self._diagnostik_dropdown(label_text, placeholder)
            print("[CKGBot][DIAG dropdown]\n" + diag)
            raise RuntimeError(
                f"Dropdown '{label_text}'='{nilai}' gagal: {type(e).__name__}. "
                f"Lihat '[DIAG dropdown]' di atas.")

    async def _centang_tanpa_wali(self):
        """
        Bila section 'Isi Data Wali' muncul (umumnya balita/lansia/tanpa NIK),
        centang 'Daftarkan tanpa data wali' agar field wali tidak wajib diisi.
        Non-fatal: bila tidak ada, lewati diam-diam.
        """
        page = self._page
        try:
            # Checkbox asli <input name="noWali"> adalah checkbox custom Vue: input
            # kerap tersembunyi (ukuran 0 / ditutup overlay), jadi check(force=True)
            # bisa gagal ("Error") karena klik nyata tak bisa mengenainya. Strategi
            # bertingkat: (1) klik label/teks, (2) force-check input, (3) set via JS
            # + dispatch event agar v-model Vue ikut update. Bila section wali tak
            # muncul, input ini tak ada -> lewati.
            cb = page.locator("input[name='noWali']")
            if await cb.count() == 0:
                return  # section wali tidak muncul
            cb = cb.first
            # Scroll section 'Isi Data Wali' ke viewport: portal kadang tak
            # memvalidasi field di luar layar -> 'Selanjutnya' tetap disabled.
            # <input name=noWali> tersembunyi (ukuran 0) sehingga scroll padanya
            # TIDAK menggeser modal; jadi scroll lewat ELEMEN TERLIHAT (teks
            # label) pakai JS scrollIntoView -> menggulirkan scroll-container modal.
            for target in ("Daftarkan tanpa data wali", "Isi Data Wali"):
                try:
                    el = page.get_by_text(target, exact=False).first
                    if await el.count() > 0:
                        await el.evaluate(
                            "e => e.scrollIntoView({block:'center'})")
                        await self._jeda()
                        break
                except Exception:
                    continue
            if await cb.is_checked():
                await self._jeda()
                return

            async def _tercentang() -> bool:
                try:
                    return await cb.is_checked()
                except Exception:
                    return False

            # (1) klik label/teks (memicu handler wrapper bila ada)
            try:
                await page.get_by_text(
                    "Daftarkan tanpa data wali", exact=False).first.click(
                    timeout=2500)
                await self._jeda()
            except Exception:
                pass

            # (2) force-check langsung pada input
            if not await _tercentang():
                try:
                    await cb.check(force=True, timeout=3000)
                    await self._jeda()
                except Exception:
                    pass

            # (3) fallback JS: set checked + dispatch input/change utk Vue
            if not await _tercentang():
                try:
                    await cb.evaluate(
                        "el => { el.checked = true; "
                        "el.dispatchEvent(new Event('input', {bubbles:true})); "
                        "el.dispatchEvent(new Event('change', {bubbles:true})); }")
                    await self._jeda()
                except Exception:
                    pass

            if await _tercentang():
                print("[CKGBot] Checkbox 'Daftarkan tanpa data wali' dicentang.")
            else:
                await self._shot("gagal_centang_tanpa_wali")
                print("[CKGBot] PERINGATAN: 'Daftarkan tanpa data wali' "
                      "TIDAK tercentang setelah 3 cara; 'Selanjutnya' mungkin "
                      "tetap nonaktif.")
        except Exception as e:
            print(f"[CKGBot] Tidak bisa centang 'tanpa data wali' "
                  f"({type(e).__name__}: {e}); lanjut.")

    async def _pilih_tgl_pemeriksaan(self, iso_date: Optional[str] = None,
                                     wajib: bool = True) -> bool:
        """
        Pilih Tanggal Pemeriksaan pada kalender INLINE (default: HARI INI).

        Kalender ini BUKAN mx-datepicker: tiap hari = <button> berisi
        <span class="font-bold text-[18px]">N</span>. Hari non-aktif (tanggal
        lewat / kuota habis) ber-class 'cursor-not-allowed'.

        PENTING: tanpa MEMILIH tanggal di sini, tombol 'Selanjutnya' tetap
        disabled (dirender sebagai <div>, bukan <button>), sehingga Step 1
        tidak bisa lanjut. Hanya mendukung tanggal pada bulan yang sedang tampil
        (default kalender = bulan berjalan); untuk CKG, pemeriksaan = hari ini.
        """
        from datetime import datetime as _dt, date as _date
        page = self._page
        target = _date.today()
        if iso_date:
            try:
                target = _dt.strptime(iso_date, "%Y-%m-%d").date()
            except ValueError:
                pass
        hari = str(target.day)
        btns = page.locator("button:has(span[class*='text-[18px]'])")
        n = await btns.count()
        for i in range(n):
            el = btns.nth(i)
            try:
                t = (await el.locator("span[class*='text-[18px]']")
                     .first.inner_text()).strip()
            except Exception:
                continue
            if t != hari:
                continue
            cls = await el.get_attribute("class") or ""
            if "cursor-not-allowed" in cls:
                msg = (f"Tanggal Pemeriksaan {target.isoformat()} non-aktif "
                       f"(tanggal lewat / kuota habis).")
                if wajib:
                    raise RuntimeError(msg)
                print(f"[CKGBot] {msg} Lewati.")
                return False
            await el.scroll_into_view_if_needed()
            await el.click(timeout=5000)
            await self._jeda()
            print(f"[CKGBot] Tanggal Pemeriksaan dipilih: {target.isoformat()}")
            return True
        msg = (f"Tombol tanggal {hari} tak ditemukan di kalender pemeriksaan "
               f"(mungkin perlu navigasi bulan).")
        if wajib:
            raise RuntimeError(msg)
        print(f"[CKGBot] {msg} Lewati.")
        return False

    # Timing cascade alamat (longgar agar tahan koneksi internet lambat).
    # Naikkan bila perlu: hasil pencarian wilayah dimuat via jaringan.
    ALAMAT_SEARCHBOX_TIMEOUT_MS = 15000   # tunggu kotak cari level muncul
    ALAMAT_RESULT_TIMEOUT_MS = 25000      # tunggu item hasil pencarian muncul
    ALAMAT_SETTLE_MS = 700                # jeda debounce setelah mengetik / pilih

    async def _isi_alamat_domisili(self, p, wajib: bool = True):
        """
        Isi 'Alamat Domisili' = cascade wilayah lewat overlay 'Pilih Lokasi':
        Provinsi -> Kabupaten/Kota -> Kecamatan -> Kelurahan. Tiap level punya
        kotak cari ("Cari Provinsi", "Cari Kabupaten/Kota", dst): ketik nilai
        lalu klik item yang teksnya PERSIS. Nilai harus sama persis dgn nama
        wilayah di portal (mis. "Jawa Timur", "Kabupaten Gresik", "Driyorejo").

        Tahan koneksi lambat: tiap level MENUNGGU hasil pencarian benar-benar
        muncul (poll s/d ALAMAT_RESULT_TIMEOUT_MS) sebelum meng-klik, bukan
        sekadar jeda tetap.
        """
        page = self._page
        levels = [
            ("Provinsi",       "Cari Provinsi",       p.provinsi),
            ("Kabupaten/Kota", "Cari Kabupaten/Kota", p.kabupaten_kota),
            ("Kecamatan",      "Cari Kecamatan",      p.kecamatan),
            ("Kelurahan",      "Cari Kelurahan",      p.kelurahan),
        ]
        if not any(v for _, _, v in levels):
            if wajib:
                raise RuntimeError(
                    "Alamat Domisili kosong: kolom Provinsi/Kabupaten/Kota/"
                    "Kecamatan/Kelurahan di Excel belum diisi.")
            print("[CKGBot] Alamat Domisili dilewati (kosong).")
            return

        # buka kontrol -> overlay 'Pilih Lokasi'
        ctrl = await self._kontrol_dropdown("Alamat Domisili", None)
        await ctrl.click(timeout=6000)
        await self._jeda()

        for nama_level, ph, nilai in levels:
            if not nilai:
                raise RuntimeError(
                    f"Nilai '{nama_level}' kosong - keempat tingkat alamat "
                    f"(Provinsi/Kabupaten/Kota/Kecamatan/Kelurahan) wajib diisi.")
            # 1) tunggu kotak cari level ini muncul (level sebelumnya selesai dimuat)
            search = page.get_by_placeholder(ph).first
            try:
                await search.wait_for(
                    state="visible", timeout=self.ALAMAT_SEARCHBOX_TIMEOUT_MS)
            except PWTimeout:
                raise RuntimeError(
                    f"Kotak cari '{ph}' tak muncul - cascade alamat macet "
                    f"sebelum level {nama_level} (koneksi lambat?).")
            await search.fill(str(nilai))
            # debounce: beri waktu input ter-proses sebelum hasil dimuat
            await page.wait_for_timeout(self.ALAMAT_SETTLE_MS)

            # 2) POLL: tunggu item hasil muncul (hasil dimuat via jaringan)
            opt = await self._tunggu_opsi_alamat(
                str(nilai), self.ALAMAT_RESULT_TIMEOUT_MS)
            if opt is None:
                raise RuntimeError(
                    f"Wilayah '{nilai}' tak muncul di daftar {nama_level} dalam "
                    f"{self.ALAMAT_RESULT_TIMEOUT_MS // 1000}s. Cek ejaan (harus "
                    f"PERSIS sama portal) atau koneksi internet.")
            await opt.click(timeout=8000)
            # 3) beri waktu level berikutnya / penutupan overlay termuat
            await page.wait_for_timeout(self.ALAMAT_SETTLE_MS)
            await self._jeda()
            print(f"[CKGBot] Alamat {nama_level}: {nilai}")
        print("[CKGBot] Alamat Domisili (cascade wilayah) selesai.")

    async def _tunggu_opsi_alamat(self, nilai: str, timeout_ms: int):
        """Poll s/d timeout: kembalikan locator ITEM DAFTAR hasil pencarian yang
        terlihat, atau None bila tak muncul.

        PENTING: overlay 'Pilih Lokasi' menampilkan dua jenis elemen ber-teks
        sama: (a) CHIP breadcrumb pilihan terdahulu (<button ...rounded-md>) dan
        (b) ITEM daftar yang sebenarnya (<button ...text-left...border-b>). Kita
        HARUS klik item daftar, bukan chip (klik chip malah membuka ulang level
        sebelumnya). Maka pencarian dibatasi ke button 'text-left' di .modal-content.
        """
        page = self._page
        exact = re.compile(rf"^\s*{re.escape(str(nilai))}\s*$", re.I)
        waited = 0
        interval = 400
        while waited <= timeout_ms:
            for cand in (
                # item daftar di dalam overlay (bukan chip breadcrumb rounded-md)
                page.locator(".modal-content button[class*='text-left']")
                    .filter(has_text=exact),
                page.locator("button[class*='text-left']").filter(has_text=exact),
            ):
                try:
                    c = cand.first
                    if await c.count() > 0 and await c.is_visible():
                        return c
                except Exception:
                    pass
            await page.wait_for_timeout(interval)
            waited += interval
        return None

    async def _pilih_baris_individu(self, nik: str):
        """
        Pada 'List Data Individu' (halaman konfirmasi), klik tombol 'Pilih' di
        baris yang NIK-nya cocok. Ini MENG-AKTIFKAN tombol 'Daftarkan dengan NIK'
        (sebelum 'Pilih' tombol itu masih disabled / dirender <div>).
        Bila NIK tak ketemu, pakai baris pertama yang punya tombol 'Pilih'.
        """
        page = self._page
        row = page.locator("tr", has_text=str(nik)).first
        if await row.count() == 0:
            row = page.locator("tr").filter(
                has=page.get_by_text("Pilih", exact=True)).first
        btn = row.get_by_role("button", name="Pilih").first
        if await btn.count() == 0:
            btn = row.get_by_text("Pilih", exact=True).first
        await btn.click(timeout=8000)
        await self._jeda()
        print(f"[CKGBot] 'Pilih' baris individu (NIK {nik}).")

    async def _ekstrak_tiket(self, timeout_ms: int = 10000) -> Optional[str]:
        """Ambil No. Tiket (mis. 'H75-RFB') dari dialog 'Berhasil Daftar'.

        No. Tiket kadang baru ter-render beberapa saat setelah dialog sukses
        muncul, jadi pembacaan di-poll berulang sampai `timeout_ms` sebelum
        menyerah (mencegah false-negative 'tidak terbaca').
        """
        page = self._page
        pola = re.compile(r"\b([A-Z0-9]{2,4}-[A-Z0-9]{2,5})\b")
        sisa = timeout_ms
        interval = 500
        while True:
            # 1) coba dari elemen yang memuat kata 'Tiket'
            try:
                el = page.get_by_text(S.SATUSEHAT["teks_tiket"], exact=False).first
                teks = await el.inner_text(timeout=2000)
                m = pola.search(teks)
                if m:
                    return m.group(1)
            except Exception:
                pass
            # 2) fallback: cari di seluruh body
            try:
                teks = await page.inner_text("body")
                m = pola.search(teks)
                if m:
                    return m.group(1)
            except Exception:
                pass
            if sisa <= 0:
                return None
            await page.wait_for_timeout(interval)
            sisa -= interval

    async def daftar_satu(self, p: Peserta, on_step=None) -> Optional[str]:
        """
        Daftarkan SATU peserta mengikuti wizard portal SATUSEHAT.

        Mengembalikan No. Tiket bila berhasil. Bila gagal di suatu langkah,
        melempar RuntimeError yang menyebut langkah + path screenshot, dan
        TIDAK melanjutkan ke langkah berikutnya.

        on_step(nama, info): callback opsional untuk logging dari pemanggil.
        """
        page = self._page
        L = S.SATUSEHAT

        def log(nama, info=""):
            if on_step:
                on_step(nama, info)

        langkah = "mulai"
        try:
            # --- pastikan di halaman /ckg-pendaftaran-individu (auto-navigasi,
            #     konsisten dgn konfirmasi hadir & pelayanan) ---
            langkah = "buka halaman daftar individu"
            log(langkah)
            if S.URL_PENDAFTARAN_INDIVIDU not in (page.url or ""):
                await page.goto(S.URL_PENDAFTARAN_INDIVIDU)
                await self._settle(timeout_ms=8000)
            await self._tutup_dialog()
            await self._jeda()

            # --- buka formulir ---
            langkah = "klik 'Daftar Baru'"
            log(langkah)
            await self._klik_tombol(L["btn_daftar_baru"])   # TODO verifikasi selector
            await page.wait_for_load_state("networkidle")
            await self._jeda()

            # --- STEP 1: Isi identitas (semua manual, TANPA Cek NIK) ---
            # NIK diisi langsung sebagai textbox biasa (tombol "Cek NIK" tidak
            # diklik & checkbox "Tidak punya NIK" tidak dipakai).
            langkah = "isi NIK"
            log(langkah, p.nik)
            await self._ketik_label(L["label_nik"], p.nik, wajib=True)

            langkah = "isi Nama Lengkap"
            log(langkah, p.nama)
            await self._ketik_label(L["label_nama"], p.nama, wajib=True)

            langkah = "isi Tanggal Lahir"
            log(langkah, p.tgl_lahir)
            await self._isi_tanggal(L["label_tgl_lahir"], p.tgl_lahir, wajib=True)

            # Centang 'Daftarkan tanpa data wali' tepat setelah Tanggal Lahir
            # (bila section wali muncul). Dilakukan SEBELUM Jenis Kelamin agar
            # dropdown JK wali ikut hilang -> JK peserta tak ambigu. Jeda agar
            # form settle.
            langkah = "centang 'Daftarkan tanpa data wali' (bila ada)"
            log(langkah)
            await self._centang_tanpa_wali()
            await self._jeda()

            langkah = "pilih Jenis Kelamin"
            jk = "Laki-laki" if (p.jenis_kelamin or "").upper() == "L" else "Perempuan"
            log(langkah, jk)
            await self._pilih_dropdown(L["label_jk"], jk,
                                       placeholder=L["ph_jk"], wajib=True)

            langkah = "isi No. WhatsApp Aktif"
            no_wa = p.no_wa or p.no_hp
            log(langkah, no_wa)
            await self._ketik_label(L["label_wa"], no_wa, wajib=True)

            # Tanggal Pemeriksaan = langkah TERAKHIR (WAJIB diklik; default kalender
            # tidak otomatis ter-pilih). Ditaruh paling akhir karena meng-enable
            # 'Selanjutnya' hanya setelah semua field lain valid - kalau dipilih
            # lebih awal, 'Selanjutnya' bisa tetap disabled (bug timing portal).
            langkah = "pilih Tanggal Pemeriksaan"
            log(langkah, p.tanggal_pemeriksaan or "hari ini")
            await self._pilih_tgl_pemeriksaan(p.tanggal_pemeriksaan, wajib=True)
            await self._jeda()
            await self._shot("step1_identitas")

            langkah = "klik 'Selanjutnya' (Step 1)"
            log(langkah)
            await self._klik_tombol(L["btn_selanjutnya"])    # TODO verifikasi selector
            await page.wait_for_load_state("networkidle")
            await self._jeda()

            # --- POPUP hasil setelah 'Selanjutnya' (Step 1) ---
            # Tiga kemungkinan, semuanya bisa telat render -> poll sampai salah
            # satu muncul:
            #   1) "Individu sudah menerima layanan" -> sudah pernah CKG (tandai
            #      & lanjut baris berikutnya, BUKAN error teknis).
            #   2) "Data peserta tidak valid" -> NIK/Nama/Tgl Lahir tak cocok KTP/KK.
            #   3) "Data peserta valid" -> klik 'Lanjutkan' menuju Step 2.
            langkah = "konfirmasi popup validasi data"
            log(langkah)
            sisa = 10000
            interval = 500
            while sisa > 0:
                if await page.get_by_text(
                        L["teks_sudah_layanan"], exact=False).count() > 0:
                    await self._shot("sudah_menerima_layanan")
                    raise SudahMenerimaLayananError(
                        "Individu sudah menerima layanan (sudah pernah CKG).")
                if await page.get_by_text(
                        L["teks_tidak_valid"], exact=False).count() > 0:
                    await self._shot("data_tidak_valid")
                    raise DataTidakValidError(
                        "Data peserta tidak valid - NIK/Nama/Tgl Lahir tak cocok "
                        "KTP/KK.")
                # Popup 'Terjadi kesalahan - Belum bisa memproses data. Silakan
                # coba lagi.' -> cukup catat & lewati, JANGAN diulang prosesnya.
                if await page.get_by_text(
                        L["teks_belum_proses"], exact=False).count() > 0:
                    await self._shot("belum_bisa_memproses")
                    raise KesalahanProsesError(
                        "Portal belum bisa memproses data (Terjadi kesalahan) "
                        "saat Isi identitas. Dilewati, tidak diulang.")
                # Gagal ambil data identitas dari Dukcapil (img-response-fetch).
                if await page.get_by_text(
                        re.compile(L["teks_dukcapil_fetch"], re.IGNORECASE)
                        ).count() > 0:
                    await self._shot("gagal_dukcapil")
                    raise DukcapilFetchError(
                        "Gagal mengambil data identitas dari Dukcapil. Peserta "
                        "perlu memperbarui data di Dukcapil. Dilewati, tidak "
                        "diulang.")
                if await page.get_by_text(
                        L["teks_valid"], exact=False).count() > 0:
                    break
                await page.wait_for_timeout(interval)
                sisa -= interval
            langkah = "klik 'Lanjutkan' (popup data valid)"
            log(langkah)
            try:
                await self._klik_tombol(L["btn_lanjutkan"], timeout=10000)
                await page.wait_for_load_state("networkidle")
                await self._jeda()
            except Exception:
                print("[CKGBot] Popup 'Lanjutkan' tidak muncul; lanjut ke Step 2.")

            # --- STEP 2: Isi data pendukung ---
            langkah = "isi data pendukung (Step 2)"
            log(langkah)
            await self._pilih_dropdown(L["label_status_nikah"], p.status_pernikahan)
            await self._pilih_dropdown(L["label_disabilitas"], p.disabilitas)
            await self._pilih_dropdown(L["label_pekerjaan"], p.pekerjaan)
            # Alamat Domisili = cascade wilayah (Provinsi->Kab/Kota->Kec->Kelurahan).
            langkah = "isi Alamat Domisili (cascade wilayah)"
            log(langkah)
            await self._isi_alamat_domisili(p, wajib=True)
            langkah = "isi Detail Alamat Domisili"
            log(langkah)
            await self._ketik_label(L["label_detail_alamat"], p.detail_alamat,
                                    wajib=False)
            await self._shot("step2_pendukung")

            langkah = "klik 'Selanjutnya' (Step 2)"
            log(langkah)
            await self._klik_tombol(L["btn_selanjutnya"])    # TODO verifikasi selector
            await page.wait_for_load_state("networkidle")
            await self._jeda()

            # --- KONFIRMASI: List Data Individu -> Daftarkan DENGAN NIK ---
            # Portal menampilkan baris hasil pencocokan Dukcapil. Klik 'Pilih' di
            # baris ber-NIK cocok DULU -> baru tombol 'Daftarkan dengan NIK' aktif
            # (sebelum 'Pilih' tombol itu disabled/<div>).
            langkah = "klik 'Pilih' pada baris data individu"
            log(langkah)
            await self._pilih_baris_individu(p.nik)

            # NIK valid & lolos validasi Dukcapil -> pakai jalur 'dengan NIK'.
            langkah = "klik 'Daftarkan dengan NIK'"
            log(langkah)
            await self._klik_tombol(L["btn_daftarkan_nik"])   # "Daftarkan dengan NIK"
            await page.wait_for_load_state("networkidle")
            await self._jeda()

            # --- Tunggu hasil: dialog sukses ATAU notif 'sudah menerima layanan' ---
            # Kedua notif bisa telat render; poll sampai salah satu muncul agar
            # tidak salah memvonis (sukses vs sudah-pernah-CKG).
            langkah = "tunggu hasil pendaftaran"
            log(langkah)
            sisa = 15000
            interval = 500
            while sisa > 0:
                if await page.get_by_text(
                        L["teks_sudah_layanan"], exact=False).count() > 0:
                    await self._shot("sudah_menerima_layanan")
                    raise SudahMenerimaLayananError(
                        "Individu sudah menerima layanan (sudah pernah CKG).")
                # Gagal ambil data identitas dari Dukcapil saat simpan akhir.
                if await page.get_by_text(
                        re.compile(L["teks_dukcapil_fetch"], re.IGNORECASE)
                        ).count() > 0:
                    await self._shot("gagal_dukcapil")
                    raise DukcapilFetchError(
                        "Gagal mengambil data identitas dari Dukcapil saat "
                        "simpan pendaftaran. Peserta perlu memperbarui data di "
                        "Dukcapil. Dilewati, tidak diulang.")
                if await page.get_by_text(
                        L["teks_berhasil"], exact=False).count() > 0:
                    break
                await page.wait_for_timeout(interval)
                sisa -= interval

            # --- BERHASIL: tangkap No. Tiket ---
            langkah = "tangkap No. Tiket"
            log(langkah)
            # No. Tiket sering muncul sepersekian detik setelah dialog sukses.
            # Baca tiket DULU (polling) baru screenshot, agar tidak false-negative
            # dan screenshot ikut menangkap tiket yang sudah ter-render.
            await self._jeda()
            no_tiket = await self._ekstrak_tiket(timeout_ms=12000)
            shot = await self._shot("berhasil_daftar")
            log("No. Tiket", no_tiket or "(tidak terbaca)")

            # --- tutup dialog ---
            langkah = "klik 'Tutup'"
            log(langkah)
            try:
                await self._klik_tombol(L["btn_tutup"], timeout=8000)
            except Exception:
                pass  # tidak fatal bila tombol Tutup tidak ada

            if not no_tiket:
                raise RuntimeError(
                    f"Pendaftaran tampak selesai tetapi No. Tiket tidak terbaca. "
                    f"Cek screenshot: {shot}")
            return no_tiket

        except LewatiPesertaError:
            # bukan kegagalan teknis (sudah-CKG / data tidak valid) - teruskan
            # apa adanya agar pemanggil bisa menandai baris & melanjutkan
            # (jangan dibungkus jadi RuntimeError).
            raise
        except Exception as e:
            shot = await self._shot("ERROR")
            raise RuntimeError(
                f"Gagal pada langkah '{langkah}': {type(e).__name__}: {e} "
                f"(screenshot: {shot})") from e

    # =====================================================================
    # KONFIRMASI HADIR (halaman /ckg-pendaftaran-individu)
    # =====================================================================
    async def buka_halaman_konfirmasi(self):
        """Pastikan berada di halaman 'Cari/Daftarkan Individu' (tempat filter &
        tabel data terdaftar). Bila tab aktif bukan halaman itu, navigasi ke URL-
        nya (sesi login dipakai dari Chrome via CDP)."""
        page = self._page
        url = S.KONFIRMASI["url"]
        if url not in (page.url or ""):
            await page.goto(url)
            await self._settle(timeout_ms=8000)   # halaman awal: beri waktu lebih
        await self._jeda()

    async def _pilih_filter_kolom(self, nilai: str = "NIK"):
        """Set dropdown filter pencarian (Nomor Tiket / NIK / Nama) ke `nilai`.

        Dropdown custom Vue: teks pilihan saat ini ada di div non-interaktif;
        klik div 'cursor-pointer' terdekat untuk membuka, lalu klik opsi yang
        teksnya PERSIS `nilai`.
        """
        page = self._page
        # 1) temukan kontrol via teks yang SEDANG terpilih (salah satu dari opsi)
        ctrl = None
        for cur in S.KONFIRMASI["opsi_filter_semua"]:
            loc = page.get_by_text(cur, exact=True).first
            try:
                if await loc.count() > 0 and await loc.is_visible():
                    ctrl = loc
                    # sudah terpilih sesuai target -> tak perlu ubah
                    if cur == nilai:
                        return
                    break
            except Exception:
                continue
        if ctrl is None:
            raise RuntimeError(
                "Dropdown filter (Nomor Tiket/NIK/Nama) tak ditemukan di halaman.")
        klik = ctrl.locator(
            "xpath=ancestor-or-self::*[contains(@class,'cursor-pointer')][1]")
        target = klik.first if await klik.count() > 0 else ctrl
        await target.click(timeout=6000)
        await self._jeda()
        # 2) klik opsi `nilai` (teks PERSIS)
        exact = re.compile(rf"^\s*{re.escape(nilai)}\s*$")
        for opt in (
            page.locator(
                "div[class*='cursor-pointer'][class*='hover:bg-gray-1']"
            ).filter(has_text=exact),
            page.locator(
                "div[class*='shadow-standard'] div[class*='cursor-pointer']"
            ).filter(has_text=exact),
            page.get_by_text(exact).locator("visible=true"),
            page.get_by_role("option", name=exact),
        ):
            try:
                if await opt.count() > 0:
                    await opt.first.click(timeout=5000)
                    await self._jeda()
                    print(f"[CKGBot] Filter pencarian -> {nilai}")
                    return
            except Exception:
                continue
        raise RuntimeError(f"Opsi filter '{nilai}' tak ditemukan setelah dropdown dibuka.")

    async def _cari_nik(self, nik: str):
        """Ketik NIK di textbox cari lalu picu pencarian (Enter)."""
        page = self._page
        box = page.get_by_placeholder(
            re.compile(S.KONFIRMASI["ph_cari"], re.I)).first
        if await box.count() == 0:
            # fallback: textbox terlihat pertama di area filter
            box = page.get_by_role("textbox").first
        await box.click(timeout=6000)
        try:
            await box.fill("", timeout=4000)
        except Exception:
            pass
        await box.fill(str(nik), timeout=6000)
        await box.press("Enter")
        await self._settle()      # cap pendek; hasil tabel ditunggu via polling
        await self._jeda()

    async def konfirmasi_hadir_satu(self, p, on_step=None,
                                    tanggal_filter: Optional[str] = None) -> str:
        """
        Konfirmasi kehadiran SATU peserta (cocokkan via NIK) di halaman
        /ckg-pendaftaran-individu.

        Langkah: set filter tanggal (bila `tanggal_filter` diisi) -> set dropdown
        filter = NIK -> ketik NIK -> di baris hasil klik 'Konfirmasi Hadir' ->
        popup 'Tandai Hadir' (centang + 'Hadir') -> verifikasi 'Sudah Hadir' ->
        tutup dialog. Kembalikan path screenshot bukti.

        tanggal_filter: ISO 'YYYY-MM-DD' (mis. tanggal daftar peserta). Tabel
            difilter per Tanggal Pemeriksaan; nilai ini menyesuaikan kalender
            filter agar baris peserta muncul. None = biarkan default (hari ini).

        Raise:
          - SudahHadirError    : baris sudah 'Sudah Hadir' (lewati, terminal).
          - TidakDitemukanError: NIK tak muncul di tabel (cek tanggal filter).
          - RuntimeError       : kegagalan teknis lain (dengan path screenshot).
        """
        page = self._page
        K = S.KONFIRMASI
        nama = (p.nama or "").strip()

        def log(nama_, info=""):
            if on_step:
                on_step(nama_, info)

        langkah = "buka halaman konfirmasi"
        try:
            log(langkah)
            await self.buka_halaman_konfirmasi()
            # tutup dialog/modal sisa dari peserta sebelumnya (bila ada) agar
            # filter & tabel bisa diklik.
            await self._tutup_dialog()

            # set filter tanggal sesuai tanggal daftar (agar baris peserta muncul)
            if tanggal_filter:
                langkah = "set filter tanggal"
                log(langkah, tanggal_filter)
                await self._set_tanggal_filter(tanggal_filter)

            langkah = "set filter = NIK"
            log(langkah)
            await self._pilih_filter_kolom(K["opsi_filter"])

            langkah = "cari NIK"
            log(langkah, p.nik)
            await self._cari_nik(p.nik)

            # cari baris hasil: poll hingga tombol 'Konfirmasi Hadir' / teks
            # 'Sudah Hadir' / tabel kosong terdeteksi.
            langkah = "temukan baris peserta"
            log(langkah)
            btn = await self._tunggu_baris_konfirmasi(p, timeout_ms=15000)

            langkah = "klik 'Konfirmasi Hadir'"
            log(langkah)
            await btn.click(timeout=8000)
            await self._jeda()

            # popup 'Tandai Hadir?': centang persetujuan -> klik 'Hadir'.
            langkah = "popup 'Tandai Hadir' (centang persetujuan + klik Hadir)"
            log(langkah)
            await self._popup_tandai_hadir()

            # verifikasi: baris berubah jadi 'Sudah Hadir' / toast berhasil
            langkah = "verifikasi hadir"
            log(langkah)
            ok = await self._verifikasi_hadir(timeout_ms=12000)
            shot = await self._shot("konfirmasi_hadir")
            log("bukti", shot)
            if not ok:
                raise RuntimeError(
                    f"Sudah klik 'Konfirmasi Hadir' tetapi status tidak berubah "
                    f"jadi 'Sudah Hadir'. Mungkin ada popup/field tambahan. "
                    f"Cek screenshot: {shot}")

            # tutup dialog sukses 'Berhasil Hadir' agar peserta berikutnya bersih.
            langkah = "tutup dialog sukses"
            log(langkah)
            await self._tutup_dialog()
            print(f"[CKGBot] Konfirmasi hadir OK (NIK {p.nik}, {nama}).")
            return shot

        except LewatiPesertaError:
            raise
        except Exception as e:
            shot = await self._shot("ERROR_konfirmasi")
            raise RuntimeError(
                f"Gagal pada langkah '{langkah}': {type(e).__name__}: {e} "
                f"(screenshot: {shot})") from e

    async def _tunggu_baris_konfirmasi(self, p, timeout_ms: int = 15000):
        """Poll tabel setelah filter NIK. Kembalikan locator tombol 'Konfirmasi
        Hadir' pada baris peserta. Raise SudahHadirError / TidakDitemukanError
        sesuai kondisi."""
        page = self._page
        K = S.KONFIRMASI
        nama = (p.nama or "").strip()
        btn_exact = re.compile(rf"^\s*{re.escape(K['btn_konfirmasi'])}\s*$", re.I)
        sudah_re = re.compile(K["teks_sudah_hadir"], re.I)
        kosong_re = re.compile(K["teks_kosong"], re.I)
        waited, interval = 0, 500
        while waited <= timeout_ms:
            konf = page.get_by_role("button", name=btn_exact)
            if await konf.count() == 0:
                konf = page.get_by_text(btn_exact).locator("visible=true")
            sudah = page.get_by_text(sudah_re).locator("visible=true")
            nk = await konf.count()
            ns = await sudah.count()

            if nk > 0:
                btn = konf.first
                # verifikasi nama pada baris yang sama (anti salah peserta) bila
                # ada >1 baris tersisa atau nama tersedia.
                if nama:
                    row = btn.locator(
                        "xpath=ancestor::tr[1] | ancestor::*[contains(@class,'row')"
                        " or contains(@class,'grid') or contains(@class,'flex')][1]")
                    try:
                        if await row.count() > 0:
                            txt = (await row.first.inner_text()).strip()
                            if txt and nama.lower() not in txt.lower():
                                # baris pertama bukan peserta kita: cari baris yg memuat nama
                                row2 = page.locator(
                                    "tr", has_text=re.compile(re.escape(nama), re.I)).first
                                b2 = row2.get_by_role(
                                    "button", name=btn_exact).first
                                if await b2.count() > 0:
                                    return b2
                                raise RuntimeError(
                                    f"Hasil filter NIK {p.nik} tidak memuat nama "
                                    f"'{nama}'. Cocokkan manual (jangan asal klik).")
                    except RuntimeError:
                        raise
                    except Exception:
                        pass
                return btn

            if ns > 0:
                # tak ada tombol konfirmasi & ada 'Sudah Hadir' -> sudah hadir
                await self._shot("sudah_hadir")
                raise SudahHadirError(
                    f"Peserta NIK {p.nik} sudah dikonfirmasi hadir.")

            # belum ada baris: cek empty-state
            try:
                if await page.get_by_text(kosong_re).locator(
                        "visible=true").count() > 0:
                    raise TidakDitemukanError(
                        f"NIK {p.nik} tidak ada di tabel pada tanggal filter. "
                        f"Cek tanggal pemeriksaan / Status Daftar.")
            except TidakDitemukanError:
                raise
            except Exception:
                pass
            await page.wait_for_timeout(interval)
            waited += interval
        # timeout tanpa baris apa pun -> anggap tak ditemukan
        raise TidakDitemukanError(
            f"NIK {p.nik} tak muncul dalam {timeout_ms // 1000}s "
            f"(cek tanggal filter / koneksi).")

    async def _popup_tandai_hadir(self):
        """Tangani popup 'Tandai Hadir?' setelah klik 'Konfirmasi Hadir':
        (Tanggal Kehadiran dibiarkan default = hari ini) -> centang checkbox
        persetujuan -> klik tombol 'Hadir' (yang baru aktif setelah dicentang).
        """
        page = self._page
        K = S.KONFIRMASI
        # tunggu popup muncul (judul 'Tandai Hadir')
        judul = page.get_by_text(re.compile(K["teks_popup"], re.I)).first
        try:
            await judul.wait_for(state="visible", timeout=8000)
        except Exception:
            print("[CKGBot] Popup 'Tandai Hadir' tak terdeteksi; lanjut coba centang.")
        # batasi semua aksi ke wadah dialog (hindari elemen tabel di belakang modal)
        root = page.locator(
            "[role=dialog], .swal2-popup, .modal-content, "
            "div[class*='modal'], div[class*='dialog']").filter(
            has=page.get_by_text(re.compile(K["teks_popup"], re.I))).first
        if await root.count() == 0:
            root = judul.locator(
                "xpath=ancestor::*[contains(@class,'modal') or contains(@class,'dialog')"
                " or @role='dialog'][1]")
        if await root.count() == 0:
            root = page      # fallback: seluruh halaman

        # 1) centang checkbox persetujuan (custom Vue: input bisa tersembunyi ->
        #    klik teks label dulu, lalu force-check + dispatch event bila perlu).
        pola = re.compile(K["chk_persetujuan"], re.I)
        tercentang = False
        try:
            await root.get_by_text(pola).first.click(timeout=4000)
            await self._jeda()
        except Exception:
            pass
        cb = root.get_by_role("checkbox").first
        try:
            if await cb.count() > 0:
                tercentang = await cb.is_checked()
        except Exception:
            tercentang = False
        if not tercentang and await cb.count() > 0:
            for cara in ("check", "js"):
                try:
                    if cara == "check":
                        await cb.check(force=True, timeout=3000)
                    else:
                        await cb.evaluate(
                            "el => { el.checked = true; "
                            "el.dispatchEvent(new Event('input', {bubbles:true})); "
                            "el.dispatchEvent(new Event('change', {bubbles:true})); }")
                    await self._jeda()
                    if await cb.is_checked():
                        tercentang = True
                        break
                except Exception:
                    continue
        if not tercentang:
            print("[CKGBot] PERINGATAN: checkbox persetujuan mungkin belum "
                  "tercentang; tombol 'Hadir' bisa tetap nonaktif.")

        # 2) klik 'Hadir' (PERSIS - bukan 'Konfirmasi Hadir' di tabel). Tombol
        #    baru aktif setelah checkbox dicentang; coba beberapa kali singkat.
        btn_re = re.compile(K["btn_hadir"], re.I)
        scope = root if hasattr(root, "get_by_role") else page
        for _ in range(6):
            btn = scope.get_by_role("button", name=btn_re).first
            if await btn.count() == 0:
                btn = scope.get_by_text(btn_re).locator("visible=true").first
            try:
                if await btn.count() > 0 and await btn.is_visible():
                    await btn.click(timeout=4000)
                    await self._jeda()
                    print("[CKGBot] Popup 'Tandai Hadir': klik 'Hadir'.")
                    return
            except Exception:
                pass
            await page.wait_for_timeout(400)
        raise RuntimeError(
            "Tombol 'Hadir' di popup tak bisa diklik (checkbox persetujuan "
            "mungkin belum tercentang sehingga tombol tetap nonaktif).")

    async def _verifikasi_hadir(self, timeout_ms: int = 12000) -> bool:
        """Poll sampai ada penanda berhasil ('Sudah Hadir' / toast berhasil)."""
        page = self._page
        pola = re.compile(S.KONFIRMASI["teks_berhasil"], re.I)
        waited, interval = 0, 500
        while waited <= timeout_ms:
            try:
                if await page.get_by_text(pola).locator(
                        "visible=true").count() > 0:
                    return True
            except Exception:
                pass
            await page.wait_for_timeout(interval)
            waited += interval
        return False

    async def _tutup_dialog(self, maks: int = 5):
        """Tutup dialog/modal yang sedang terbuka (mis. 'Berhasil Hadir').

        Klik tombol 'Tutup' bila ada; bila masih ada modal, tekan Escape. Diulang
        sampai tak ada modal terlihat atau `maks` percobaan. Non-fatal: bila tak
        ada dialog, langsung selesai. WAJIB dipanggil setelah sukses & sebelum
        memproses peserta berikutnya (dialog yang menggantung memblok klik tabel)."""
        page = self._page
        tutup_re = re.compile(S.KONFIRMASI["btn_tutup"], re.I)
        modal_sel = ("[role=dialog], .swal2-popup, .modal-content, "
                     "div[class*='modal'], div[class*='dialog']")
        for _ in range(maks):
            # 1) tombol 'Tutup' (paling bersih)
            try:
                btn = page.get_by_role("button", name=tutup_re).first
                if await btn.count() > 0 and await btn.is_visible():
                    await btn.click(timeout=3000)
                    await self._jeda()
                    continue
            except Exception:
                pass
            # 2) masih ada modal terlihat? -> Escape
            try:
                modal = page.locator(modal_sel).first
                if await modal.count() > 0 and await modal.is_visible():
                    await page.keyboard.press("Escape")
                    await page.wait_for_timeout(300)
                    continue
            except Exception:
                pass
            return   # tak ada dialog tersisa
        # upaya terakhir: Escape sekali lagi (tak fatal bila gagal)
        try:
            await page.keyboard.press("Escape")
        except Exception:
            pass

    # bulan singkat Bahasa Indonesia - format tampilan mx-datepicker filter:
    # "12 Jun 2026" / "08 Mei 2026" (hari NOL di depan, locale id).
    _BULAN_ID = ("Jan", "Feb", "Mar", "Apr", "Mei", "Jun",
                 "Jul", "Agu", "Sep", "Okt", "Nov", "Des")
    # toleransi ejaan Agustus antar-locale (Agu/Agt/Ags)
    _BULAN_ALT = {8: ("Agu", "Agt", "Ags")}

    def _tgl_cocok(self, tampilan: str, d) -> bool:
        """True bila teks tampilan datepicker (mis. '08 Mei 2026') = tanggal d."""
        t = (tampilan or "").lower()
        if str(d.year) not in t:
            return False
        if f"{d.day:02d}" not in t and f"{d.day} " not in t:
            return False
        kandidat = self._BULAN_ALT.get(d.month, (self._BULAN_ID[d.month - 1],))
        return any(b.lower() in t for b in kandidat)

    async def _set_tanggal_filter(self, iso_date: str):
        """Set kalender filter tanggal (mx-datepicker, satu-satunya di halaman)
        ke `iso_date` (YYYY-MM-DD). Lewati bila sudah menampilkan tanggal itu.

        Tabel 'Data Individu Terdaftar' difilter per Tanggal Pemeriksaan; agar
        baris peserta muncul saat dicari via NIK, tanggal filter harus = tanggal
        pemeriksaan/daftar peserta. Reuse navigasi `_pilih_tanggal_mx` (klik bulan
        via indeks -> tahan-locale)."""
        from datetime import datetime as _dt
        try:
            d = _dt.strptime(iso_date, "%Y-%m-%d")
        except (ValueError, TypeError):
            print(f"[CKGBot] Tanggal filter '{iso_date}' tak valid; lewati (pakai default).")
            return
        page = self._page
        root = page.locator(".mx-datepicker").first
        if await root.count() == 0:
            raise RuntimeError("Datepicker filter (.mx-datepicker) tak ditemukan di halaman.")
        try:
            cur = (await root.inner_text()).strip()
        except Exception:
            cur = ""
        if self._tgl_cocok(cur, d):
            print(f"[CKGBot] Filter tanggal sudah '{cur}'; tak perlu diubah.")
            return
        await self._pilih_tanggal_mx(root, d)
        # tampilan datepicker ter-update sinkron (client-side); tak perlu tunggu
        # jaringan di sini - pencarian NIK berikutnya akan memfilter ulang tabel.
        try:
            cur2 = (await root.inner_text()).strip()
        except Exception:
            cur2 = ""
        if not self._tgl_cocok(cur2, d):
            raise RuntimeError(
                f"Gagal set filter tanggal ke {iso_date} (tampilan masih '{cur2}').")
        print(f"[CKGBot] Filter tanggal -> {cur2}")
