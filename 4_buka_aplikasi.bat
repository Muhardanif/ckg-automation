@echo off
REM ===================================================================
REM Buka APLIKASI WEB CKG Automation (UI ber-tombol).
REM   - Halaman "1. Daftar (Upload)"        : pendaftaran via login
REM   - Halaman "2/3. Hadir & Pelayanan"    : Konfirmasi Hadir & Pelayanan (CDP)
REM Catatan: untuk tahap Hadir/Pelayanan, jalankan dulu 1_mulai_chrome.bat,
REM LOGIN portal, buka menu CKG, dan TUTUP file Excel.
REM ===================================================================
cd /d "%~dp0"

REM buka browser ke halaman operasi (server menyusul nyala)
start "" http://127.0.0.1:8000/operasi

echo === Menjalankan server web di http://127.0.0.1:8000 ===
echo (Biarkan jendela ini terbuka selama memakai aplikasi. Tekan Ctrl+C untuk berhenti.)
echo.
venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000

pause
