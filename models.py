# -*- coding: utf-8 -*-

from enum import IntEnum

from sqlalchemy import Column, Enum, ForeignKey, Integer, String, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker

Base = declarative_base()


class ItemStatusEnum(IntEnum):
    DISCONTINUED = -1
    OUTOFSTOCK = 0
    AVAILABLE = 1
    PREORDER = 2
    UPCOMING = 3
    CALLFORPRICE = 4


class Platform(Base):
    __tablename__ = "platforms"

    id = Column(Integer, primary_key=True)
    url = Column(String)
    title = Column(String)

    products = relationship("Product", back_populates="platform")


# TODO: Add product views field.
class Product(Base):
    __tablename__ = "products"

    id = Column(String, primary_key=True)
    title = Column(String)
    category = Column(String)
    subcategory1 = Column(String)
    subcategory2 = Column(String)
    price_regular = Column(Integer)
    price = Column(Integer)
    code = Column(String, index=True)
    url = Column(String)
    status = Column(Enum(ItemStatusEnum))

    reviews = relationship("Review", back_populates="product")
    specifications = relationship("Specification", back_populates="product")
    questions = relationship("Question", back_populates="product")

    brand_id = Column(Integer, ForeignKey("brands.id"))
    brand = relationship("Brand", back_populates="products")

    platform_id = Column(Integer, ForeignKey("platforms.id"), nullable=False)
    platform = relationship("Platform", back_populates="products")


class Brand(Base):
    __tablename__ = "brands"

    id = Column(Integer, primary_key=True)
    title = Column(String, unique=True)

    products = relationship("Product", back_populates="brand")


class Review(Base):
    __tablename__ = "reviews"

    id = Column(Integer, primary_key=True)
    rating = Column(Integer)
    username = Column(String)
    comment = Column(String)

    product_id = Column(String, ForeignKey("products.id"))
    product = relationship("Product", back_populates="reviews")


class Specification(Base):
    __tablename__ = "specs"

    id = Column(Integer, primary_key=True)
    key = Column(String)
    value = Column(String)

    product_id = Column(String, ForeignKey("products.id"))
    product = relationship("Product", back_populates="specifications")


class Question(Base):
    __tablename__ = "questions"

    id = Column(Integer, primary_key=True)
    username = Column(String)
    question = Column(String)
    answer = Column(String)

    product_id = Column(String, ForeignKey("products.id"))
    product = relationship("Product", back_populates="questions")


DEFAULT_DBURI = 'sqlite:///datadir/db.sqlite3'


def create_db_session(dburi, echo=False):
    engine = create_engine(dburi, echo=echo)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    return session
