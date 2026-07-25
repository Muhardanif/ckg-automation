@echo off
REM ===================================================================
REM Buka APLIKASI WEB CKG Automation (UI ber-tombol).
REM   - Halaman "Operasi"   : Pendaftaran, Konfirmasi Hadir & Pelayanan
REM   - Halaman "Riwayat"   : audit trail proses yang pernah dijalankan
REM Catatan: untuk tahap Hadir/Pelayanan, jalankan dulu 1_mulai_chrome.bat,
REM LOGIN portal, buka menu CKG, dan TUTUP file Excel.
REM ===================================================================
cd /d "%~dp0"

REM -------------------------------------------------------------------
REM Rebuild CSS bila node_modules ada. Tailwind hanya meng-emit class yang
REM benar-benar dipakai template, jadi class baru TIDAK berlaku sampai
REM di-build ulang. Ini pernah membuat indikator langkah hilang diam-diam.
REM Mesin operator yang tak punya Node akan melewati langkah ini; app/main.py
REM tetap memperingatkan bila app.css lebih tua dari template.
REM -------------------------------------------------------------------
if exist node_modules (
  echo === Membangun ulang CSS ^(npm run build:css^) ===
  call npm run build:css
  echo.
)

REM buka browser ke halaman operasi (server menyusul nyala)
start "" http://127.0.0.1:8000/operasi

echo === Menjalankan server web di http://127.0.0.1:8000 ===
echo (Biarkan jendela ini terbuka selama memakai aplikasi. Tekan Ctrl+C untuk berhenti.)
echo.
venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000

pause
