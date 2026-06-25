@echo off
REM ===================================================================
REM Jalankan pendaftaran BATCH semua baris di Excel.
REM Syarat: 1_mulai_chrome.bat sudah dijalankan, sudah LOGIN manual, dan
REM file Excel dalam keadaan TERTUTUP.
REM ===================================================================
cd /d "%~dp0"

set "EXCEL=data\input\template_pendaftaran.xlsx"

echo === Pra-cek data (NIK vs Tgl Lahir / Jenis Kelamin) ===
venv\Scripts\python.exe tools\cek_data.py --excel "%EXCEL%"

echo.
echo === Menjalankan batch pendaftaran ===
echo (Baris yang sudah punya No. Tiket akan dilewati.)
echo.
venv\Scripts\python.exe tools\jalankan_batch.py --excel "%EXCEL%"

echo.
echo Selesai. Hasil (No. Tiket / Status) tertulis di: %EXCEL%
pause
