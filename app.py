import os
import re
import shutil
from flask import Flask, render_template, request, redirect, url_for, session, flash, send_from_directory
from werkzeug.utils import secure_filename
from sqlalchemy import or_

from database import db, User, Department, Menu, Post, FileAttachment
from data_scraper import is_allowed_file, scrape_text_from_file

# --- App Configuration ---
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///bpm_database.db'
app.config['SECRET_KEY'] = 'a-very-secret-key-that-you-should-change'
app.config['UPLOAD_FOLDER'] = 'uploads'
db.init_app(app)

# --- Command to initialize the database ---
@app.cli.command("init-db")
def init_db_command():
    """Drops all existing tables and creates new ones with sample data."""
    with app.app_context():
        db.drop_all()
        db.create_all()
        
        # 1. Create and commit departments first to get their IDs
        d_finance = Department(name="Finance", active=True)
        d_mgmt = Department(name="Management", active=True)
        db.session.add_all([d_finance, d_mgmt])
        db.session.commit()
        print("Departments created.")

        # 2. Re-fetch departments from DB to ensure IDs are loaded
        finance_dept_from_db = Department.query.filter_by(name="Finance").first()
        mgmt_dept_from_db = Department.query.filter_by(name="Management").first()
        
        # 3. Create users with correct department IDs
        users = [
            User(username="super_admin", password="super_pass", email="sa@ex.com", role="superadmin"),
            User(username="finance_admin", password="pass_finance", email="fa@ex.com", role="admin", department_id=finance_dept_from_db.id),
            User(username="finance_user", password="user_pass", email="fu@ex.com", role="user", department_id=finance_dept_from_db.id),
            User(username="mgmt_admin", password="pass_mgmt", email="ma@ex.com", role="admin", department_id=mgmt_dept_from_db.id)
        ]
        db.session.add_all(users)
        db.session.commit()
        print("Initialized the database with users linked to correct department IDs.")

# --- Helper Functions ---
def get_current_user_and_permissions():
    """Gets the current user object and their super_admin status from the session."""
    if 'user_id' not in session: return None, False
    user = db.session.get(User, session['user_id'])
    is_super_admin = user.role == 'superadmin' if user else False
    return user, is_super_admin

def can_user_edit_department(user, department, is_super_admin):
    """Checks if the current user can edit a specific department."""
    if not user: return False
    return is_super_admin or (user.role == 'admin' and department and user.department_id == department.id)

def get_flat_menu_list(menus):
    """Creates an indented list of menu names and IDs for dropdowns."""
    flat_list = []
    def _flatten(menu_list, depth=0):
        for item in menu_list:
            indented_name = '—' * depth + ' ' + item.name if depth > 0 else item.name
            flat_list.append({'id': item.id, 'name': indented_name})
            if item.children: _flatten(item.children, depth + 1)
    _flatten(menus)
    return flat_list

# --- Page & Auth Routes ---
@app.route('/', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        user = db.session.get(User, session['user_id'])
        if user:
            if user.role == 'superadmin':
                return redirect(url_for('admin_panel'))
            if user.department and user.department.active:
                return redirect(url_for('department_dashboard', department_name=user.department.name))
        return redirect(url_for('logout')) # Failsafe for invalid session

    if request.method == 'POST':
        user = User.query.filter_by(username=request.form.get('username')).first()
        if user and user.password == request.form.get('password'):
            session['user_id'] = user.id
            flash("Login successful!", "success")
            return redirect(url_for('login')) # Let the logic above handle the redirect
        else:
            flash("Invalid username or password.", "danger")
            return render_template('login.html') # Re-render on failure
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear(); flash('You have been logged out.', 'info'); return redirect(url_for('login'))

@app.route('/setup', methods=['GET', 'POST'])
def setup_page():
    user, is_super_admin = get_current_user_and_permissions()
    if not user: return redirect(url_for('login'))
    
    # This route now ONLY handles the username change form submission.
    if request.method == 'POST':
        new_username = request.form.get('new_username', '').strip()

        # Business logic validation for the username change
        if user.role == 'superadmin':
            flash("Superadmin username cannot be changed from this page for security.", 'warning')
        elif not new_username:
            flash("New username cannot be empty.", 'danger')
        elif new_username == user.username:
            flash("Please enter a username different from your current one.", 'info')
        elif User.query.filter(User.username == new_username, User.id != user.id).first():
            flash("That username is already taken by another user.", 'danger')
        else:
            user.username = new_username
            db.session.commit()
            flash("Username changed successfully! Please log in again.", 'success')
            return redirect(url_for('logout'))
            
    return render_template('setup.html', user=user, is_super_admin=is_super_admin)

# --- Admin Routes ---
@app.route('/admin')
def admin_panel():
    user, is_super_admin = get_current_user_and_permissions()
    if not is_super_admin: return redirect(url_for('login'))
    departments = Department.query.order_by(Department.name).all()
    return render_template('admin_panel.html', departments=departments, user=user)

@app.route('/admin/add_department', methods=['POST'])
def add_department():
    user, is_super_admin = get_current_user_and_permissions()
    if not is_super_admin: return "Access Denied", 403
    dept_name = request.form.get('department_name', '').strip()
    if dept_name and not Department.query.filter_by(name=dept_name).first():
        new_dept = Department(name=dept_name)
        db.session.add(new_dept); db.session.commit(); flash(f"Department '{dept_name}' created.", 'success')
    else: flash("Department name is empty or already exists.", 'danger')
    return redirect(url_for('admin_panel'))

@app.route('/admin/edit_department/<int:department_id>', methods=['POST'])
def edit_department_name(department_id):
    user, is_super_admin = get_current_user_and_permissions()
    if not is_super_admin: return "Access Denied", 403
    department = db.session.get(Department, department_id)
    new_name = request.form.get('new_department_name', '').strip()
    if department and new_name and not Department.query.filter(Department.name == new_name, Department.id != department_id).first():
        department.name = new_name; db.session.commit(); flash(f"Department name updated to '{new_name}'.", 'success')
    else: flash("New name is invalid or already exists.", 'danger')
    return redirect(url_for('admin_panel'))

@app.route('/admin/toggle_department/<int:department_id>', methods=['POST'])
def toggle_department_status(department_id):
    user, is_super_admin = get_current_user_and_permissions()
    if not is_super_admin: return "Access Denied", 403
    department = db.session.get(Department, department_id)
    if department:
        department.active = not department.active; db.session.commit()
        flash(f"Department '{department.name}' status updated.", 'success')
    return redirect(url_for('admin_panel'))

@app.route('/admin/delete_department/<int:department_id>', methods=['POST'])
def delete_department(department_id):
    user, is_super_admin = get_current_user_and_permissions()
    if not is_super_admin: return "Access Denied", 403

    department = db.session.get(Department, department_id)
    if department:
        department_upload_folder = os.path.join(app.config['UPLOAD_FOLDER'], str(department.id))
        if os.path.exists(department_upload_folder):
            try: shutil.rmtree(department_upload_folder)
            except OSError as e: flash(f"Error deleting files for '{department.name}': {e}", 'danger'); return redirect(url_for('admin_panel'))
        
        User.query.filter_by(department_id=department.id).update({User.department_id: None})
        department_name = department.name
        db.session.delete(department)
        db.session.commit()
        flash(f"Department '{department_name}' has been permanently deleted.", "success")
    else: flash("Department not found.", "danger")
    return redirect(url_for('admin_panel'))
    
@app.route('/admin/users')
def user_management():
    user, is_super_admin = get_current_user_and_permissions()
    if not is_super_admin: return redirect(url_for('login'))
    users = User.query.order_by(User.role.desc(), User.username).all()
    departments = Department.query.order_by(Department.name).all()
    return render_template('admin_users.html', users=users, departments=departments, user=user)

@app.route('/admin/users/add', methods=['POST'])
def add_user():
    user, is_super_admin = get_current_user_and_permissions();
    if not is_super_admin: return redirect(url_for('login'))
    username, email, password, role, department_id = (request.form.get(k, '').strip() for k in ['username','email','password','role','department_id'])
    if not all([username, email, password, role]):
        flash('Username, email, password, and role are required fields.', 'danger')
    elif User.query.filter(or_(User.username == username, User.email == email)).first():
        flash('Username or email already exists.', 'danger')
    else:
        new_user = User(username=username, email=email, password=password, role=role) # In prod, hash this
        if role != 'superadmin' and department_id: new_user.department_id = int(department_id)
        db.session.add(new_user); db.session.commit(); flash(f'User "{username}" created.', 'success')
    return redirect(url_for('user_management'))
    
@app.route('/admin/users/edit/<int:user_id>', methods=['POST'])
def edit_user(user_id):
    user, is_super_admin = get_current_user_and_permissions()
    if not is_super_admin: return redirect(url_for('login'))
    user_to_edit = db.session.get(User, user_id)
    if not user_to_edit: return redirect(url_for('user_management'))
    new_password = request.form.get('password').strip()
    if new_password: user_to_edit.password = new_password
    user_to_edit.role = request.form.get('role'); dept_id = request.form.get('department_id')
    if user_to_edit.role == 'superadmin':
        user_to_edit.department_id = None
    else:
        user_to_edit.department_id = int(dept_id) if dept_id else None
    db.session.commit(); flash(f'User "{user_to_edit.username}" updated.', 'success')
    return redirect(url_for('user_management'))
    
@app.route('/admin/users/delete/<int:user_id>', methods=['POST'])
def delete_user(user_id):
    user, is_super_admin = get_current_user_and_permissions()
    if not is_super_admin: return redirect(url_for('login'))
    user_to_delete = db.session.get(User, user_id)
    if user_to_delete and user_to_delete.role != 'superadmin':
        db.session.delete(user_to_delete); db.session.commit()
        flash(f"User '{user_to_delete.username}' deleted.", "success")
    elif user_to_delete: flash("Cannot delete the superadmin account.", "danger")
    return redirect(url_for('user_management'))

# --- Main BPM Routes ---
@app.route('/department/<string:department_name>', methods=['GET', 'POST'])
def department_dashboard(department_name):
    user, is_super_admin = get_current_user_and_permissions()
    if not user: return redirect(url_for('login'))

    department = Department.query.filter_by(name=department_name).first()
    if not department:
        flash(f"Department '{department_name}' not found.", 'danger'); return redirect(url_for('admin_panel') if is_super_admin else url_for('login'))
    
    can_edit = can_user_edit_department(user, department, is_super_admin)
    
    if not department.active and not is_super_admin:
        flash(f"'{department.name}' is inactive.", 'info'); return redirect(url_for('department_dashboard', department_name=user.department.name))

    if request.method == 'POST' and can_edit:
        new_menu_name = request.form.get('new_menu_name'); parent_id = request.form.get('parent_menu_id')
        if new_menu_name:
            new_menu = Menu(name=new_menu_name, department_id=department.id)
            if parent_id and parent_id != 'root': new_menu.parent_id = int(parent_id)
            db.session.add(new_menu); db.session.commit(); flash("Menu created.", "success")
        return redirect(url_for('department_dashboard', department_name=department_name))

    visible_departments = Department.query.order_by(Department.name).all() if is_super_admin else Department.query.filter_by(active=True).order_by(Department.name).all()
    top_level_menus = Menu.query.filter_by(department_id=department.id, parent_id=None).order_by(Menu.name).all()
    
    return render_template('department_dashboard.html', department=department, top_level_menus=top_level_menus, flat_menu_list=get_flat_menu_list(top_level_menus),
                           can_edit=can_edit, is_super_admin=is_super_admin, all_departments=visible_departments, user=user)

@app.route('/department/<string:department_name>/menu/<int:menu_id>', methods=['GET', 'POST'])
def menu_content_page(department_name, menu_id):
    user, is_super_admin = get_current_user_and_permissions()
    if not user: return redirect(url_for('login'))
    
    menu = db.session.get(Menu, menu_id)
    if not menu:
        flash("Menu not found.", "danger"); return redirect(url_for('department_dashboard', department_name=department_name))
    
    can_edit = can_user_edit_department(user, menu.department, is_super_admin)
    if not menu.active and not can_edit:
        flash('This menu is inactive.', 'danger'); return redirect(url_for('department_dashboard', department_name=department_name))

    if request.method == 'POST' and can_edit:
        new_post = Post(menu_id=menu.id, rich_content=request.form.get('content', ''), scraped_file_content="")
        db.session.add(new_post); db.session.commit()
        files, scraped_texts = request.files.getlist('files[]'), []
        for file in files:
            if file and file.filename:
                filename = secure_filename(file.filename); upload_path = os.path.join(app.config['UPLOAD_FOLDER'], str(menu.department.id), str(menu.id))
                os.makedirs(upload_path, exist_ok=True); filepath = os.path.join(upload_path, filename); file.save(filepath)
                db.session.add(FileAttachment(filename=filename, post_id=new_post.id))
                if is_allowed_file(filename):
                    text = scrape_text_from_file(filepath);
                    if text: scraped_texts.append(text)
        if scraped_texts: new_post.scraped_file_content = "\n\n".join(scraped_texts); db.session.commit()
        flash("Content posted successfully.", "success")
        return redirect(url_for('menu_content_page', department_name=department_name, menu_id=menu_id))
    
    posts_to_display = Post.query.filter_by(menu_id=menu.id, is_deleted=False).order_by(Post.id.desc()).all()
    return render_template('menu_content.html', menu=menu, posts=posts_to_display, can_edit=can_edit, user=user)

@app.route('/search')
def search():
    user, is_super_admin = get_current_user_and_permissions();
    if not user: return redirect(url_for('login'))
    query = request.args.get('query', '').strip().lower(); 
    if not query: return redirect(request.referrer)
    search_term = f"%{query}%"; results = []
    active_filter = or_(Department.active == True, is_super_admin == True)
    
    posts_found = Post.query.join(Menu).join(Department).filter(active_filter, not_(Post.is_deleted), or_(Post.rich_content.ilike(search_term), Post.scraped_file_content.ilike(search_term))).all()
    
    for post in posts_found:
        snippet = f"Match in: {post.rich_content[:150]}..."
        results.append({'type': 'Content', 'url': url_for('menu_content_page', department_name=post.menu.department.name, menu_id=post.menu.id) + f"#post-{post.id}", 'department': post.menu.department.name, 'menu': post.menu.name, 'context': snippet})
    
    return render_template('search_results.html', query=request.args.get('query',''), results=results, user=user)

@app.route('/toggle_menu/<int:menu_id>', methods=['POST'])
def toggle_menu_status(menu_id):
    menu = db.session.get(Menu, menu_id); user, is_super_admin = get_current_user_and_permissions()
    if menu and can_user_edit_department(user, menu.department, is_super_admin):
        menu.active = not menu.active; db.session.commit()
    return redirect(request.referrer)

@app.route('/toggle_post/<int:post_id>', methods=['POST'])
def toggle_post_status(post_id):
    post = db.session.get(Post, post_id); user, is_super_admin = get_current_user_and_permissions()
    if post and can_user_edit_department(user, post.menu.department, is_super_admin):
        post.active = not post.active; db.session.commit(); flash(f"Post status updated.", 'info')
    return redirect(request.referrer)

@app.route('/delete_post/<int:post_id>', methods=['POST'])
def delete_post(post_id):
    post = db.session.get(Post, post_id); user, is_super_admin = get_current_user_and_permissions()
    if post and can_user_edit_department(user, post.menu.department, is_super_admin):
        post.is_deleted = True; db.session.commit()
        flash("Content has been soft-deleted.", "success")
    return redirect(request.referrer)

@app.route('/uploads/download/<int:file_id>')
def download_file(file_id):
    attachment = db.session.get(FileAttachment, file_id)
    if not attachment: return "File not found.", 404
    user, is_super_admin = get_current_user_and_permissions(); can_edit = can_user_edit_department(user, attachment.post.menu.department, is_super_admin)
    if not attachment.post.is_deleted:
        if can_edit or (attachment.post.active and attachment.post.menu.active and attachment.post.menu.department.active):
            upload_path = os.path.join(app.config['UPLOAD_FOLDER'], str(attachment.post.menu.department_id), str(attachment.post.menu.id))
            return send_from_directory(upload_path, attachment.filename, as_attachment=True)
    return "Access to this file is restricted.", 403

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True, port=5000)