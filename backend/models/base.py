"""Declarative base compartilhada por todos os modelos."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
