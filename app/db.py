"""
Lapisan database (SQLite + SQLAlchemy).

Menggantikan penyimpanan in-memory agar data peserta & status submit
PERSISTEN lintas restart server. Berisi:
  - definisi model ORM (Batch, PesertaRow)
  - konversi ke/dari dataclass `Peserta` (DTO yang dipakai reader & bot)
  - helper CRUD ringkas yang dipakai main.py & runner.py

Catatan keamanan: file DB (data/ckg.db) berisi NIK & data kesehatan.
Sudah dimasukkan ke .gitignore — jangan commit.
"""
import os
from datetime import datetime
from typing import List, Optional

from sqlalchemy import (
    create_engine, String, Integer, DateTime, ForeignKey, JSON, func, select
)
from sqlalchemy.orm import (
    DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker, Session
)

from .schema import Peserta, KelompokUsia, StatusSubmit

# --- lokasi file DB ---
DATA_DIR = "data"
DB_PATH = os.path.join(DATA_DIR, "ckg.db")
os.makedirs(DATA_DIR, exist_ok=True)

# check_same_thread=False karena runner berjalan di thread terpisah.
engine = create_engine(
    f"sqlite:///{DB_PATH}",
    echo=False,
    future=True,
    connect_args={"check_same_thread": False},
)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False, class_=Session)


class Base(DeclarativeBase):
    pass


class Batch(Base):
    """Satu sesi upload (satu file Excel)."""
    __tablename__ = "batch"

    id: Mapped[int] = mapped_column(primary_key=True)
    nama_file: Mapped[str] = mapped_column(String(255))
    kelompok_usia: Mapped[str] = mapped_column(String(20))
    dibuat: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    peserta: Mapped[List["PesertaRow"]] = relationship(
        back_populates="batch", cascade="all, delete-orphan"
    )


class Run(Base):
    """Satu kali proses dijalankan — baris audit trail.

    Dashboard hanya menampilkan proses yang SEDANG berjalan; begitu selesai,
    jejaknya hilang. Tabel ini menyimpan siapa menjalankan apa, dengan
    parameter apa, kapan, dan hasilnya — supaya kesalahan bisa ditelusuri
    mundur (mis. "siapa yang menjalankan SUBMIT+SELESAIKAN kemarin sore?").

    `operator` diisi dari user OS: aplikasi ini sengaja tanpa login karena
    hanya diikat ke 127.0.0.1 dan dipakai satu operator per laptop.
    """
    __tablename__ = "run"

    id: Mapped[int] = mapped_column(primary_key=True)
    jenis: Mapped[str] = mapped_column(String(30), index=True)   # daftar|hadir|pelayanan|chrome
    label: Mapped[str] = mapped_column(String(120))
    operator: Mapped[str] = mapped_column(String(120), default="")
    perintah: Mapped[Optional[str]] = mapped_column(String(1000))
    parameter: Mapped[dict] = mapped_column(JSON, default=dict)

    mulai: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, index=True)
    selesai: Mapped[Optional[datetime]] = mapped_column(DateTime)

    # berjalan | sukses | gagal | dihentikan
    status: Mapped[str] = mapped_column(String(20), default="berjalan", index=True)
    returncode: Mapped[Optional[int]] = mapped_column(Integer)
    ringkasan: Mapped[Optional[str]] = mapped_column(String(500))

    jumlah_total: Mapped[int] = mapped_column(Integer, default=0)
    jumlah_sukses: Mapped[int] = mapped_column(Integer, default=0)
    jumlah_gagal: Mapped[int] = mapped_column(Integer, default=0)

    @property
    def durasi_detik(self) -> Optional[int]:
        if not self.selesai:
            return None
        return int((self.selesai - self.mulai).total_seconds())


class PesertaRow(Base):
    """Satu peserta CKG yang persisten di DB."""
    __tablename__ = "peserta"

    id: Mapped[int] = mapped_column(primary_key=True)
    batch_id: Mapped[Optional[int]] = mapped_column(ForeignKey("batch.id"))

    nik: Mapped[str] = mapped_column(String(32), index=True, default="")
    nama: Mapped[str] = mapped_column(String(255), default="")
    tgl_lahir: Mapped[Optional[str]] = mapped_column(String(20))
    jenis_kelamin: Mapped[Optional[str]] = mapped_column(String(2))
    kelompok_usia: Mapped[str] = mapped_column(String(20))
    no_hp: Mapped[Optional[str]] = mapped_column(String(40))
    alamat: Mapped[Optional[str]] = mapped_column(String(500))

    # dict pemeriksaan disimpan sebagai JSON (SQLite menyimpannya sebagai TEXT).
    pemeriksaan: Mapped[dict] = mapped_column(JSON, default=dict)

    baris_sumber: Mapped[Optional[int]] = mapped_column(Integer)
    file_sumber: Mapped[Optional[str]] = mapped_column(String(255))

    status_submit: Mapped[str] = mapped_column(
        String(20), default=StatusSubmit.BELUM.value, index=True
    )
    keterangan: Mapped[Optional[str]] = mapped_column(String(500))
    waktu_submit: Mapped[Optional[str]] = mapped_column(String(40))
    bukti_screenshot: Mapped[Optional[str]] = mapped_column(String(500))

    percobaan: Mapped[int] = mapped_column(Integer, default=0)  # jumlah upaya submit
    dibuat: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    batch: Mapped[Optional[Batch]] = relationship(back_populates="peserta")

    # ----- konversi -----
    def to_dataclass(self) -> Peserta:
        return Peserta(
            nik=self.nik or "",
            nama=self.nama or "",
            tgl_lahir=self.tgl_lahir,
            jenis_kelamin=self.jenis_kelamin,
            kelompok_usia=KelompokUsia(self.kelompok_usia),
            no_hp=self.no_hp,
            alamat=self.alamat,
            pemeriksaan=self.pemeriksaan or {},
            baris_sumber=self.baris_sumber,
            file_sumber=self.file_sumber,
            status_submit=StatusSubmit(self.status_submit),
            keterangan=self.keterangan,
            waktu_submit=self.waktu_submit,
            bukti_screenshot=self.bukti_screenshot,
        )

    def update_from_dataclass(self, p: Peserta) -> None:
        """Salin hasil submit (status, keterangan, dst.) dari dataclass kembali ke row."""
        self.status_submit = p.status_submit.value
        self.keterangan = p.keterangan
        self.waktu_submit = p.waktu_submit
        self.bukti_screenshot = p.bukti_screenshot


def init_db() -> None:
    """Buat tabel bila belum ada. Dipanggil saat startup app."""
    Base.metadata.create_all(engine)


def _row_from_dataclass(p: Peserta, batch_id: Optional[int]) -> PesertaRow:
    return PesertaRow(
        batch_id=batch_id,
        nik=p.nik or "",
        nama=p.nama or "",
        tgl_lahir=p.tgl_lahir,
        jenis_kelamin=p.jenis_kelamin,
        kelompok_usia=p.kelompok_usia.value,
        no_hp=p.no_hp,
        alamat=p.alamat,
        pemeriksaan=p.pemeriksaan or {},
        baris_sumber=p.baris_sumber,
        file_sumber=p.file_sumber,
        status_submit=p.status_submit.value,
        keterangan=p.keterangan,
    )


def simpan_batch(peserta: List[Peserta], nama_file: str,
                 kelompok: KelompokUsia) -> dict:
    """
    Simpan hasil pembacaan satu file Excel ke DB.

    Mengembalikan ringkasan: jumlah disimpan & jumlah dilewati karena NIK
    sudah ada di DB (deteksi duplikat dasar — lihat Fase 2 untuk lebih lanjut).
    """
    disimpan, duplikat = 0, []
    with SessionLocal() as s:
        batch = Batch(nama_file=nama_file, kelompok_usia=kelompok.value)
        s.add(batch)
        s.flush()  # dapatkan batch.id

        # NIK yang sudah ada di DB (untuk skip duplikat)
        nik_baru = {p.nik for p in peserta if p.nik}
        nik_ada = set()
        if nik_baru:
            rows = s.execute(
                select(PesertaRow.nik).where(PesertaRow.nik.in_(nik_baru))
            ).all()
            nik_ada = {r[0] for r in rows}

        for p in peserta:
            # lewati bila NIK sudah ada di DB ATAU sudah muncul di batch ini
            if p.nik and p.nik in nik_ada:
                duplikat.append(p.nik)
                continue
            s.add(_row_from_dataclass(p, batch.id))
            if p.nik:
                nik_ada.add(p.nik)  # cegah duplikat dalam file yang sama
            disimpan += 1

        s.commit()
        batch_id = batch.id

    return {"batch_id": batch_id, "disimpan": disimpan,
            "duplikat": duplikat, "total": len(peserta)}


def hitung_status() -> dict:
    """Kembalikan jumlah peserta per status (untuk dashboard)."""
    with SessionLocal() as s:
        total = s.scalar(select(func.count()).select_from(PesertaRow)) or 0
        per = dict(
            s.execute(
                select(PesertaRow.status_submit, func.count())
                .group_by(PesertaRow.status_submit)
            ).all()
        )
    return {
        "total": total,
        "belum": per.get(StatusSubmit.BELUM.value, 0),
        "proses": per.get(StatusSubmit.PROSES.value, 0),
        "sukses": per.get(StatusSubmit.SUKSES.value, 0),
        "gagal": per.get(StatusSubmit.GAGAL.value, 0),
    }


def jumlah_belum() -> int:
    with SessionLocal() as s:
        return s.scalar(
            select(func.count()).select_from(PesertaRow)
            .where(PesertaRow.status_submit == StatusSubmit.BELUM.value)
        ) or 0


def ambil_id_untuk_proses(statuses: List[str]) -> List[int]:
    """ID peserta yang berstatus salah satu dari `statuses`, urut sesuai input."""
    with SessionLocal() as s:
        rows = s.execute(
            select(PesertaRow.id)
            .where(PesertaRow.status_submit.in_(statuses))
            .order_by(PesertaRow.id)
        ).all()
    return [r[0] for r in rows]


def hapus_belum() -> int:
    """Kosongkan antrian: hapus peserta yang belum/ gagal disubmit.

    Menyimpan riwayat yang sudah SUKSES.
    """
    from sqlalchemy import delete
    with SessionLocal() as s:
        res = s.execute(
            delete(PesertaRow).where(
                PesertaRow.status_submit.in_(
                    [StatusSubmit.BELUM.value, StatusSubmit.GAGAL.value]
                )
            )
        )
        s.commit()
        return res.rowcount or 0


def semua_peserta() -> List[PesertaRow]:
    """Semua peserta (untuk ekspor log)."""
    with SessionLocal() as s:
        return list(s.scalars(select(PesertaRow).order_by(PesertaRow.id)).all())


# ---------------------------------------------------------------------------
# Audit trail (tabel `run`)
# ---------------------------------------------------------------------------
def _operator() -> str:
    """Nama operator = user OS. Aplikasi tanpa login (diikat ke 127.0.0.1)."""
    import getpass
    try:
        return getpass.getuser()
    except Exception:
        return "tidak diketahui"


def mulai_run(jenis: str, label: str, perintah: str = "",
              parameter: Optional[dict] = None, jumlah_total: int = 0) -> int:
    """Catat awal sebuah proses. Kembalikan id-nya untuk dipakai `akhiri_run`."""
    with SessionLocal() as s:
        r = Run(
            jenis=jenis, label=label, operator=_operator(),
            perintah=perintah or None, parameter=parameter or {},
            mulai=datetime.now(), status="berjalan", jumlah_total=jumlah_total,
        )
        s.add(r)
        s.commit()
        return r.id


def akhiri_run(run_id: Optional[int], status: str, returncode: Optional[int] = None,
               ringkasan: str = "", sukses: int = 0, gagal: int = 0) -> None:
    """Tutup baris audit. Aman dipanggil dengan run_id None (mis. saat gagal start)."""
    if run_id is None:
        return
    with SessionLocal() as s:
        r = s.get(Run, run_id)
        if r is None:
            return
        r.status = status
        r.selesai = datetime.now()
        r.returncode = returncode
        r.ringkasan = (ringkasan or None)
        r.jumlah_sukses = sukses
        r.jumlah_gagal = gagal
        # Tahap CDP tidak tahu jumlah peserta di awal (mulai_run dipanggil
        # sebelum tool membaca Excel), jadi jumlah_total baru bisa disimpulkan
        # di akhir. Tanpa ini, detail run menampilkan "0 total, 12 sukses".
        if not r.jumlah_total:
            r.jumlah_total = sukses + gagal
        s.commit()


def tandai_run_tergantung() -> int:
    """Tutup run yang masih 'berjalan' dari sesi sebelumnya.

    Kalau server mati di tengah proses, barisnya akan selamanya tampak
    'berjalan' dan membuat halaman Riwayat berbohong. Dipanggil saat startup.
    """
    with SessionLocal() as s:
        rows = list(s.scalars(select(Run).where(Run.status == "berjalan")).all())
        for r in rows:
            r.status = "gagal"
            r.selesai = r.selesai or datetime.now()
            r.ringkasan = "Server berhenti saat proses masih berjalan (status tak diketahui)."
        s.commit()
        return len(rows)


def daftar_run(limit: int = 20, offset: int = 0,
               jenis: str = "") -> tuple[List[Run], int]:
    """Halaman riwayat: run terbaru dulu. Kembalikan (baris, total)."""
    with SessionLocal() as s:
        q = select(Run)
        qc = select(func.count()).select_from(Run)
        if jenis:
            q = q.where(Run.jenis == jenis)
            qc = qc.where(Run.jenis == jenis)
        total = s.scalar(qc) or 0
        rows = list(s.scalars(
            q.order_by(Run.mulai.desc(), Run.id.desc()).limit(limit).offset(offset)
        ).all())
    return rows, total


def ambil_run(run_id: int) -> Optional[Run]:
    with SessionLocal() as s:
        return s.get(Run, run_id)


def cari_peserta(q: str = "", status: str = "", limit: int = 25,
                 offset: int = 0) -> tuple[List[PesertaRow], int]:
    """Drill-down peserta: cari NIK/nama, filter status, ber-paginasi."""
    with SessionLocal() as s:
        stmt = select(PesertaRow)
        cnt = select(func.count()).select_from(PesertaRow)
        if q:
            pola = f"%{q.strip()}%"
            kondisi = PesertaRow.nik.like(pola) | PesertaRow.nama.like(pola)
            stmt, cnt = stmt.where(kondisi), cnt.where(kondisi)
        if status:
            stmt, cnt = stmt.where(PesertaRow.status_submit == status), \
                        cnt.where(PesertaRow.status_submit == status)
        total = s.scalar(cnt) or 0
        rows = list(s.scalars(
            stmt.order_by(PesertaRow.id.desc()).limit(limit).offset(offset)
        ).all())
    return rows, total
