"""
Lapisan database (SQLite + SQLAlchemy).

Menyimpan audit trail: tabel `run` — siapa menjalankan tahap apa, dengan
parameter apa, kapan, dan hasilnya. Data peserta TIDAK disimpan di sini;
sumber kebenarannya adalah file Excel yang ditulis-balik oleh tools/.
"""
import os
from datetime import datetime
from typing import List, Optional

from sqlalchemy import (
    create_engine, String, Integer, DateTime, JSON, func, select
)
from sqlalchemy.orm import (
    DeclarativeBase, Mapped, mapped_column, sessionmaker, Session
)


# --- lokasi file DB ---
DATA_DIR = "data"
DB_PATH = os.path.join(DATA_DIR, "ckg.db")
os.makedirs(DATA_DIR, exist_ok=True)

# check_same_thread=False karena tahap dijalankan di thread terpisah.
engine = create_engine(
    f"sqlite:///{DB_PATH}",
    echo=False,
    future=True,
    connect_args={"check_same_thread": False},
)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False, class_=Session)


class Base(DeclarativeBase):
    pass


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


def init_db() -> None:
    """Buat tabel bila belum ada. Dipanggil saat startup app."""
    Base.metadata.create_all(engine)


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


