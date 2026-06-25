"""
Isi kolom 'Nilai Default (ISI)' di PEMETAAN_PELAYANAN_FULL.xlsx dengan SARAN
default (baseline sehat / tanpa-risiko / normal) untuk di-review user.

Prinsip:
  - Faktor risiko (Ya/Tidak)        -> 'Tidak'
  - Frekuensi gejala jiwa           -> 'Tidak sama sekali'
  - Barthel/ADL                     -> 'Mandiri' / 'Terkendali teratur'
  - Pemeriksaan klinis              -> 'Normal' / 'Tidak ada ...'
  - Field angka & data per-peserta  -> dikosongkan, ditandai '(dari Excel/alat)'
  - Item sensitif (perlu putusan)   -> diisi saran + catatan 'CEK'

Cocokkan via substring nama sheet (sheet ter-truncate 31 char). Jalankan:
  venv\\Scripts\\python.exe tools\\isi_default_pemetaan.py
"""
import os

import openpyxl

XLSX = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "data", "output", "PEMETAAN_PELAYANAN_FULL.xlsx")

EXCEL = "(dari Excel/alat)"

# key = substring nama form (cocok ke sheet). value = {sq(int): (default, catatan)}.
DEFAULTS = {
    "Demografi Lansia": {
        100: (EXCEL, "Status Perkawinan dari registrasi"),
        101: ("Non disabilitas", ""),
    },
    "Faktor Risiko Kanker Usus": {100: ("Tidak", ""), 101: ("Tidak", "")},
    "Faktor Risiko TB": {100: ("Tidak batuk", "")},
    "Hati": {s: ("Tidak", "") for s in range(100, 109)},
    "Kanker Leher Rahim": {100: ("Ya", "CEK: gating IVA; 'Ya' utk wanita pernah menikah")},
    "Kesehatan Jiwa": {s: ("Tidak sama sekali", "") for s in (100, 101, 102, 103)},
    "Penapisan Risiko Kanker Paru": {s: ("Tidak", "") for s in (100, 102, 103, 104, 105)},
    "Perilaku Merokok": {100: ("Tidak", ""), 107: ("Tidak", "")},
    "Tingkat Aktivitas Fisik": {
        100: ("Ya", "CEK: skor aktivitas fisik"),
        103: ("Tidak", "CEK"), 106: ("Ya", "CEK"),
        109: ("Tidak", "CEK"), 112: ("Tidak", "CEK"), 115: ("Tidak", "CEK"),
    },
    "Gizi (BB": {100: (EXCEL, ""), 101: (EXCEL, ""), 102: (EXCEL, "")},
    "Gula Darah": {100: ("Tidak", ""), 102: (EXCEL, ""), 104: (EXCEL, ""), 105: (EXCEL, "")},
    "Tekanan Darah": {100: ("Tidak", ""), 102: (EXCEL, ""), 103: (EXCEL, ""),
                      104: (EXCEL, ""), 105: (EXCEL, "")},
    "SKILAS Penurunan Kognitif": {100: ("Ya", ""), 101: ("Benar semua", ""), 102: ("Ya", "")},
    "SKILAS Mobilisasi": {100: ("Ya", "CEK polaritas: 'mampu berdiri'")},
    "SKILAS Malnutrisi": {100: ("Tidak", ""), 101: ("Tidak", ""), 102: ("Tidak", "")},
    "Pemeriksaan Gejala De": {100: ("Tidak", ""), 101: ("Tidak", "")},  # SKILAS Depresi (dropdown)
    "Pemeriksaan Gangguan Fungsio": {       # Barthel Index
        100: ("Terkendali teratur", ""), 101: ("Mandiri", ""), 102: ("Mandiri", ""),
        103: ("Mandiri", ""), 104: ("Mandiri", ""), 105: ("Mandiri", ""),
        106: ("Mandiri", ""), 107: ("Mandiri", ""), 108: ("Mandiri", ""), 109: ("Mandiri", ""),
    },
    "Skrining Telinga dan Mata": {
        100: ("Tidak ada serumen impaksi", ""), 101: ("Tidak ada infeksi telinga", ""),
        102: ("Normal", ""), 104: ("Normal (visus 6/6 - 6/12)", ""), 109: ("Normal", ""),
    },
    "Skrining Karies dan Gigi Hilang": {100: ("Tidak", ""),
                                        101: ("Tidak", "CEK: lansia sering ada gigi hilang")},
    "Skrining Penyakit Periodontal": {100: ("Tidak", ""), 101: ("Tidak", "")},
    "Hasil Pemeriksaan - Skrining Ja": {100: ("Normal", ""), 101: ("Normal", "")},
    "Skrining Kanker Payudara": {100: ("SADANIS", "CEK: SADANIS vs USG")},
}


def main():
    wb = openpyxl.load_workbook(XLSX)
    terisi, takcocok = 0, []
    for ws in wb.worksheets:
        if ws.title == "Daftar Form":
            continue
        # cari key DEFAULTS yg jadi prefix/substring judul sheet
        key = next((k for k in DEFAULTS if ws.title.startswith(k[:31]) or k[:28] in ws.title), None)
        if key is None:
            takcocok.append(ws.title)
            continue
        dmap = DEFAULTS[key]
        for row in ws.iter_rows(min_row=2):
            sq = row[1].value                       # kolom 'sq'
            if sq in dmap:
                val, cat = dmap[sq]
                row[5].value = val                  # 'Nilai Default (ISI)'
                if cat:
                    old = row[7].value or ""
                    row[7].value = (old + " | " + cat).strip(" |") if old else cat
                terisi += 1
    wb.save(XLSX)
    print(f"[OK] {terisi} default terisi di {XLSX}")
    if takcocok:
        print("[!] sheet tak tercocokkan:", takcocok)


if __name__ == "__main__":
    main()
