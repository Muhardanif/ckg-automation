# CKG Automation — Design System (MASTER)

> **Sumber kebenaran (Source of Truth)** desain untuk semua halaman.
> Stack target: **Tailwind CSS v4 + DaisyUI v5**. Tema: `ckg` (light).
> Saat membangun/mengubah halaman, ikuti file ini. Penyimpangan per-halaman
> ditaruh di `design-system/pages/<nama-halaman>.md` (override Master).

Dihasilkan dengan ui-ux-pro-max:
- **Pattern:** Real-Time / Operations (tool otomasi, status-driven, data-dense tapi scannable)
- **Style:** Minimalism / Flat — bersih, light, WCAG AAA, Tailwind 10/10
- **Color:** Medical Clinic — teal kesehatan + health green (selaras brand teal lama)
- **Typography:** Corporate Trust — Lexend + Source Sans 3 (best-for: healthcare/government/accessibility)

---

## 1. Palet Warna

Dipetakan ke token semantik DaisyUI (lihat `theme.css`). **Jangan pakai hex mentah di markup** — pakai class semantik (`bg-primary`, `text-error`, `badge-success`, dst).

| Peran | Token DaisyUI | Hex | Teks di atasnya | Kontras |
|------|----------------|-----|------------------|---------|
| Latar halaman | `base-200` | `#F1F5F9` | `base-content` | — |
| Permukaan/kartu | `base-100` | `#FFFFFF` | `base-content` | — |
| Border/divider | `base-300` | `#E2E8F0` | — | — |
| Teks utama | `base-content` | `#0F172A` | — | 16:1 ✓ |
| Teks sekunder | `base-content/70` | (#475569) | — | 7:1 ✓ |
| **Primary** (aksi utama) | `primary` | `#0E7490` | `#FFFFFF` | 4.8:1 ✓ AA |
| Secondary | `secondary` | `#0F766E` | `#FFFFFF` | 4.9:1 ✓ AA |
| **Accent** (highlight sehat) | `accent` | `#15803D` | `#FFFFFF` | 4.7:1 ✓ AA |
| Neutral (UI gelap) | `neutral` | `#1E293B` | `#F8FAFC` | 14:1 ✓ |
| Info | `info` | `#0284C7` | `#FFFFFF` | 4.5:1 ✓ AA |
| Success (Sukses) | `success` | `#15803D` | `#FFFFFF` | 4.7:1 ✓ AA |
| Warning (Perhatian) | `warning` | `#F59E0B` | `#451A03` (gelap) | 8:1 ✓ |
| Error (Gagal/Hapus) | `error` | `#DC2626` | `#FFFFFF` | 4.0:1 (besar/bold) |

**Aturan warna**
- `primary` = satu aksi utama per layar (Jalankan, Mulai, Upload).
- `error` khusus aksi destruktif/status gagal — **selalu** dipisah dari aksi normal.
- `warning` = amber, **teksnya gelap** (jangan putih) agar kontras.
- Warna **tidak boleh** jadi satu-satunya penanda makna → selalu sertakan ikon/teks
  (mis. badge "Gagal" + ikon, bukan sekadar merah).
- Status panel Operasi: berjalan = `badge-warning`, berhenti = `badge-ghost`,
  sukses = `badge-success`, gagal = `badge-error`.

---

## 2. Typography & Font Pairing

| Peran | Font | Token |
|------|------|-------|
| Heading (h1–h4) | **Lexend** 600/700 | `font-heading` |
| Body / label | **Source Sans 3** 400/500/600 | `font-sans` |
| Data numerik (NIK, No. Tiket, jumlah) | **JetBrains Mono** + `tabular-nums` | `font-mono` / class `.tabular` |

Import font sudah ada di `theme.css`. Lexend dipilih karena dirancang untuk
keterbacaan (reading proficiency) — cocok untuk tool program kesehatan pemerintah.

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
**Container**: `max-w-5xl mx-auto px-4` (≈ konsisten dengan layout sekarang).
**Ritme vertikal section**: 16 / 24 / 32 / 48 sesuai tingkat hirarki.
**Shadow**: halus saja (`shadow-sm`/`--depth:1`) — sesuai gaya flat.

---

## 4. Breakpoint & Layout

| BP | Lebar | Aturan |
|----|-------|--------|
| base | <640 | 1 kolom, nav collapse (hamburger) |
| `sm` | 640 | form 2 kolom |
| `md` | 768 | nav inline |
| `lg` | 1024 | grid stats 4 kolom, panel 2 kolom |
| `xl`+ | 1280 | container max-w-5xl tetap |

- **Mobile-first**: tulis class dasar untuk layar kecil, naik dengan `sm:`/`lg:`.
- Tidak boleh horizontal-scroll; tabel lebar → bungkus `overflow-x-auto`.
- Grid wajib responsif: `grid-cols-1 sm:grid-cols-2 lg:grid-cols-4` (bukan kolom tetap).

---

## 5. Komponen Dasar (DaisyUI v5)

> **Reusable:** macro Jinja siap pakai ada di `app/templates/_components.html`.
> Di template anak: `{% import "_components.html" as ui %}`, lalu mis.
> `{{ ui.button("Jalankan") }}`, `{{ ui.badge("Sukses", variant="success") }}`,
> `{{ ui.field("username", "Username", required=True) }}`,
> `{% call ui.card(title="Judul") %}…{% endcall %}`. Macro tersedia:
> `button`, `card`, `field` (input), `select`, `checkbox`, `badge`, `alert`.
> **Jangan menyalin markup kartu/tombol/field** — pakai macro ini supaya warna &
> struktur konsisten dari satu sumber. Contoh markup mentah di bawah hanya rujukan.

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

### Navbar
```html
<div class="navbar bg-primary text-primary-content">
  <div class="max-w-5xl mx-auto w-full px-4 flex-wrap gap-2">
    <span class="text-lg font-semibold mr-4">CKG Automation</span>
    <!-- mobile: dropdown; desktop: menu inline -->
    <a class="btn btn-ghost btn-sm" aria-current="page">Operasi (CDP)</a>
    ...
  </div>
</div>
```
Halaman aktif ditandai `aria-current="page"` + highlight. ≤5 item utama.

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

---

## 6. Checklist Pra-Rilis (wajib lulus)

- [ ] Tidak ada emoji sebagai ikon → pakai SVG (Lucide/Heroicons).
- [ ] Kontras teks ≥ 4.5:1 (normal), ikon/UI ≥ 3:1.
- [ ] Semua field punya label terlihat + `for/id`; field wajib ditandai.
- [ ] Tombol async di-disable + spinner; tidak bisa double-submit.
- [ ] Target sentuh ≥ 44px; checkbox/radio diberi area klik cukup.
- [ ] Grid & nav responsif (375 / 768 / 1024); tanpa horizontal-scroll.
- [ ] Status dinamis pakai `aria-live`; error pakai `role="alert"`.
- [ ] Warna bukan satu-satunya penanda (sertakan ikon/teks).
- [ ] Fokus keyboard terlihat; urutan tab = urutan visual.
- [ ] `prefers-reduced-motion` dihormati; transisi 150–300ms.

---

## 7. Setup & Build (Tailwind v4 + DaisyUI v5)

> **Status: SUDAH LIVE.** Kelima template (`base/index/preview/dashboard/operasi`)
> sudah memakai komponen DaisyUI. `app/static/app.css` di-build dari `theme.css`.

Rebuild CSS setiap kali kelas di template berubah:
```bash
npm run build:css     # sekali (minified)
npm run watch:css     # mode tonton saat mengembangkan
```
Konfigurasi yang berlaku:
- `package.json` → bin `tailwindcss` dari `@tailwindcss/cli`; input `./design-system/theme.css`,
  output `./app/static/app.css`.
- v4 **tidak pakai** `tailwind.config.js`/`content[]` — sumber kelas via `@source
  "../app/templates"` di `theme.css` (auto-scan). File config v3 sudah dihapus.
- `base.html`: `<html lang="id" data-theme="ckg">` + `<link rel="stylesheet" href="/static/app.css">`.
- `@plugin "daisyui" { themes: false; }` → hanya tema `ckg` yang di-emit.

Saat menulis markup baru, **patuhi token & komponen di atas** + checklist §6.
