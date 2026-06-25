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
