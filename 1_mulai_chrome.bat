@echo off
REM ===================================================================
REM Buka Chrome dengan remote-debugging untuk otomasi pendaftaran CKG.
REM Setelah ini: LOGIN manual ke portal, buka CKG Umum - Cari/Daftarkan
REM Individu, lalu jalankan 2_jalankan_batch.bat
REM ===================================================================

set "CHROME=C:\Program Files\Google\Chrome\Application\chrome.exe"
if not exist "%CHROME%" set "CHROME=C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"
if not exist "%CHROME%" (
  echo [GAGAL] chrome.exe tidak ditemukan di lokasi standar.
  echo Edit file ini dan sesuaikan baris "set CHROME=..." dengan lokasi Chrome Anda.
  pause
  exit /b 1
)

start "" "%CHROME%" --remote-debugging-port=9222 --user-data-dir="C:\chrome-ckg-debug"

echo.
echo Chrome dibuka dengan remote-debugging (port 9222).
echo.
echo Langkah berikutnya:
echo   1. LOGIN manual ke https://sehatindonesiaku.kemkes.go.id (termasuk CAPTCHA)
echo   2. Buka menu: CKG Umum  -  Cari/Daftarkan Individu
echo   3. Tutup file Excel template_pendaftaran.xlsx bila terbuka
echo   4. Jalankan: 2_jalankan_batch.bat
echo.
pause
