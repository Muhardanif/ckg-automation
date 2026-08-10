# CKG Automation — Design System (MASTER)

> **Sumber kebenaran (Source of Truth)** desain untuk semua halaman.
> Stack: **Tailwind CSS v4 + DaisyUI v5**. Tema: `ckg` (terang) & `ckg-dark` (gelap).
> Saat membangun/mengubah halaman, ikuti file ini. Penyimpangan per-halaman
> ditaruh di `design-system/pages/<nama-halaman>.md` (override Master).

Dihasilkan dengan ui-ux-pro-max:
- **Pattern:** Real-Time / Operations (tool otomasi, status-driven, data-dense tapi scannable)
- **Style:** Minimalism / Flat — bersih, WCAG AA, Tailwind 10/10
- **Color:** Medical Clinic — teal brand + health green (lihat §0 Brand)
- **Typography:** Plus Jakarta Sans (font wordmark logo) + JetBrains Mono untuk data numerik

---

## 0. Brand

Paket aset resmi ada di **`app/static/img/brand/`** (jangan ubah nama/pindahkan
isinya). Karena `/static` sudah di-mount ke `app/static`, aset langsung tersedia
di `/static/img/brand/...` — **tidak perlu mount tambahan** di `main.py`.

| Token | Hex | Dipakai untuk |
|-------|-----|----------------|
| `--ckg-teal` | `#0F766E` | warna utama logo → token `primary` (terang) |
| `--ckg-navy` | `#0B132B` | wordmark, permukaan gelap → token `neutral` (terang) |
| `--ckg-grey` | `#E5E7EB` | pemisah → token `base-300` (terang) |

Utility Tailwind `bg-ckg-navy` / `text-ckg-teal` / `border-ckg-grey` tersedia
(alias `--color-ckg-*` di `@theme`). Untuk komponen biasa **tetap pakai token
semantik** (`bg-primary`, `badge-success`) — hanya permukaan brand yang boleh
memakai `ckg-*` langsung.

`--ckg-navy` **tidak** dipakai sebagai `neutral` di tema gelap: nilainya nyaris
sama dengan `base-200` (`#0F172A`), jadi tombol neutral akan lenyap ke latar.

### Aset logo — pakai PNG, bukan SVG

| Kebutuhan | Berkas |
|-----------|--------|
| Sidebar (terang / gelap) | `img/brand/logo/ckg-logo-horizontal-{color,white}.png`, tinggi `h-10` |
| Landing `/` (terang / gelap) | `img/brand/logo/ckg-logo-stacked-{color,white}.png`, tinggi `h-28` |
| Favicon | `img/brand/favicon/favicon-{32,192}.png` |
| Apple touch icon | `img/brand/app-icon/ckg-app-icon-180.png` |

> ⚠ **SVG brand hanya sumber vektor, jangan dipakai lewat `<img>`.** Wordmark di
> dalamnya adalah `<text>` hidup ber-`font-family: Plus Jakarta Sans`. SVG yang
> dimuat sebagai `<img>` dirender di konteks terisolasi: font web halaman tidak
> berlaku di sana, hanya font yang **terinstal di sistem**. Di PC puskesmas tanpa
> Plus Jakarta Sans, "CKG AUTOMATION" akan diam-diam jatuh ke font sistem.
> PNG-nya 3000px — jauh lebih dari cukup untuk 40px, tetap tajam di layar retina.

Versi `color` memakai wordmark navy yang lenyap di latar gelap, jadi tiap logo
dipasang dua kali dengan class `.light-only` / `.dark-only` (lihat `theme.css`).

---

## 1. Palet Warna

Dipetakan ke token semantik DaisyUI (lihat `theme.css`). **Jangan pakai hex mentah di markup** — pakai class semantik (`bg-primary`, `text-error`, `badge-success`, dst).

> ⚠ **Angka di bawah dihasilkan mesin, bukan ditulis tangan.** Regenerasi dengan
> `venv\Scripts\python.exe tools/cek_kontras.py --markdown`, dan verifikasi
> dengan `tools/cek_kontras.py` (exit ≠ 0 bila ada pasangan yang gagal AA).
> Versi tulis-tangan sebelumnya meleset pada 7 dari 9 token — `info` diklaim
> 4.5:1 padahal 4.10:1 dan dipakai untuk teks normal di `alert-info`.

### Tema terang (`ckg`)

| Peran | Token DaisyUI | Hex | Teks di atasnya | Kontras |
|------|----------------|-----|------------------|---------|
| Primary | `primary` | `#0F766E` | `#FFFFFF` | 5.47:1 ✓ AA |
| Secondary | `secondary` | `#0E7490` | `#FFFFFF` | 5.36:1 ✓ AA |
| Accent | `accent` | `#15803D` | `#FFFFFF` | 5.02:1 ✓ AA |
| Neutral | `neutral` | `#0B132B` | `#F8FAFC` | 17.57:1 ✓ AA |
| Info | `info` | `#0369A1` | `#FFFFFF` | 5.93:1 ✓ AA |
| Success | `success` | `#15803D` | `#FFFFFF` | 5.02:1 ✓ AA |
| Warning | `warning` | `#F59E0B` | `#451A03` | 6.97:1 ✓ AA |
| Error | `error` | `#B91C1C` | `#FFFFFF` | 6.47:1 ✓ AA |
| Teks utama | `base-content` | `#0F172A` | — | 17.9:1 ✓ |
| Teks sekunder | `base-content/60` | (#6F747F) | — | 4.69:1 ✓ |
| Teks sekunder | `base-content/70` | (#575D6A) | — | 6.61:1 ✓ |

### Tema gelap (`ckg-dark`)

Bukan inversi: brand dinaikkan terangnya dan `-content`-nya digelapkan.

| Peran | Token DaisyUI | Hex | Teks di atasnya | Kontras |
|------|----------------|-----|------------------|---------|
| Primary | `primary` | `#2DD4BF` | `#042F2E` | 7.77:1 ✓ AA |
| Secondary | `secondary` | `#22D3EE` | `#083344` | 7.41:1 ✓ AA |
| Accent | `accent` | `#4ADE80` | `#052E16` | 8.55:1 ✓ AA |
| Neutral | `neutral` | `#334155` | `#F8FAFC` | 9.90:1 ✓ AA |
| Info | `info` | `#38BDF8` | `#082F49` | 6.48:1 ✓ AA |
| Success | `success` | `#4ADE80` | `#052E16` | 8.55:1 ✓ AA |
| Warning | `warning` | `#FBBF24` | `#451A03` | 8.97:1 ✓ AA |
| Error | `error` | `#F87171` | `#450A0A` | 5.84:1 ✓ AA |
| Teks utama | `base-content` | `#E2E8F0` | — | 11.9:1 ✓ |
| Teks sekunder | `base-content/60` | (#949CA8) | — | 5.28:1 ✓ |
| Teks sekunder | `base-content/70` | (#A7AFBA) | — | 6.61:1 ✓ |

### Permukaan & border

| Peran | Terang | Gelap | Catatan |
|------|--------|-------|---------|
| Latar halaman | `base-200` `#F1F5F9` | `#0F172A` | `body` |
| Permukaan/kartu | `base-100` `#FFFFFF` | `#1E293B` | kartu **lebih terang** dari latar di kedua tema |
| Pemisah dekoratif | `base-300` `#E5E7EB` | `#334155` | `--ckg-grey`; dikecualikan WCAG 1.4.11 |
| Border kontrol form | `--color-border-strong` `#64748B` | `#94A3B8` | wajib ≥ 3:1 (batas field harus terlihat) |

Checkbox/radio wajib memakai `checkbox-primary`/`radio-primary` (sudah ada di
macro): tanpa varian warna, DaisyUI membiarkan latar kotak transparan saat
tercentang sehingga status tercentang hanya ditandai glyph centang tipis.

**Aturan warna**
- `primary` = satu aksi utama per layar (Jalankan, Mulai, Upload).
- `error` khusus aksi destruktif/status gagal — **selalu** dipisah dari aksi normal.
- `warning` = amber, **teksnya gelap** (jangan putih) agar kontras.
- Warna **tidak boleh** jadi satu-satunya penanda makna → selalu sertakan ikon/teks.
  Macro `ui.status_run()` dan badge status di `peserta.html` sudah menerapkan ini.
- Opasitas teks minimum `\60` (mis. `text-base-content/60`). Di bawah itu gagal AA.
- **Jangan** pakai `-content/<opasitas>` di atas permukaan berwarna
  (mis. `text-primary-content/60` di navbar = 2.96:1, gagal). Kalau perlu redup,
  batasnya `/90`.
- Status panel Operasi: berjalan = `badge-warning`, berhenti = `badge-ghost`,
  sukses = `badge-success`, gagal = `badge-error`.

---

## 2. Typography & Font Pairing

| Peran | Font | Token |
|------|------|-------|
| Heading (h1–h4) | **Plus Jakarta Sans** 600/700 | `font-heading` |
| Body / label | **Plus Jakarta Sans** 400/500/600 | `font-sans` |
| Data numerik (NIK, No. Tiket, jumlah) | **JetBrains Mono** + `tabular-nums` | `font-mono` / class `.tabular` |

Plus Jakarta Sans dipakai untuk heading **dan** body karena ia font wordmark
logo: UI dan logo memakai huruf yang sama. Bobot 800 ikut diunduh — dipakai
`.stat-value` dan wordmark logo; tanpa berkas aslinya browser memalsukan
tebalnya (synthetic bold) dan hurufnya melebar.

**Font di-host sendiri**, bukan `@import` ke `fonts.googleapis.com`. Aplikasi ini
dipakai di jaringan puskesmas/dinkes yang bisa terisolasi dari internet; import
lintas-domain menahan render lalu jatuh ke font sistem. Berkas `.woff2` (subset
latin + latin-ext) ada di `app/static/fonts/`, `@font-face`-nya di
`design-system/fonts.css` (dibangkitkan `tools/ambil_font.py`, jangan diedit
manual), semuanya `font-display: swap`.

**Type scale** (rasio ~1.2, base 16px):

| Peran | Ukuran | Tailwind | line-height | weight |
|------|--------|----------|-------------|--------|
| Display | 36px | `text-4xl` | 1.15 | 700 |
| H1 | 30px | `text-3xl` | 1.2 | 700 |
| H2 | 24px | `text-2xl` | 1.25 | 600 |
| H3 | 20px | `text-xl` | 1.3 | 600 |
| H4 / label besar | 18px | `text-lg` | 1.4 | 600 |
| Body | 16px | `text-base` | 1.5–1.6 | 400 |
| Small / helper | 14px | `text-sm` | 1.5 | 400 |
| Caption | 12px | `text-xs` | 1.4 | 500 |

**Aturan**
- Body **minimal 16px** (hindari auto-zoom iOS, keterbacaan).
- Panjang baris teks panjang 60–75 karakter (`max-w-prose`).
- Hirarki dibangun lewat **ukuran + weight + spasi**, bukan warna saja.
- Kolom angka pakai `.tabular` agar tidak "geser" saat update.

---

## 3. Spacing Scale (ritme 4/8px)

| Token | px | Tailwind | Pemakaian |
|------|----|----------|-----------|
| 2xs | 4 | `1` | gap ikon-teks |
| xs | 8 | `2` | padding kecil, gap checkbox |
| sm | 12 | `3` | gap antar field |
| md | 16 | `4` | padding kartu, gap default |
| lg | 24 | `6` | padding kartu besar, jarak sub-section |
| xl | 32 | `8` | jarak antar section |
| 2xl | 48 | `12` | jarak blok besar / atas-bawah halaman |
| 3xl | 64 | `16` | hero / pemisah mayor |

**Radius** (token DaisyUI): field/btn `0.5rem`, card/modal `0.75rem`, pill = `rounded-full`.
**Container**: `max-w-7xl mx-auto px-4` — dinaikkan dari `5xl` karena tabel
Riwayat & Data Peserta punya 6–7 kolom dan tercekik di 1024px.
**Ritme vertikal section**: 16 / 24 / 32 / 48 sesuai tingkat hirarki.
**Shadow**: halus saja (`shadow-sm`/`--depth:1`) — sesuai gaya flat.

---

## 4. Breakpoint & Layout

Kerangka: **sidebar tetap** (`drawer lg:drawer-open`), bukan navbar horizontal.
Item navigasi sudah 5 dan akan bertambah; navbar memaksa memangkas label atau
menyembunyikan menu di balik "more".

| BP | Lebar | Aturan |
|----|-------|--------|
| base | <640 | 1 kolom, sidebar jadi drawer (hamburger di topbar) |
| `sm` | 640 | form 2 kolom, stats horizontal |
| `md` | 768 | — |
| `lg` | 1024 | **sidebar permanen**, grid panel 2 kolom |
| `xl`+ | 1280 | container `max-w-7xl` tetap |

- **Mobile-first**: tulis class dasar untuk layar kecil, naik dengan `sm:`/`lg:`.
- Tidak boleh horizontal-scroll; tabel lebar → bungkus `overflow-x-auto`.
- Grid wajib responsif: `grid-cols-1 sm:grid-cols-2 lg:grid-cols-4` (bukan kolom tetap).
- Tinggi layar penuh pakai `min-h-dvh`, bukan `100vh` (bilah alamat mobile).
- **Bahasa navigasi tanpa jargon internal.** "Operasi", bukan "Operasi (CDP)";
  CDP adalah detail implementasi, bukan konsep milik operator.

---

## 5. Komponen Dasar (DaisyUI v5)

> **Reusable:** macro Jinja siap pakai ada di `app/templates/_components.html`.
> Di template anak: `{% import "_components.html" as ui %}`, lalu mis.
> `{{ ui.button("Jalankan") }}`, `{{ ui.badge("Sukses", variant="success") }}`,
> `{{ ui.field("username", "Username", required=True) }}`,
> `{% call ui.card(title="Judul") %}…{% endcall %}`. Macro tersedia:
> `button`, `card`, `field` (input), `select`, `checkbox`, `badge`, `alert`,
> `steps`, `icon`, `empty_state`, `skeleton`, `status_run`, `paginasi`.
> **Jangan menyalin markup kartu/tombol/field** — pakai macro ini supaya warna &
> struktur konsisten dari satu sumber. Contoh markup mentah di bawah hanya rujukan.

> **Teks label di-escape.** Kirim `"Upload & Preview"`, **bukan**
> `"Upload &amp; Preview"` — entity HTML akan ter-escape dua kali dan tampil
> harfiah. Butuh markup di dalam label? `ui.checkbox(..., html=True)`.

### Tiga jebakan DaisyUI v5 yang sudah memakan korban

**1. `.label` BUKAN label field.** Di v5 `.label` adalah *teks bantuan*:
14px, `opacity 0.6`, dan `white-space: nowrap`. Dipakai sebagai pembungkus
field, ia membuat label tampak pudar, membuat `<input>` di dalamnya **mewarisi**
warna pudar itu, dan menolak membungkus teks sehingga menjebol layar 375px.
Pakai `ui.label_field()` + `ui.help_text()` (atau macro `field`/`select`).

**2. Class varian yang disusun dinamis tidak akan di-emit.** Macro membangun
`btn btn-{{ variant }}`; pemindai Tailwind membaca teks sumber, bukan hasil
render, jadi ia tak pernah melihat `btn-warning`. Semua varian di-safelist lewat
`@source inline(...)` di `theme.css` — **tambahkan di sana** setiap kali ada
nilai `variant` baru. Sebelum safelist ini, `btn-warning` dan `btn-neutral`
tampil abu-abu polos, dan varian yang kebetulan berfungsi hanya berfungsi karena
namanya tertulis di contoh kode MASTER.md ini yang ikut terpindai.

**3. Override komponen DaisyUI tidak boleh ditaruh di `@layer base`.** DaisyUI
meng-emit komponennya di layer `components`, yang menang atas `base`. Aturan
border `border-strong` sempat ditulis di dalam `@layer base` dan **diam-diam
tidak pernah berlaku**. Tulis override komponen sebagai CSS **tanpa layer** —
CSS tanpa layer selalu menang atas CSS ber-layer.

Ketiganya gagal tanpa error. `app/main.py` memeriksa sentinel varian saat
startup; sisanya hanya bisa ditangkap dengan melihat halaman sungguhan.

Gunakan komponen DaisyUI + token tema. Contoh siap-pakai:

### Tombol
```html
<button class="btn btn-primary">Jalankan Pendaftaran</button>
<button class="btn btn-outline">Sekunder</button>
<button class="btn btn-error">Hentikan</button>
<button class="btn btn-ghost btn-sm">Aksi kecil</button>

<!-- Async: kunci + spinner saat proses (cegah double-run) -->
<button class="btn btn-primary" disabled>
  <span class="loading loading-spinner loading-sm"></span> Memproses…
</button>
```
Aturan: satu `btn-primary` per kartu/layar; aksi destruktif `btn-error` terpisah;
tombol async **selalu** di-disable + spinner selama request.

### Sidebar (navigasi utama)
Didefinisikan sekali di `base.html`; halaman anak tidak menyentuhnya.
```html
<div class="drawer lg:drawer-open">
  <input id="drawerToggle" type="checkbox" class="drawer-toggle">
  <div class="drawer-content flex flex-col min-h-dvh">…</div>
  <div class="drawer-side">
    <nav id="sidebar" class="bg-base-100 border-r border-base-300 w-72">
      <ul class="menu">
        <li class="menu-title …">Menu utama</li>
        <li><a class="menu-active" aria-current="page">
          <span class="nav-ikon">…ikon…</span>
          <span><span class="nav-label">Label</span>
                <span class="text-xs text-base-content/70">Deskripsi singkat</span></span>
        </a></li>
      </ul>
    </nav>
  </div>
</div>
```
- Item menu **dua baris**: label + deskripsi singkat yang terlihat (bukan
  tooltip `title` — tooltip tak terjangkau layar sentuh). Deskripsi
  `text-xs text-base-content/70`.
- Halaman aktif ditandai `aria-current="page"` **dan** `menu-active` — gayanya
  di-override di `theme.css` ("Sidebar: navigasi utama"): latar primary 10% +
  bilah kiri primary + ikon `.nav-ikon` primary + label semibold. **Jangan**
  memakai `text-primary` sebagai warna teks item aktif: di tema terang primary
  di atas latar ber-tint hanya ~4.5:1, terlalu mepet.
- Setiap item wajib ikon + label teks — ikon tanpa label merusak discoverability.
- Topbar: layar sempit menampilkan **nama halaman aktif** (bukan brand — brand
  sudah di drawer & judul tab); desktop menampilkan penanda lokasi ringan
  (ikon + nama, `text-sm text-base-content/70`). Esc menutup drawer.
- Skip-link `#konten` harus jadi elemen fokus pertama.

### Kartu
```html
<div class="card bg-base-100 border border-base-300 shadow-sm">
  <div class="card-body gap-3">
    <h2 class="card-title">1. Pendaftaran (Batch)</h2>
    <p class="text-sm text-base-content/70">Deskripsi singkat tahap.</p>
    <div class="card-actions"><button class="btn btn-primary">Jalankan</button></div>
  </div>
</div>
```

### Form (label, input, validasi)
```html
<fieldset class="fieldset">
  <label class="label" for="kelompok">Kelompok Usia <span class="text-error">*</span></label>
  <select id="kelompok" class="select select-bordered w-full" required>…</select>

  <label class="label" for="username">Username portal</label>
  <input id="username" class="input input-bordered w-full" autocomplete="username" required>

  <p class="label text-error" role="alert">Pesan error di bawah field terkait.</p>
</fieldset>
```
Aturan: **label terlihat** (bukan placeholder saja) + `for/id`; field wajib diberi `*`;
error tepat di bawah field + `role="alert"`; input `min-height 44px` (sudah di base);
pakai `input-type`/`autocomplete` yang tepat.

### Alert / Feedback
```html
<div class="alert alert-success" role="status">✓ 12 peserta berhasil didaftarkan.</div>
<div class="alert alert-error" role="alert">Gagal membaca file Excel.</div>
```
Status live (polling) pakai `aria-live="polite"`. Toast auto-dismiss 3–5s.

### Badge status
```html
<span class="badge badge-success">Sukses</span>
<span class="badge badge-error">Gagal</span>
<span class="badge badge-warning">Berjalan</span>
<span class="badge badge-ghost">Idle</span>
```

### Progress (dengan aria)
```html
<progress class="progress progress-primary w-full" value="0" max="100"
          aria-label="Progres proses"></progress>
```

### Stats (dashboard counter)
```html
<div class="stats stats-vertical lg:stats-horizontal bg-base-100 border border-base-300 w-full">
  <div class="stat"><div class="stat-title">Total</div><div class="stat-value tabular">0</div></div>
  <div class="stat"><div class="stat-title">Sukses</div><div class="stat-value text-success tabular">0</div></div>
  <div class="stat"><div class="stat-title">Gagal</div><div class="stat-value text-error tabular">0</div></div>
</div>
```

### Tabel (preview data)
```html
<div class="overflow-x-auto">
  <table class="table table-zebra">
    <thead><tr><th scope="col">NIK</th><th scope="col">Nama</th>…</tr></thead>
    <tbody><tr><td class="tabular">…</td>…</tr></tbody>
  </table>
</div>
```

### Log live (Operasi)
```html
<pre class="bg-neutral text-neutral-content text-xs rounded-box p-3 h-80 overflow-auto whitespace-pre-wrap"
     aria-live="polite"></pre>
```
Saat kosong, tampilkan `ui.empty_state(...)` — bukan kotak hitam melompong.

### Empty state & skeleton
```jinja
{{ ui.empty_state("Belum ada proses dijalankan", "Log akan muncul di sini…") }}
{{ ui.skeleton(classes="h-9 w-16") }}
```
Angka yang belum dimuat ditampilkan sebagai **skeleton**, bukan `0`. Menampilkan
`0` lalu melompat ke `214` berarti sempat menampilkan data **salah**, bukan data
kosong.

---

## 6. Umpan Balik, Konfirmasi & Kegagalan

Bagian ini lahir dari audit: kelemahan terbesar aplikasi ini bukan warna atau
font, melainkan cara ia berperilaku saat ada yang salah.

### Status koneksi (WAJIB untuk data yang di-poll)
Semua polling lewat `ckg.mulaiPolling()` di `app/static/ui.js`. **Dilarang**
`catch (e) {}` kosong: kalau server mati, halaman akan membekukan angka terakhir
dan terus menampilkannya seolah masih hidup. Sediakan `<div id="koneksi" hidden
role="alert" class="alert alert-error">` dan oper id-nya lewat `elemenKoneksi`.
Polling berhenti saat tab tersembunyi dan mundur teratur (backoff) saat gagal.

### Bobot konfirmasi sepadan dengan konsekuensi
Pakai `ckg.konfirmasiAksi()`, bukan `confirm()` bawaan (bisa di-Enter tanpa dibaca).

| Konsekuensi | Contoh | Bentuk konfirmasi |
|------------|--------|-------------------|
| Tak ada / bisa diulang | Uji coba Pelayanan, Buka Chrome | Modal biasa, `varian: 'primary'` |
| Mengubah data di portal | Kirim sungguhan, Konfirmasi Hadir | Modal `varian: 'warning'` + rincian parameter |
| **Ireversibel** | SUBMIT + SELESAIKAN, Kosongkan antrian | Modal `varian: 'error'` + rincian + label tombol eksplisit ("Kunci data sekarang") |

Selalu sertakan `rincian: [...]` berisi parameter yang akan dipakai — operator
harus melihat *apa* yang akan terjadi, bukan hanya *bahwa* sesuatu akan terjadi.

### Aksi destruktif
Tombol destruktif **di-disable saat tak ada yang bisa dihancurkan** (mis.
"Hentikan" saat idle). Tombol merah yang selalu aktif melatih operator
mengabaikan warna merah.

### Kejujuran status
Proses yang dihentikan operator ≠ proses yang gagal. Rekam terpisah
(`dihentikan` vs `gagal`). Run yang menggantung karena server mati ditutup saat
startup (`db.tandai_run_tergantung`) supaya Riwayat tidak berbohong.

---

## 7. Checklist Pra-Rilis (wajib lulus)

- [ ] `venv\Scripts\python.exe tools/cek_kontras.py` exit 0.
- [ ] `npm run build:css` dijalankan setelah class baru ditambahkan.
- [ ] Tidak ada emoji sebagai ikon → pakai `ui.icon()` (Lucide).
- [ ] Kontras teks ≥ 4.5:1 (normal), border field & ikon ≥ 3:1.
- [ ] Diuji di **kedua tema** (`ckg` dan `ckg-dark`), bukan hanya terang.
- [ ] Semua field punya label terlihat + `for/id`; field wajib ditandai.
- [ ] Tombol async di-disable + spinner; tidak bisa double-submit.
- [ ] Aksi ireversibel memakai `konfirmasiAksi({ varian: 'error', … })` dengan label tombol yang menyebut akibatnya.
- [ ] Tak ada `catch {}` kosong pada fetch; status koneksi terlihat.
- [ ] Daftar kosong punya empty state; angka async punya skeleton.
- [ ] Target sentuh ≥ 44px; checkbox/radio diberi area klik cukup.
- [ ] Grid & nav responsif (375 / 768 / 1024); tanpa horizontal-scroll.
- [ ] Status dinamis pakai `aria-live`; error pakai `role="alert"`.
- [ ] Warna bukan satu-satunya penanda (sertakan ikon/teks).
- [ ] Fokus keyboard terlihat; skip-link ada; urutan tab = urutan visual.
- [ ] `prefers-reduced-motion` dihormati; transisi 150–300ms.

---

## 8. Setup & Build (Tailwind v4 + DaisyUI v5)

> **Status: SUDAH LIVE.** Tujuh template (`base/index/preview/dashboard/operasi/
> riwayat/riwayat_detail/peserta`) memakai komponen DaisyUI.
> `app/static/app.css` di-build dari `theme.css`.

Rebuild CSS setiap kali kelas di template atau `ui.js` berubah:
```bash
npm run build:css     # sekali (minified) + stamp mtime
npm run watch:css     # mode tonton saat mengembangkan
```

**Kenapa ini sering terlupa dan bagaimana dicegah.** Tailwind hanya meng-emit
class yang benar-benar ditemukan di sumber. Class baru yang belum di-build
**tidak ada** di CSS, dan halaman rusak diam-diam tanpa satu pun error. Ini
sudah pernah terjadi: komponen `steps` hilang dari tiga halaman. Tiga lapis
pengaman sekarang:

1. `4_buka_aplikasi.bat` menjalankan `npm run build:css` otomatis bila `node_modules` ada.
2. `app/main.py` (`_peringatkan_css_basi`) memperingatkan di konsol saat startup
   bila `app.css` lebih tua dari template/`theme.css`.
3. `npm run build:css` diakhiri script `stamp` — Tailwind tidak menulis ulang
   berkas yang identik byte-per-byte, jadi mtime-nya harus dimajukan manual
   agar pengaman (2) tidak beralarm palsu.

Konfigurasi yang berlaku:
- `package.json` → bin `tailwindcss` dari `@tailwindcss/cli`; input `./design-system/theme.css`,
  output `./app/static/app.css`.
- v4 **tidak pakai** `tailwind.config.js`/`content[]` — sumber kelas via
  `@source "../app/templates"` **dan** `@source "../app/static/ui.js"` di
  `theme.css`. `ui.js` wajib disebut: modal konfirmasi dibangun dari JavaScript.
- `base.html`: `data-theme` diset skrip inline di `<head>` (dari `localStorage`,
  fallback `prefers-color-scheme`) supaya tak berkedip terang→gelap.
- `@plugin "daisyui" { themes: false; }` → hanya `ckg` & `ckg-dark` yang di-emit.

Font: `tools/ambil_font.py` (butuh internet sekali) → `app/static/fonts/*.woff2`
+ `design-system/fonts.css`.

Saat menulis markup baru, **patuhi token & komponen di atas** + checklist §7.
