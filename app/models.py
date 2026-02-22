import datetime

from sqlalchemy import BigInteger, Date, DateTime, Float, Integer, String, Text, func, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Lead(Base):
    __tablename__ = "leads"

    id_custom: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    status: Mapped[int] = mapped_column(Integer, nullable=False)
    date: Mapped[datetime.date] = mapped_column(Date, nullable=False, index=True)
    webmaster: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    sum: Mapped[float] = mapped_column(Float, nullable=False, server_default=text("0"))
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    imported_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )


class WebmasterReport(Base):
    __tablename__ = "webmaster_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    webmaster: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    period_days: Mapped[int] = mapped_column(Integer, nullable=False)
    leads_total: Mapped[int] = mapped_column(Integer, nullable=False)
    approved: Mapped[int] = mapped_column(Integer, nullable=False)
    bought_out: Mapped[int] = mapped_column(Integer, nullable=False)
    trash: Mapped[int] = mapped_column(Integer, nullable=False)
    approve_pct: Mapped[float] = mapped_column(Float, nullable=False)
    buyout_pct: Mapped[float] = mapped_column(Float, nullable=False)
    trash_pct: Mapped[float] = mapped_column(Float, nullable=False)
    score_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    issues: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'[]'"))
