"""
Unduh font brand dari Google Fonts lalu simpan sebagai woff2 lokal.

Kenapa self-host: aplikasi ini dipakai di jaringan puskesmas/dinkes yang bisa
terisolasi dari internet. Selama theme.css memakai `@import` ke
fonts.googleapis.com, teks menunggu permintaan lintas-domain yang gagal saat
offline — render tertahan lalu jatuh ke font sistem.

Menghasilkan:
  app/static/fonts/*.woff2   -- berkas font (subset latin + latin-ext)
  design-system/fonts.css    -- @font-face yang menunjuk ke berkas di atas

Jalankan ulang hanya bila daftar font/berat di FAMILIES berubah:
    venv\\Scripts\\python.exe tools/ambil_font.py
Lalu rebuild CSS: npm run build:css
"""
from __future__ import annotations

import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FONT_DIR = ROOT / "app" / "static" / "fonts"
OUT_CSS = ROOT / "design-system" / "fonts.css"

# Subset yang dipakai bahasa Indonesia. Sisanya (cyrillic/greek/vietnamese)
# dibuang supaya bundel kecil.
KEEP_SUBSETS = {"latin", "latin-ext"}

FAMILIES = [
    # Font brand: dipakai untuk teks isi DAN heading (lihat --font-sans /
    # --font-heading di theme.css). Bobot 800 diperlukan karena wordmark logo
    # dan `.stat-value` memakainya; tanpa berkas aslinya browser memalsukan
    # tebalnya (synthetic bold) dan hurufnya melebar.
    ("Plus Jakarta Sans", [400, 500, 600, 700, 800]),
    # 700 diperlukan: `.stat-value` memakai font-weight 800 dan class `.tabular`
    # memaksa font mono. Tanpa bobot tebal asli, browser memalsukan tebalnya
    # (synthetic bold) dan angka dashboard tampak tipis serta melebar.
    ("JetBrains Mono", [400, 500, 600, 700]),
]

# UA browser modern -> Google membalas dengan woff2 (bukan ttf untuk UA lama).
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

HEADER = """/* =========================================================================
   Font self-hosted — subset latin + latin-ext.
   DIBANGKITKAN OLEH tools/ambil_font.py — jangan diedit manual.

   Berkas woff2 ada di app/static/fonts/ dan disajikan oleh StaticFiles.
   `font-display: swap` dipakai supaya teks tampil dengan font sistem lebih
   dulu, bukan tak terlihat (FOIT), sambil font brand dimuat.
   ========================================================================= */
"""


def _ambil(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()


def _url_css() -> str:
    bagian = [
        f"family={urllib.parse.quote(nama)}:wght@{';'.join(str(w) for w in berat)}"
        for nama, berat in FAMILIES
    ]
    return "https://fonts.googleapis.com/css2?" + "&".join(bagian) + "&display=swap"


def main() -> int:
    FONT_DIR.mkdir(parents=True, exist_ok=True)

    print(f"[1/3] Ambil daftar @font-face dari Google Fonts...")
    try:
        css = _ambil(_url_css()).decode("utf-8")
    except Exception as e:
        print(f"GAGAL: tidak bisa menghubungi fonts.googleapis.com ({e})")
        print("Butuh internet sekali saja; setelah itu font sudah lokal.")
        return 1

    # Tiap @font-face didahului komentar nama subset, mis. "/* latin */".
    blok = re.findall(r"/\*\s*([\w-]+)\s*\*/\s*(@font-face\s*\{[^}]*\})", css)
    if not blok:
        print("GAGAL: format balasan Google Fonts tak dikenali.")
        return 1

    print(f"[2/3] Unduh woff2 (subset: {', '.join(sorted(KEEP_SUBSETS))})...")
    faces, dipakai = [], set()
    for subset, isi in blok:
        if subset not in KEEP_SUBSETS:
            continue
        fam = re.search(r"font-family:\s*'([^']+)'", isi).group(1)
        berat = re.search(r"font-weight:\s*(\d+)", isi).group(1)
        url = re.search(r"url\((https://[^)]+\.woff2)\)", isi).group(1)
        rentang = re.search(r"unicode-range:\s*([^;]+);", isi).group(1).strip()

        nama_berkas = f"{fam.lower().replace(' ', '-')}-{berat}-{subset}.woff2"
        tujuan = FONT_DIR / nama_berkas
        if not tujuan.exists():
            tujuan.write_bytes(_ambil(url))
        dipakai.add(nama_berkas)
        faces.append((fam, berat, nama_berkas, rentang, subset))
        print(f"      {nama_berkas:44} {tujuan.stat().st_size / 1024:6.1f} KB")

    if not faces:
        print("GAGAL: tak ada subset yang cocok.")
        return 1

    # Buang woff2 yatim dari proses sebelumnya (mis. berat yang sudah dihapus).
    for lama in FONT_DIR.glob("*.woff2"):
        if lama.name not in dipakai:
            lama.unlink()
            print(f"      hapus yatim: {lama.name}")

    print(f"[3/3] Tulis {OUT_CSS.relative_to(ROOT)}...")
    bagian = [HEADER]
    for fam, berat, nama_berkas, rentang, subset in faces:
        bagian.append(
            f"/* {subset} */\n"
            f"@font-face {{\n"
            f"  font-family: '{fam}';\n"
            f"  font-style: normal;\n"
            f"  font-weight: {berat};\n"
            f"  font-display: swap;\n"
            f"  src: url('/static/fonts/{nama_berkas}') format('woff2');\n"
            f"  unicode-range: {rentang};\n"
            f"}}"
        )
    OUT_CSS.write_text("\n".join(bagian) + "\n", encoding="utf-8")

    total = sum(p.stat().st_size for p in FONT_DIR.glob("*.woff2"))
    print(f"\nSelesai: {len(faces)} @font-face, total {total / 1024:.0f} KB.")
    print("Langkah berikutnya: npm run build:css")
    return 0


if __name__ == "__main__":
    sys.exit(main())
