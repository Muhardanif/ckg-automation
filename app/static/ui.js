/* =========================================================================
   CKG Automation — perkakas UI bersama.

   Dua hal yang diperbaiki dari versi sebelumnya:

   1. Polling yang gagal diam-diam. Kode lama membungkus fetch dengan
      `catch (e) {}` kosong: kalau server mati, halaman membekukan angka
      terakhir dan terus menampilkannya seolah masih hidup. Untuk alat yang
      mengirim data peserta ke portal pemerintah, "diam-diam menampilkan data
      basi" adalah mode kegagalan yang berbahaya. `mulaiPolling` memunculkan
      status koneksi eksplisit dan mundur teratur (backoff) saat gagal.

   2. `confirm()` bawaan untuk aksi yang mengunci data peserta secara final.
      Dialog native bisa di-Enter tanpa dibaca. `konfirmasiAksi` menampilkan
      ringkasan dampak, dan untuk aksi ireversibel menuntut pengetikan kata
      konfirmasi.
   ========================================================================= */
(function () {
  'use strict';

  // ---------------------------------------------------------------------
  // Polling dengan indikator koneksi + backoff + berhenti saat tab tak aktif
  // ---------------------------------------------------------------------
  var JEDA_DASAR = 1500;
  var JEDA_MAKS = 15000;
  var GAGAL_SEBELUM_LAPOR = 2; // 1 kegagalan bisa sekadar reload server

  /**
   * @param {string|function():string} url  endpoint JSON. Boleh fungsi, supaya
   *        pemanggil bisa menyusun kursor (mis. '?sejak=N') tiap putaran.
   * @param {function(Object)} saatData  dipanggil dengan payload
   * @param {Object} opsi          { jeda, elemenKoneksi }
   */
  function mulaiPolling(url, saatData, opsi) {
    opsi = opsi || {};
    var jedaDasar = opsi.jeda || JEDA_DASAR;
    var kotak = opsi.elemenKoneksi
      ? document.getElementById(opsi.elemenKoneksi) : null;

    var gagalBeruntun = 0;
    var timer = null;
    var terakhirSukses = null;

    function gambarKoneksi() {
      if (!kotak) return;
      if (gagalBeruntun < GAGAL_SEBELUM_LAPOR) {
        kotak.hidden = true;
        return;
      }
      var detik = terakhirSukses
        ? Math.round((Date.now() - terakhirSukses) / 1000) : null;
      kotak.hidden = false;
      kotak.textContent = detik === null
        ? 'Tidak dapat menghubungi server. Angka di halaman ini belum pernah dimuat.'
        : 'Terputus dari server. Angka di bawah terakhir diperbarui '
          + detik + ' detik lalu — jangan dijadikan patokan.';
    }

    function jadwalkan(jeda) {
      clearTimeout(timer);
      timer = setTimeout(putaran, jeda);
    }

    function putaran() {
      // Tab tersembunyi: tak ada yang membaca. Cek lagi nanti.
      if (document.hidden) { jadwalkan(jedaDasar); return; }

      fetch(typeof url === 'function' ? url() : url, { cache: 'no-store' })
        .then(function (r) {
          if (!r.ok) throw new Error('HTTP ' + r.status);
          return r.json();
        })
        .then(function (data) {
          gagalBeruntun = 0;
          terakhirSukses = Date.now();
          gambarKoneksi();
          try { saatData(data); } catch (e) { console.error(e); }
          jadwalkan(jedaDasar);
        })
        .catch(function (err) {
          gagalBeruntun += 1;
          gambarKoneksi();
          console.warn('Polling gagal (' + gagalBeruntun + '):', err.message);
          // Mundur teratur: jangan membanjiri server yang sedang bermasalah.
          var jeda = Math.min(jedaDasar * Math.pow(2, gagalBeruntun - 1), JEDA_MAKS);
          jadwalkan(jeda);
        });
    }

    // Segera segarkan begitu operator kembali ke tab.
    document.addEventListener('visibilitychange', function () {
      if (!document.hidden) jadwalkan(0);
    });

    putaran();
    return { segarkan: function () { jadwalkan(0); } };
  }

  // ---------------------------------------------------------------------
  // Modal konfirmasi
  // ---------------------------------------------------------------------
  function el(tag, kelas, teks) {
    var n = document.createElement(tag);
    if (kelas) n.className = kelas;
    if (teks) n.textContent = teks;
    return n;
  }

  /**
   * Tampilkan dialog konfirmasi. Mengembalikan Promise<boolean>.
   *
   * @param {Object} o
   *   judul    {string}
   *   pesan    {string}   kalimat konsekuensi, ditulis lugas
   *   rincian  {string[]} daftar parameter yang akan dipakai (opsional)
   *   varian   {'primary'|'warning'|'error'}
   *   tombol   {string}   label tombol konfirmasi
   */
  function konfirmasiAksi(o) {
    return new Promise(function (selesai) {
      var dlg = el('dialog', 'modal');
      var kotak = el('div', 'modal-box max-w-lg');

      kotak.appendChild(el('h3', 'font-heading font-semibold text-lg', o.judul));
      kotak.appendChild(el('p', 'py-2 text-base-content/80', o.pesan));

      if (o.rincian && o.rincian.length) {
        var ul = el('ul', 'text-sm bg-base-200 rounded-box p-3 my-2 space-y-1');
        o.rincian.forEach(function (baris) {
          ul.appendChild(el('li', 'flex gap-2', '• ' + baris));
        });
        kotak.appendChild(ul);
      }

      var aksi = el('div', 'modal-action');
      var batal = el('button', 'btn btn-ghost', 'Batal');
      var ya = el('button', 'btn btn-' + (o.varian || 'primary'),
                  o.tombol || 'Lanjutkan');

      function tutup(hasil) {
        dlg.close();
        dlg.remove();
        selesai(hasil);
      }
      batal.addEventListener('click', function () { tutup(false); });
      ya.addEventListener('click', function () { tutup(true); });
      // Esc / klik luar = batal (jalan keluar selalu tersedia).
      dlg.addEventListener('cancel', function (e) { e.preventDefault(); tutup(false); });

      aksi.appendChild(batal);
      aksi.appendChild(ya);
      kotak.appendChild(aksi);

      var latar = el('form', 'modal-backdrop');
      latar.method = 'dialog';
      latar.appendChild(el('button', '', 'tutup'));
      latar.addEventListener('submit', function () { tutup(false); });

      dlg.appendChild(kotak);
      dlg.appendChild(latar);
      document.body.appendChild(dlg);
      dlg.showModal();
      batal.focus();
    });
  }

  window.ckg = { mulaiPolling: mulaiPolling, konfirmasiAksi: konfirmasiAksi };
})();
