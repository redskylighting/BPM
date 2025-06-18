from sqlalchemy import create_engine, Column, Integer, String, Boolean, ForeignKey
from sqlalchemy.orm import relationship, sessionmaker
from sqlalchemy.ext.declarative import declarative_base

DATABASE_URL = "sqlite:///bpm_database.db"
Base = declarative_base()

class User(Base):
    __tablename__ = 'user'
    id = Column(Integer, primary_key=True)
    username = Column(String(50), unique=True, nullable=False)
    password = Column(String(50), nullable=False)
    email = Column(String(120), unique=True, nullable=False)
    role = Column(String(50), default='user')
    department_id = Column(Integer, ForeignKey('department.id'), nullable=True)
    department = relationship("Department", back_populates="users")
    def __repr__(self):
        return f"<User(username='{self.username}')>"

class Department(Base):
    __tablename__ = 'department'
    id = Column(Integer, primary_key=True)
    name = Column(String(100), unique=True, nullable=False)
    active = Column(Boolean, default=True)
    users = relationship("User", back_populates="department")
    menus = relationship("Menu", back_populates="department")
    def __repr__(self):
        return f"<Department(name='{self.name}')>"

class Menu(Base):
    __tablename__ = 'menu'
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    active = Column(Boolean, default=True)
    department_id = Column(Integer, ForeignKey('department.id'), nullable=False)
    department = relationship("Department", back_populates="menus")
    parent_id = Column(Integer, ForeignKey('menu.id'), nullable=True)
    children = relationship("Menu", remote_side=[id], back_populates="parent")
    parent = relationship("Menu", remote_side=[parent_id], back_populates="children")
    posts = relationship("Post", back_populates="menu")
    def __repr__(self):
        return f"<Menu(name='{self.name}')>"

class Post(Base):
    __tablename__ = 'post'
    id = Column(Integer, primary_key=True)
    rich_content = Column(String, nullable=True)
    scraped_file_content = Column(String, nullable=True)
    active = Column(Boolean, default=True)
    menu_id = Column(Integer, ForeignKey('menu.id'), nullable=False)
    menu = relationship("Menu", back_populates="posts")
    file_attachments = relationship("FileAttachment", back_populates="post")
    def __repr__(self):
        return f"<Post(id='{self.id}')>"

class FileAttachment(Base):
    __tablename__ = 'file_attachment'
    id = Column(Integer, primary_key=True)
    filename = Column(String(255), nullable=False)
    post_id = Column(Integer, ForeignKey('post.id'), nullable=False)
    post = relationship("Post", back_populates="file_attachments")
    def __repr__(self):
        return f"<FileAttachment(filename='{self.filename}')>"

# Create the engine
engine = create_engine(DATABASE_URL)

# Create a session
Session = sessionmaker(bind=engine)

def init_db(db):
    """
    Initialize the database: create tables and add initial data.
    """
    # Create the tables
    Base.metadata.create_all(engine)
    print("Database tables created.")
    # Example: Add initial data (e.g., a default department)
    session = Session()
    if not session.query(Department).filter_by(name="Management").first():
        # ...existing code...
        print("Initialized the database with sample data.")
