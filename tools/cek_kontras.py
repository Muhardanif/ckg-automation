"""
Hitung rasio kontras WCAG untuk token warna tema, terang dan gelap.

Alasan ada: tabel kontras di design-system/MASTER.md pernah ditulis tangan dan
meleset pada 7 dari 9 token — satu di antaranya (`info`) diklaim lolos AA
padahal 4.10:1, dan dipakai untuk teks normal di alert. Angka desain harus
dihitung, bukan diingat.

Pakai:
    venv\\Scripts\\python.exe tools/cek_kontras.py            # tabel + exit 1 bila ada yang gagal
    venv\\Scripts\\python.exe tools/cek_kontras.py --markdown # potongan tabel untuk MASTER.md

Ambang WCAG 2.1:
    teks normal (<18.66px bold / <24px)  : >= 4.5:1  (AA)
    teks besar                            : >= 3.0:1  (AA)
    komponen UI & grafis non-teks         : >= 3.0:1  (AA)
"""
from __future__ import annotations

import sys

# Konsol Windows default cp1252 dan meledak pada "✓". Tabel ini memang untuk
# ditempel ke Markdown, jadi paksa UTF-8 alih-alih membuang simbolnya.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

AA_NORMAL = 4.5
AA_BESAR = 3.0


def _luminansi_kanal(c: int) -> float:
    s = c / 255
    return s / 12.92 if s <= 0.03928 else ((s + 0.055) / 1.055) ** 2.4


def luminansi(hexs: str) -> float:
    h = hexs.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return (0.2126 * _luminansi_kanal(r)
            + 0.7152 * _luminansi_kanal(g)
            + 0.0722 * _luminansi_kanal(b))


def kontras(a: str, b: str) -> float:
    la, lb = luminansi(a), luminansi(b)
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


def campur(fg: str, bg: str, alpha: float) -> str:
    """Warna hasil `fg` dengan opasitas `alpha` di atas `bg` (mis. text-base-content/70)."""
    f, b = fg.lstrip("#"), bg.lstrip("#")
    return "#" + "".join(
        f"{round(int(f[i:i + 2], 16) * alpha + int(b[i:i + 2], 16) * (1 - alpha)):02x}"
        for i in (0, 2, 4)
    )


# ---------------------------------------------------------------------------
# Sumber kebenaran token: harus SAMA dengan design-system/theme.css.
# ---------------------------------------------------------------------------
TERANG = {
    "base-100": "#ffffff", "base-200": "#f1f5f9", "base-300": "#e5e7eb",  # --ckg-grey
    "border-strong": "#64748b",  # border kontrol form (input/select) — WCAG 1.4.11
    "base-content": "#0f172a",
    "primary": "#0f766e", "primary-content": "#ffffff",   # --ckg-teal
    "secondary": "#0e7490", "secondary-content": "#ffffff",
    "accent": "#15803d", "accent-content": "#ffffff",
    "neutral": "#0b132b", "neutral-content": "#f8fafc",   # --ckg-navy
    "info": "#0369a1", "info-content": "#ffffff",
    "success": "#15803d", "success-content": "#ffffff",
    "warning": "#f59e0b", "warning-content": "#451a03",
    "error": "#b91c1c", "error-content": "#ffffff",
}

GELAP = {
    "base-100": "#1e293b", "base-200": "#0f172a", "base-300": "#334155",
    "border-strong": "#94a3b8",  # border kontrol form (input/select) — WCAG 1.4.11
    "base-content": "#e2e8f0",
    "primary": "#2dd4bf", "primary-content": "#042f2e",
    "secondary": "#22d3ee", "secondary-content": "#083344",
    "accent": "#4ade80", "accent-content": "#052e16",
    "neutral": "#334155", "neutral-content": "#f8fafc",
    "info": "#38bdf8", "info-content": "#082f49",
    "success": "#4ade80", "success-content": "#052e16",
    "warning": "#fbbf24", "warning-content": "#451a03",
    "error": "#f87171", "error-content": "#450a0a",
}

PERAN = ["primary", "secondary", "accent", "neutral", "info", "success",
         "warning", "error"]


def kasus(tema: dict) -> list[tuple[str, str, str, float]]:
    """(deskripsi, fg, bg, ambang) untuk semua pasangan yang benar-benar dipakai."""
    out: list[tuple[str, str, str, float]] = []
    permukaan = tema["base-100"]

    # teks utama & sekunder di kartu dan di latar halaman
    for nama_bg, bg in (("base-100", permukaan), ("base-200", tema["base-200"])):
        out.append((f"base-content di {nama_bg}", tema["base-content"], bg, AA_NORMAL))
        for a in (60, 70):
            out.append((f"base-content/{a} di {nama_bg}",
                        campur(tema["base-content"], bg, a / 100), bg, AA_NORMAL))

    # tombol/badge/alert solid: <peran>-content di atas <peran>
    for p in PERAN:
        out.append((f"{p}-content di atas {p}", tema[f"{p}-content"], tema[p], AA_NORMAL))

    # teks berwarna di atas permukaan kartu (text-error, text-success, ...)
    for p in ("error", "success", "info", "primary"):
        out.append((f"text-{p} di base-100", tema[p], permukaan, AA_NORMAL))

    # Border kontrol form: WCAG 1.4.11 menuntut 3:1 karena batas field harus
    # bisa dilihat. `base-300` sengaja TIDAK diuji di sini — ia dipakai sebagai
    # pemisah/divider dekoratif antar kartu, yang dikecualikan 1.4.11 (batas
    # kartu bukan satu-satunya penanda; kartu sudah dibedakan oleh warna
    # permukaan). Menggelapkan base-300 sampai 3:1 akan membuat setiap kartu
    # terkurung garis abu tebal.
    for nama_bg, bg in (("base-100", permukaan), ("base-200", tema["base-200"])):
        out.append((f"border-strong (input) di {nama_bg}",
                    tema["border-strong"], bg, AA_BESAR))
    return out


def jalankan(nama: str, tema: dict) -> list[tuple[str, float, float]]:
    gagal = []
    print(f"\n=== Tema {nama} ===")
    print(f"{'pasangan':42}{'rasio':>8}{'ambang':>8}   status")
    for desk, fg, bg, ambang in kasus(tema):
        r = kontras(fg, bg)
        ok = r >= ambang
        if not ok:
            gagal.append((desk, r, ambang))
        print(f"{desk:42}{r:8.2f}{ambang:8.1f}   {'OK' if ok else 'GAGAL'}")
    return gagal


def markdown(tema: dict) -> None:
    print("| Peran | Token DaisyUI | Hex | Teks di atasnya | Kontras |")
    print("|------|----------------|-----|------------------|---------|")
    for p in PERAN:
        r = kontras(tema[f"{p}-content"], tema[p])
        tanda = "✓ AA" if r >= AA_NORMAL else "✗ GAGAL"
        print(f"| {p.capitalize()} | `{p}` | `{tema[p].upper()}` | "
              f"`{tema[f'{p}-content'].upper()}` | {r:.2f}:1 {tanda} |")
    r = kontras(tema["base-content"], tema["base-100"])
    print(f"| Teks utama | `base-content` | `{tema['base-content'].upper()}` | — | {r:.1f}:1 ✓ |")
    for a in (60, 70):
        c = campur(tema["base-content"], tema["base-100"], a / 100)
        r = kontras(c, tema["base-100"])
        print(f"| Teks sekunder | `base-content/{a}` | ({c.upper()}) | — | {r:.2f}:1 "
              f"{'✓' if r >= AA_NORMAL else '✗'} |")


def main() -> int:
    if "--markdown" in sys.argv:
        print("<!-- Terang -->")
        markdown(TERANG)
        print("\n<!-- Gelap -->")
        markdown(GELAP)
        return 0

    gagal = jalankan("terang (ckg)", TERANG) + jalankan("gelap (ckg-dark)", GELAP)
    if gagal:
        print(f"\n{len(gagal)} pasangan GAGAL ambang WCAG AA:")
        for desk, r, ambang in gagal:
            print(f"  - {desk}: {r:.2f}:1 (butuh {ambang}:1)")
        return 1
    print("\nSemua pasangan lolos ambang WCAG AA.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
