# -*- coding: utf-8 -*-

from json import loads

from sqlalchemy import Column, ForeignKey, Integer, String, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker

Base = declarative_base()


class Product(Base):
    __tablename__ = "products"

    id = Column(String, primary_key=True)
    title = Column(String)
    category = Column(String)
    subcategory1 = Column(String)
    subcategory2 = Column(String)
    brand = Column(String)
    price_old = Column(Integer)
    price = Column(Integer)

    reviews = relationship("Review", back_populates="product")
    specifications = relationship("Specification", back_populates="product")

    brand_id = Column(Integer, ForeignKey("brands.id"))
    brand = relationship("Brand", back_populates="products")


class Brand(Base):
    __tablename__ = "brands"

    id = Column(Integer, primary_key=True)
    title = Column(String)

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


DEFAULT_DBURI = 'sqlite:///datadir/db.sqlite3'


def create_db_session(dburi, echo=False):
    engine = create_engine(dburi, echo=echo)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    return session
