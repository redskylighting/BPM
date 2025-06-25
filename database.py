from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import relationship
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ForeignKey

db = SQLAlchemy()

class Department(db.Model):
    id = db.Column(Integer, primary_key=True)
    name = db.Column(String(100), unique=True, nullable=False)
    active = db.Column(Boolean, default=True, nullable=False)
    users = relationship("User", back_populates="department")
    menus = relationship("Menu", back_populates="department", cascade="all, delete-orphan")

class User(db.Model):
    id = db.Column(Integer, primary_key=True)
    username = db.Column(String(80), unique=True, nullable=False)
    password = db.Column(String(120), nullable=False)
    email = db.Column(String(120), unique=True, nullable=False)
    role = db.Column(String(20), nullable=False, default='user')
    department_id = db.Column(Integer, db.ForeignKey('department.id'), nullable=True)
    department = relationship("Department", back_populates="users")
    is_locked = db.Column(Boolean, default=False, nullable=False)
    mfa_code = db.Column(String(6), nullable=True)
    mfa_code_expires = db.Column(DateTime, nullable=True)
    mfa_attempts = db.Column(Integer, default=0, nullable=False)

class Menu(db.Model):
    __tablename__ = 'menu'
    id = db.Column(Integer, primary_key=True)
    name = db.Column(String(150), nullable=False)
    active = db.Column(Boolean, default=True, nullable=False)
    parent_id = db.Column(Integer, db.ForeignKey('menu.id'))
    department_id = db.Column(Integer, db.ForeignKey('department.id'), nullable=False)
    department = relationship("Department", back_populates="menus")
    
    # CORRECTED RELATIONSHIP: Defines parent and children unambiguously.
    parent = relationship('Menu', remote_side=[id], back_populates='children')
    children = relationship('Menu', back_populates='parent', cascade="all, delete-orphan")

    posts = relationship("Post", back_populates="menu", cascade="all, delete-orphan")

class Post(db.Model):
    id = db.Column(Integer, primary_key=True)
    active = db.Column(Boolean, default=True, nullable=False)
    is_deleted = db.Column(Boolean, default=False, nullable=False)
    rich_content = db.Column(Text, nullable=True)
    scraped_file_content = db.Column(Text, nullable=True)
    menu_id = db.Column(Integer, db.ForeignKey('menu.id'), nullable=False)
    menu = relationship("Menu", back_populates="posts")
    attachments = relationship("FileAttachment", back_populates="post", cascade="all, delete-orphan")

class FileAttachment(db.Model):
    id = db.Column(Integer, primary_key=True)
    filename = db.Column(String(255), nullable=False)
    post_id = db.Column(Integer, db.ForeignKey('post.id'), nullable=False)
    post = relationship("Post", back_populates="attachments")