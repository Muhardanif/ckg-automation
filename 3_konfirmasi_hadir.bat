@echo off
REM ===================================================================
REM KONFIRMASI HADIR semua peserta SUKSES di Excel.
REM Syarat: 1_mulai_chrome.bat sudah dijalankan, sudah LOGIN manual, buka
REM menu CKG Umum > Cari/Daftarkan Individu, FILTER TANGGAL = hari pemeriksaan,
REM dan file Excel dalam keadaan TERTUTUP.
REM ===================================================================
cd /d "%~dp0"

set "EXCEL=data\input\template_pendaftaran.xlsx"

echo === Konfirmasi hadir (hanya baris Status Daftar = SUKSES) ===
echo (Baris yang sudah HADIR akan dilewati.)
echo.
venv\Scripts\python.exe tools\konfirmasi_hadir.py --excel "%EXCEL%"

echo.
echo Selesai. Hasil (Status Hadir / Waktu Hadir) tertulis di: %EXCEL%
pause
