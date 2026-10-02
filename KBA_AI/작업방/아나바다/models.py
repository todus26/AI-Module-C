from datetime import datetime

from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash, generate_password_hash

db = SQLAlchemy()

STATUS_AVAILABLE = "거래가능"
STATUS_DONE = "거래완료"


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(30), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)

    items = db.relationship(
        "Item", back_populates="author", cascade="all, delete-orphan"
    )

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Item(db.Model):
    __tablename__ = "items"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=False)
    price = db.Column(db.Integer, nullable=False, default=0)  # 0이면 무료 나눔
    image_filename = db.Column(db.String(255), nullable=True)
    status = db.Column(db.String(20), nullable=False, default=STATUS_AVAILABLE)
    author_id = db.Column(
        db.Integer, db.ForeignKey("users.id"), nullable=False, index=True
    )
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=datetime.now, onupdate=datetime.now
    )

    author = db.relationship("User", back_populates="items")

    @property
    def is_free(self):
        return self.price == 0

    @property
    def is_done(self):
        return self.status == STATUS_DONE

    @property
    def status_label(self):
        if self.is_done:
            return "나눔 완료" if self.is_free else "거래 완료"
        return "나눔 중" if self.is_free else "거래 가능"

    @property
    def price_label(self):
        return "무료 나눔" if self.is_free else f"{self.price:,}원"
