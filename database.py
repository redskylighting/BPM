from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import relationship

# Initialize the database extension
db = SQLAlchemy()

# Define the database models (tables)
class Department(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    active = db.Column(db.Boolean, default=True, nullable=False)
    users = relationship("User", back_populates="department")
    menus = relationship("Menu", back_populates="department", cascade="all, delete-orphan")

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    role = db.Column(db.String(20), nullable=False, default='user')
    department_id = db.Column(db.Integer, db.ForeignKey('department.id'), nullable=True)
    department = relationship("Department", back_populates="users")

class Menu(db.Model):
    __tablename__ = 'menu'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    active = db.Column(db.Boolean, default=True, nullable=False)

    # Foreign Key to self-referencing table
    parent_id = db.Column(db.Integer, db.ForeignKey('menu.id'))

    department_id = db.Column(db.Integer, db.ForeignKey('department.id'), nullable=False)
    department = relationship("Department", back_populates="menus")
    
    # This relationship defines the "parent" attribute on the child.
    # A child menu has ONE parent.
    parent = relationship('Menu', remote_side=[id], back_populates='children')
    
    # This relationship defines the "children" attribute on the parent.
    # A parent menu can have MANY children. This is the one-to-many side,
    # so `delete-orphan` cascade belongs here.
    children = relationship('Menu', back_populates='parent', cascade="all, delete-orphan")

    posts = relationship("Post", back_populates="menu", cascade="all, delete-orphan")

class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    active = db.Column(db.Boolean, default=True, nullable=False)
    rich_content = db.Column(db.Text, nullable=True)
    scraped_file_content = db.Column(db.Text, nullable=True)
    menu_id = db.Column(db.Integer, db.ForeignKey('menu.id'), nullable=False)
    menu = relationship("Menu", back_populates="posts")
    attachments = relationship("FileAttachment", back_populates="post", cascade="all, delete-orphan")

class FileAttachment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=False)
    post = relationship("Post", back_populates="attachments")