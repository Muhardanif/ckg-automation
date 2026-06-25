"""
TRIAL: daftarkan SATU peserta ke portal SATUSEHAT/Sehat IndonesiaKu via Playwright
yang MENEMPEL ke sesi Chrome yang sudah login manual (connect_over_cdp).

Pakai ini untuk uji coba SEBELUM scale ke batch. Mode non-headless, jeda ~1 detik,
screenshot tiap langkah, dan logging detail agar ketahuan macet di langkah mana.

--------------------------------------------------------------------------------
CARA PAKAI (Windows / PowerShell)
--------------------------------------------------------------------------------
1) Tutup SEMUA jendela Chrome dulu. Lalu jalankan Chrome dengan remote debugging
   + profil khusus (agar tidak bentrok dengan Chrome biasa):

   & "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe" `
       --remote-debugging-port=9222 `
       --user-data-dir="C:\\chrome-ckg-debug"

   (Jika Chrome ada di Program Files (x86), sesuaikan path-nya.)

2) Di jendela Chrome itu: buka https://sehatindonesiaku.kemkes.go.id ,
   LOGIN MANUAL (termasuk CAPTCHA), lalu buka menu:
   CKG Umum > Cari/Daftarkan Individu. Biarkan halaman ini terbuka.

3) Verifikasi remote-debugging hidup: buka http://localhost:9222/json/version
   di tab lain — harus muncul JSON.

4) Jalankan trial (ganti NIK dengan NIK test yang VALID/terdaftar):

   venv\\Scripts\\python.exe tools\\trial_daftar.py --nik 3201234567890123

--------------------------------------------------------------------------------
"""
import argparse
import asyncio
import os
import sys
from datetime import date

# agar bisa `import app...` saat dijalankan sebagai skrip dari folder tools/
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.automation.ckg_bot import CKGBot          # noqa: E402
from app.automation import selectors as S          # noqa: E402
from app.schema import Peserta, KelompokUsia       # noqa: E402


def log(msg: str):
    print(f"[TRIAL] {msg}", flush=True)


def buat_peserta_dummy(nik: str) -> Peserta:
    """
    Peserta dummy untuk trial JALUR MANUAL (bypass Cek NIK/Dukcapil).
    EDIT nilai di sini sesuai data uji Anda. Semua field diisi manual ke portal,
    jadi tidak bergantung pada validasi Dukcapil.
    """
    return Peserta(
        nik=nik,                             # dipakai hanya bila field NIK masih aktif
        nama="BUDI TRIAL OTOMASI",
        tgl_lahir="1990-01-15",
        jenis_kelamin="L",
        kelompok_usia=KelompokUsia.DEWASA,
        no_wa="81234567890",                 # tanpa 0/+62 di depan (portal sudah +62)
        # --- data pendukung (Step 2). Teks HARUS sama dgn opsi dropdown portal. ---
        status_pernikahan="Belum Kawin",     # TODO sesuaikan dgn opsi dropdown portal
        disabilitas="Tidak ada",             # TODO sesuaikan
        pekerjaan="Lainnya",                 # TODO sesuaikan
        alamat_domisili=None,                # dilewati dulu (kemungkinan cascading)
        detail_alamat="Jl. Uji Coba No. 1 RT 001 RW 002",
        tanggal_pemeriksaan=date.today().isoformat(),
    )


def _flag_excel(args, peserta, no_tiket=None, status=None):
    """Tulis hasil (No. Tiket/Status/Waktu) ke baris Excel peserta, bila --excel."""
    if not args.excel or not peserta.baris_sumber:
        return
    from app.excel_hasil import tulis_hasil
    ok, pesan = tulis_hasil(args.excel, peserta.baris_sumber, no_tiket=no_tiket,
                            status=status, header_row=args.header_row)
    if ok:
        log(f"Excel di-flag (baris {peserta.baris_sumber}): "
            f"Tiket={no_tiket or '-'} Status={status}")
    else:
        log(f"PERINGATAN: gagal menulis flag ke Excel - {pesan} "
            f"(No. Tiket {no_tiket or '-'} TETAP tercatat di portal).")


async def jalankan(peserta: Peserta, args):
    log(f"Peserta: NIK={peserta.nik} | Nama={peserta.nama} | "
        f"TglLahir={peserta.tgl_lahir} | WA={peserta.no_wa or peserta.no_hp}")
    log(f"Menyambung ke Chrome di {args.cdp} ...")

    bot = CKGBot(headless=False, delay_ms=1000, cdp_url=args.cdp)
    try:
        await bot.connect_to_browser()
    except Exception as e:
        log(f"GAGAL connect ke Chrome: {type(e).__name__}: {e}")
        log("Pastikan langkah 1-3 di header file sudah dilakukan.")
        return 1

    def on_step(nama, info=""):
        log(f"  -> {nama}" + (f": {info}" if info else ""))

    log("Mulai proses pendaftaran satu peserta...")
    try:
        no_tiket = await bot.daftar_satu(peserta, on_step=on_step)
        log("=" * 50)
        log(f"BERHASIL! No. Tiket = {no_tiket}")
        log(f"Screenshot bukti ada di: {os.path.abspath('data/output/screenshots')}")
        log("=" * 50)
        # WAJIB: flag baris Excel agar tidak didaftarkan ulang.
        _flag_excel(args, peserta, no_tiket=no_tiket, status="SUKSES")
        return 0
    except Exception as e:
        log("=" * 50)
        log(f"BERHENTI karena gagal: {e}")
        log("Buka screenshot 'ERROR_*.png' untuk melihat kondisi halaman saat gagal.")
        log("Cek juga komentar '# TODO verifikasi selector' di ckg_bot.py /selectors.py")
        log("=" * 50)
        _flag_excel(args, peserta, status=f"GAGAL: {str(e)[:200]}")
        return 2
    finally:
        await bot.stop()   # mode CDP: tidak menutup Chrome Anda


def muat_peserta(args) -> Peserta:
    """Ambil peserta dari Excel (--excel) baris ke-N, atau dummy bila tak ada."""
    if args.excel:
        from app.readers import baca_excel
        ps = baca_excel(args.excel, KelompokUsia(args.kelompok),
                        header_row=args.header_row)
        if not ps:
            raise SystemExit(f"Tidak ada data terbaca di {args.excel}.")
        idx = args.baris - 1
        if idx < 0 or idx >= len(ps):
            raise SystemExit(
                f"--baris {args.baris} di luar rentang (terbaca {len(ps)} peserta).")
        peserta = ps[idx]
        # PROTEKSI ANTI-DOBEL: bila baris ini sudah punya No. Tiket di Excel,
        # jangan didaftarkan ulang (kecuali --paksa).
        from app.excel_hasil import baca_tiket
        tiket = baca_tiket(args.excel, peserta.baris_sumber, args.header_row)
        if tiket and not args.paksa:
            raise SystemExit(
                f"Baris {args.baris} (NIK {peserta.nik}, {peserta.nama}) SUDAH "
                f"terdaftar (No. Tiket {tiket}). Tidak dijalankan ulang. "
                f"Gunakan --paksa bila benar-benar ingin mendaftarkan lagi.")
        log(f"Memakai data REAL dari {args.excel} baris ke-{args.baris}.")
        return peserta
    log("Memakai data DUMMY (tidak ada --excel).")
    return buat_peserta_dummy(args.nik)


def main():
    ap = argparse.ArgumentParser(description="Trial pendaftaran 1 peserta CKG (CDP).")
    ap.add_argument("--excel", default="",
                    help="Path file Excel data real (mis. data/input/template_pendaftaran.xlsx).")
    ap.add_argument("--baris", type=int, default=1,
                    help="Baris data ke-berapa yang didaftarkan (1 = baris pertama). Default 1.")
    ap.add_argument("--kelompok", default="dewasa",
                    help="Kelompok usia: bayi/balita/dewasa/lansia. Default dewasa.")
    ap.add_argument("--header-row", dest="header_row", type=int, default=0,
                    help="Indeks baris header Excel (0 = baris pertama). Default 0.")
    ap.add_argument("--nik", default="3201234567890123",
                    help="NIK utk data dummy (dipakai hanya bila --excel kosong).")
    ap.add_argument("--cdp", default=S.CDP_URL,
                    help=f"URL Chrome remote-debugging (default {S.CDP_URL}).")
    ap.add_argument("--paksa", action="store_true",
                    help="Tetap daftarkan walau baris itu sudah punya No. Tiket di Excel.")
    args = ap.parse_args()

    peserta = muat_peserta(args)

    # Pra-cek konsistensi NIK vs Tgl Lahir / Jenis Kelamin (anti-tolak Dukcapil).
    from app.readers import cek_konsistensi_nik
    for w in cek_konsistensi_nik(peserta):
        log(f"PERINGATAN DATA: {w}")

    rc = asyncio.run(jalankan(peserta, args))
    sys.exit(rc)


if __name__ == "__main__":
    main()
