import datetime

from sqlalchemy import BigInteger, Date, DateTime, Float, Integer, String, func, text
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
    imported_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
