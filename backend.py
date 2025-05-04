from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
import json
import os
import datetime
from functools import wraps

app = Flask(__name__)
app.secret_key = "supersecretkey"  # Change this in production

# Admin credentials
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin123"  # Change this in production

# Database file paths
DB_DIR = "database"
PRODUCT_DB = os.path.join(DB_DIR, "product.json")
CATEGORY_DB = os.path.join(DB_DIR, "category.json")
USERS_DB = os.path.join(DB_DIR, "users.json")
WARNING_DB = os.path.join(DB_DIR, "warning.json")

# Helper functions for database operations
def read_json(file_path):
    try:
        with open(file_path, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def write_json(file_path, data):
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, 'w') as f:
        json.dump(data, f, indent=4)

# Authentication decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            flash('Please log in first', 'danger')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# Routes
@app.route('/')
def index():
    if 'logged_in' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session['logged_in'] = True
            flash('Login successful', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid credentials', 'danger')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out successfully', 'success')
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html')

# Product Routes
@app.route('/products')
@login_required
def products():
    products_data = read_json(PRODUCT_DB)
    return render_template('products.html', products=products_data)

@app.route('/products/add', methods=['GET', 'POST'])
@login_required
def add_product():
    if request.method == 'POST':
        product_name = request.form.get('name')
        category = request.form.get('category')
        description = request.form.get('description')
        images = request.form.get('images')
        filename = request.form.get('filename')
        price = int(request.form.get('price', 0))
        
        products_data = read_json(PRODUCT_DB)
        
        if product_name in products_data:
            flash('Product already exists', 'danger')
        else:
            products_data[product_name] = {
                'category': category,
                'description': description,
                'images': images,
                'filename': filename,
                'price': price
            }
            write_json(PRODUCT_DB, products_data)
            flash('Product added successfully', 'success')
            return redirect(url_for('products'))
    
    categories = read_json(CATEGORY_DB)
    return render_template('add_product.html', categories=categories)

@app.route('/products/edit/<product_name>', methods=['GET', 'POST'])
@login_required
def edit_product(product_name):
    products_data = read_json(PRODUCT_DB)
    
    if product_name not in products_data:
        flash('Product not found', 'danger')
        return redirect(url_for('products'))
    
    if request.method == 'POST':
        category = request.form.get('category')
        description = request.form.get('description')
        images = request.form.get('images')
        filename = request.form.get('filename')
        price = int(request.form.get('price', 0))
        
        products_data[product_name] = {
            'category': category,
            'description': description,
            'images': images,
            'filename': filename,
            'price': price
        }
        write_json(PRODUCT_DB, products_data)
        flash('Product updated successfully', 'success')
        return redirect(url_for('products'))
    
    categories = read_json(CATEGORY_DB)
    return render_template('edit_product.html', product_name=product_name, product=products_data[product_name], categories=categories)

@app.route('/products/delete/<product_name>', methods=['POST'])
@login_required
def delete_product(product_name):
    products_data = read_json(PRODUCT_DB)
    
    if product_name in products_data:
        del products_data[product_name]
        write_json(PRODUCT_DB, products_data)
        flash('Product deleted successfully', 'success')
    else:
        flash('Product not found', 'danger')
    
    return redirect(url_for('products'))

# Category Routes
@app.route('/categories')
@login_required
def categories():
    categories_data = read_json(CATEGORY_DB)
    return render_template('categories.html', categories=categories_data)

@app.route('/categories/add', methods=['GET', 'POST'])
@login_required
def add_category():
    if request.method == 'POST':
        category_name = request.form.get('name')
        category_id = int(request.form.get('id'))
        
        categories_data = read_json(CATEGORY_DB)
        
        if category_name in categories_data:
            flash('Category already exists', 'danger')
        else:
            categories_data[category_name] = category_id
            write_json(CATEGORY_DB, categories_data)
            flash('Category added successfully', 'success')
            return redirect(url_for('categories'))
    
    return render_template('add_category.html')

@app.route('/categories/edit/<category_name>', methods=['GET', 'POST'])
@login_required
def edit_category(category_name):
    categories_data = read_json(CATEGORY_DB)
    
    if category_name not in categories_data:
        flash('Category not found', 'danger')
        return redirect(url_for('categories'))
    
    if request.method == 'POST':
        new_category_id = int(request.form.get('id'))
        
        categories_data[category_name] = new_category_id
        write_json(CATEGORY_DB, categories_data)
        flash('Category updated successfully', 'success')
        return redirect(url_for('categories'))
    
    return render_template('edit_category.html', category_name=category_name, category_id=categories_data[category_name])

@app.route('/categories/delete/<category_name>', methods=['POST'])
@login_required
def delete_category(category_name):
    categories_data = read_json(CATEGORY_DB)
    
    if category_name in categories_data:
        del categories_data[category_name]
        write_json(CATEGORY_DB, categories_data)
        flash('Category deleted successfully', 'success')
    else:
        flash('Category not found', 'danger')
    
    return redirect(url_for('categories'))

# Users Routes
@app.route('/users')
@login_required
def users():
    users_data = read_json(USERS_DB)
    return render_template('users.html', users=users_data)

@app.route('/users/add', methods=['GET', 'POST'])
@login_required
def add_user():
    if request.method == 'POST':
        user_id = request.form.get('user_id')
        total_payment = int(request.form.get('total_payment', 0))
        
        users_data = read_json(USERS_DB)
        
        if user_id in users_data:
            flash('User already exists', 'danger')
        else:
            users_data[user_id] = {
                'total-payment': total_payment,
                'ownership': {}
            }
            write_json(USERS_DB, users_data)
            flash('User added successfully', 'success')
            return redirect(url_for('users'))
    
    return render_template('add_user.html')

@app.route('/users/edit/<user_id>', methods=['GET', 'POST'])
@login_required
def edit_user(user_id):
    users_data = read_json(USERS_DB)
    
    if user_id not in users_data:
        flash('User not found', 'danger')
        return redirect(url_for('users'))
    
    if request.method == 'POST':
        total_payment = int(request.form.get('total_payment', 0))
        
        users_data[user_id]['total-payment'] = total_payment
        write_json(USERS_DB, users_data)
        flash('User updated successfully', 'success')
        return redirect(url_for('users'))
    
    return render_template('edit_user.html', user_id=user_id, user=users_data[user_id])

@app.route('/users/delete/<user_id>', methods=['POST'])
@login_required
def delete_user(user_id):
    users_data = read_json(USERS_DB)
    
    if user_id in users_data:
        del users_data[user_id]
        write_json(USERS_DB, users_data)
        flash('User deleted successfully', 'success')
    else:
        flash('User not found', 'danger')
    
    return redirect(url_for('users'))

@app.route('/users/<user_id>/products')
@login_required
def user_products(user_id):
    users_data = read_json(USERS_DB)
    
    if user_id not in users_data:
        flash('User not found', 'danger')
        return redirect(url_for('users'))
    
    return render_template('user_products.html', user_id=user_id, ownership=users_data[user_id]['ownership'])

@app.route('/users/<user_id>/add_product', methods=['GET', 'POST'])
@login_required
def add_user_product(user_id):
    users_data = read_json(USERS_DB)
    products_data = read_json(PRODUCT_DB)
    
    if user_id not in users_data:
        flash('User not found', 'danger')
        return redirect(url_for('users'))
    
    if request.method == 'POST':
        product_name = request.form.get('product_name')
        license_key = request.form.get('license_key')
        
        if product_name not in products_data:
            flash('Product not found', 'danger')
        else:
            users_data[user_id]['ownership'][product_name] = license_key
            write_json(USERS_DB, users_data)
            flash('Product added to user successfully', 'success')
            return redirect(url_for('user_products', user_id=user_id))
    
    # Filter out already owned products
    available_products = {name: data for name, data in products_data.items() 
                          if name not in users_data[user_id]['ownership']}
    
    return render_template('add_user_product.html', user_id=user_id, products=available_products)

@app.route('/users/<user_id>/remove_product/<product_name>', methods=['POST'])
@login_required
def remove_user_product(user_id, product_name):
    users_data = read_json(USERS_DB)
    
    if user_id not in users_data:
        flash('User not found', 'danger')
    elif product_name not in users_data[user_id]['ownership']:
        flash('Product not found for this user', 'danger')
    else:
        del users_data[user_id]['ownership'][product_name]
        write_json(USERS_DB, users_data)
        flash('Product removed from user successfully', 'success')
    
    return redirect(url_for('user_products', user_id=user_id))

# Warning Routes
@app.route('/warnings')
@login_required
def warnings():
    warnings_data = read_json(WARNING_DB)
    return render_template('warnings.html', warnings=warnings_data)

@app.route('/warnings/add', methods=['GET', 'POST'])
@login_required
def add_warning():
    if request.method == 'POST':
        server_id = request.form.get('server_id')
        user_id = request.form.get('user_id')
        reason = request.form.get('reason')
        moderator_id = request.form.get('moderator_id')
        
        warnings_data = read_json(WARNING_DB)
        
        if server_id not in warnings_data:
            warnings_data[server_id] = {}
        
        if user_id not in warnings_data[server_id]:
            warnings_data[server_id][user_id] = []
        
        warning_entry = {
            'reason': reason,
            'timestamp': datetime.datetime.now().isoformat(),
            'moderator': moderator_id
        }
        
        warnings_data[server_id][user_id].append(warning_entry)
        write_json(WARNING_DB, warnings_data)
        flash('Warning added successfully', 'success')
        return redirect(url_for('warnings'))
    
    return render_template('add_warning.html')

@app.route('/warnings/delete/<server_id>/<user_id>/<int:index>', methods=['POST'])
@login_required
def delete_warning(server_id, user_id, index):
    warnings_data = read_json(WARNING_DB)
    
    if (server_id in warnings_data and 
        user_id in warnings_data[server_id] and 
        0 <= index < len(warnings_data[server_id][user_id])):
        
        warnings_data[server_id][user_id].pop(index)
        
        # Clean up empty entries
        if not warnings_data[server_id][user_id]:
            del warnings_data[server_id][user_id]
            if not warnings_data[server_id]:
                del warnings_data[server_id]
        
        write_json(WARNING_DB, warnings_data)
        flash('Warning deleted successfully', 'success')
    else:
        flash('Warning not found', 'danger')
    
    return redirect(url_for('warnings'))

# API Routes
@app.route('/api/products', methods=['GET'])
def api_products():
    products_data = read_json(PRODUCT_DB)
    return jsonify(products_data)

@app.route('/api/categories', methods=['GET'])
def api_categories():
    categories_data = read_json(CATEGORY_DB)
    return jsonify(categories_data)

@app.route('/api/users', methods=['GET'])
def api_users():
    # In a real app, you would require authentication here
    users_data = read_json(USERS_DB)
    return jsonify(users_data)

@app.route('/api/warnings', methods=['GET'])
def api_warnings():
    # In a real app, you would require authentication here
    warnings_data = read_json(WARNING_DB)
    return jsonify(warnings_data)

if __name__ == '__main__':
    # Ensure the database directory exists
    os.makedirs(DB_DIR, exist_ok=True)
    
    # Create empty files if they don't exist
    for db_file in [PRODUCT_DB, CATEGORY_DB, USERS_DB, WARNING_DB]:
        if not os.path.exists(db_file):
            write_json(db_file, {})
    
    app.run(debug=True)