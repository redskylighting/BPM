import os
import copy
import re
from flask import Flask, render_template, request, redirect, url_for, session, flash, send_from_directory
from werkzeug.utils import secure_filename
from flask_mail import Mail, Message

# --- App Configuration ---
app = Flask(__name__)
app.secret_key = 'a-very-secret-key-that-you-should-change'
UPLOAD_FOLDER = 'uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# For local email testing
app.config['MAIL_SERVER'] = 'localhost'
app.config['MAIL_PORT'] = 1025
mail = Mail(app)

# --- "Database" with 'role' Field ---
USERS = {
    'finance_admin': {'password': 'pass_finance', 'department': 'Finance', 'email': 'finance@example.com', 'role': 'admin'},
    'mgmt_admin': {'password': 'pass_mgmt', 'department': 'Management', 'email': 'management@example.com', 'role': 'admin'},
    'mfg_admin': {'password': 'pass_mfg', 'department': 'Manufacturing', 'email': 'manufacturing@example.com', 'role': 'admin'},
    'finance_user': {'password': 'user_pass', 'department': 'Finance', 'email': 'finance_user@example.com', 'role': 'user'},
    'global_viewer': {'password': 'viewer_pass', 'department': 'Finance', 'email': 'viewer@example.com', 'role': 'user'},
}

def create_menu_item(name, item_id):
    return { 'id': item_id, 'name': name, 'active': True, 'posts': [], 'files': [], 'children': [], 'post_id_counter': 0, 'file_id_counter': 0 }
def get_default_department_data():
    return {'menu_id_counter': 0, 'menu': []}
DEPARTMENT_DATA = { 'Finance': get_default_department_data(), 'Management': get_default_department_data(), 'Manufacturing': get_default_department_data() }


# --- Helper Functions ---
def get_flat_menu_list(menu_list, depth=0):
    flat_list = []
    for item in menu_list:
        indented_name = '—' * depth + ' ' + item['name'] if depth > 0 else item['name']
        flat_list.append({'id': item['id'], 'name': indented_name})
        if item.get('children'):
            flat_list.extend(get_flat_menu_list(item['children'], depth + 1))
    return flat_list

def find_item_in_tree(menu_list, item_id):
    for index, menu_item in enumerate(menu_list):
        if menu_item['id'] == item_id:
            return (menu_item, menu_list, index)
        found = find_item_in_tree(menu_item.get('children', []), item_id)
        if found[0]:
            return found
    return (None, None, None)

def get_user_permissions(department_name):
    if 'username' not in session: return None, False
    user = USERS.get(session['username'])
    if not user: return None, False
    can_edit = (user['department'] == department_name and user['role'] == 'admin')
    department = DEPARTMENT_DATA.get(department_name)
    return department, can_edit


# --- Page & Auth Routes ---
@app.route('/', methods=['GET', 'POST'])
def login():
    if 'username' in session:
        return redirect(url_for('department_dashboard', department_name=session['department']))
    if request.method == 'POST':
        username, password = request.form['username'], request.form['password']
        user = USERS.get(username)
        if user and user['password'] == password:
            session['username'], session['department'] = username, user['department']
            return redirect(url_for('department_dashboard', department_name=user['department']))
        flash('Invalid username or password.', 'danger')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))

@app.route('/setup', methods=['GET', 'POST'])
def setup_page():
    if 'username' not in session: return redirect(url_for('login'))
    current_username = session['username']
    if request.method == 'POST':
        if 'new_username' in request.form and request.form.get('new_username'):
            new_username = request.form['new_username']
            if new_username == current_username or new_username in USERS:
                flash('Username is the same or already taken.', 'danger')
            else:
                USERS[new_username] = USERS.pop(current_username)
                flash('Username changed! Please log in again.', 'success')
                return redirect(url_for('logout'))
        elif 'forgot_password' in request.form:
            user = USERS[current_username]
            msg = Message("Your Password", sender="noreply@bpm.com", recipients=[user['email']])
            msg.body = f"Hello, your password is: {user['password']}"
            try:
                mail.send(msg)
                flash(f'Reminder sent to {user["email"]}.', 'success')
            except Exception as e:
                flash(f'Failed to send email. Is your debug mail server running? Error: {e}', 'danger')

    return render_template('setup.html', username=current_username, department_name=session['department'])

@app.route('/department/<department_name>', methods=['GET', 'POST'])
def department_dashboard(department_name):
    department, can_edit = get_user_permissions(department_name)
    if not department: return redirect(url_for('login'))
    if request.method == 'POST' and can_edit:
        new_menu_name, parent_menu_id = request.form.get('new_menu_name'), request.form.get('parent_menu_id')
        if new_menu_name:
            department['menu_id_counter'] += 1
            new_item = create_menu_item(new_menu_name, department['menu_id_counter'])
            if parent_menu_id == 'root':
                department['menu'].append(new_item)
            else:
                parent, _, _ = find_item_in_tree(department['menu'], int(parent_menu_id))
                if parent:
                    parent.setdefault('children', []).append(new_item)
            flash('Menu created successfully.', 'success')
        return redirect(url_for('department_dashboard', department_name=department_name))
    return render_template('department_dashboard.html', department_name=department_name, department_menu=copy.deepcopy(department['menu']),
                           flat_menu_list=get_flat_menu_list(department['menu']), can_edit=can_edit, all_departments=DEPARTMENT_DATA.keys())

@app.route('/department/<department_name>/menu/<int:menu_id>', methods=['GET', 'POST'])
def menu_content_page(department_name, menu_id):
    department, can_edit = get_user_permissions(department_name)
    if not department: return redirect(url_for('login'))
    menu_item, _, _ = find_item_in_tree(department['menu'], menu_id)
    if not menu_item or (not menu_item['active'] and not can_edit):
        flash('Menu not found or you do not have permission.', 'danger')
        return redirect(url_for('department_dashboard', department_name=department_name))
    if request.method == 'POST' and can_edit:
        action = request.form.get('action')
        if action == 'add_post' and request.form.get('content'):
            menu_item['post_id_counter'] += 1
            menu_item.setdefault('posts', []).insert(0, {'id': menu_item['post_id_counter'], 'content': request.form['content'], 'active': True})
        elif action == 'add_file' and 'file' in request.files and request.files['file'].filename:
            file = request.files['file']
            filename = secure_filename(file.filename)
            upload_path = os.path.join(app.config['UPLOAD_FOLDER'], department_name, str(menu_id))
            os.makedirs(upload_path, exist_ok=True)
            file.save(os.path.join(upload_path, filename))
            menu_item['file_id_counter'] += 1
            menu_item.setdefault('files', []).insert(0, {'id': menu_item['file_id_counter'], 'filename': filename, 'active': True})
        return redirect(url_for('menu_content_page', department_name=department_name, menu_id=menu_id))
    return render_template('menu_content.html', department_name=department_name, menu_item=copy.deepcopy(menu_item), can_edit=can_edit)

@app.route('/search')
def search():
    if 'username' not in session: return redirect(url_for('login'))
    query = request.args.get('query', '')
    if not query: return redirect(request.referrer or url_for('department_dashboard', department_name=session['department']))
    results = []
    for dept_name, dept_data in DEPARTMENT_DATA.items():
        menu_list = dept_data.get('menu', [])
        def find_in_posts(menus):
            for menu_item in menus:
                if not menu_item['active']: continue
                for post in menu_item.get('posts', []):
                    if post['active'] and query.lower() in post['content'].lower():
                        clean_content = re.sub('<[^<]+?>', ' ', post['content'])
                        match_pos = clean_content.lower().find(query.lower())
                        start = max(0, match_pos - 70)
                        end = min(len(clean_content), match_pos + len(query) + 70)
                        snippet = clean_content[start:end].replace(query, f"<mark>{query}</mark>")
                        results.append({
                            'department': dept_name, 'menu_name': menu_item['name'],
                            'url': url_for('menu_content_page', department_name=dept_name, menu_id=menu_item['id']),
                            'context': snippet
                        })
                if menu_item.get('children'):
                    find_in_posts(menu_item['children'])
        find_in_posts(menu_list)
    return render_template('search_results.html', query=query, results=results)


# --- Action & File Routes (Correctly Formatted) ---
@app.route('/toggle_menu/<department_name>/<int:menu_id>', methods=['POST'])
def toggle_menu_status(department_name, menu_id):
    department, can_edit = get_user_permissions(department_name)
    if not can_edit: return "Access Denied", 403
    menu_item, _, _ = find_item_in_tree(department['menu'], menu_id)
    if menu_item: menu_item['active'] = not menu_item['active']
    return redirect(request.referrer)

@app.route('/delete_menu/<department_name>/<int:menu_id>', methods=['POST'])
def delete_menu(department_name, menu_id):
    department, can_edit = get_user_permissions(department_name)
    if not can_edit: return "Access Denied", 403
    _, parent_list, index = find_item_in_tree(department['menu'], menu_id)
    if parent_list is not None:
        del parent_list[index]
        flash('Menu and all its contents deleted.', 'success')
    return redirect(url_for('department_dashboard', department_name=department_name))

def _toggle_content_status(department_name, menu_id, content_id, content_type):
    department, can_edit = get_user_permissions(department_name)
    if not can_edit: return "Access Denied", 403
    menu_item, _, _ = find_item_in_tree(department['menu'], menu_id)
    if menu_item:
        item = next((i for i in menu_item.get(f'{content_type}s', []) if i['id'] == content_id), None)
        if item: item['active'] = not item['active']
    return redirect(request.referrer)

def _delete_content_item(department_name, menu_id, content_id, content_type):
    department, can_edit = get_user_permissions(department_name)
    if not can_edit: return "Access Denied", 403
    menu_item, _, _ = find_item_in_tree(department['menu'], menu_id)
    if menu_item:
        menu_item[f'{content_type}s'] = [i for i in menu_item.get(f'{content_type}s', []) if i['id'] != content_id]
        flash(f'{content_type.capitalize()} deleted.', 'success')
    return redirect(request.referrer)

@app.route('/toggle_post/<department_name>/<int:menu_id>/<int:post_id>', methods=['POST'])
def toggle_post(department_name, menu_id, post_id): return _toggle_content_status(department_name, menu_id, post_id, 'post')

@app.route('/toggle_file/<department_name>/<int:menu_id>/<int:file_id>', methods=['POST'])
def toggle_file(department_name, menu_id, file_id): return _toggle_content_status(department_name, menu_id, file_id, 'file')

@app.route('/delete_post/<department_name>/<int:menu_id>/<int:post_id>', methods=['POST'])
def delete_post(department_name, menu_id, post_id): return _delete_content_item(department_name, menu_id, post_id, 'post')

@app.route('/delete_file/<department_name>/<int:menu_id>/<int:file_id>', methods=['POST'])
def delete_file(department_name, menu_id, file_id): return _delete_content_item(department_name, menu_id, file_id, 'file')

@app.route('/uploads/<department_name>/<int:menu_id>/<filename>')
def download_file(department_name, menu_id, filename):
    department, can_edit = get_user_permissions(department_name)
    if not department: return "Not Found", 404
    menu_item, _, _ = find_item_in_tree(department['menu'], menu_id)
    if not menu_item: return "Not Found", 404
    file_item = next((f for f in menu_item['files'] if f['filename'] == filename), None)
    if not file_item or (not file_item['active'] and not can_edit):
        return "Access denied.", 403
    upload_path = os.path.join(app.config['UPLOAD_FOLDER'], department_name, str(menu_id))
    return send_from_directory(upload_path, filename, as_attachment=True)


if __name__ == '__main__':
    app.run(debug=True, port=5000)