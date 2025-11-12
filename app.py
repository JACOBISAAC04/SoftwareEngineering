from flask import Flask, render_template, request, redirect, url_for, flash, session
from supabase import create_client, Client
from datetime import timedelta
from dotenv import load_dotenv
import os
from werkzeug.security import generate_password_hash, check_password_hash

# Import the new decorator
from decorators import login_required

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'wavelink-secret-key-change-this')
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=24)

# Supabase configuration
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_KEY')
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Import blueprints
from add_employee import add_employee_bp
app.register_blueprint(add_employee_bp)

# ---------------------------------
# Root route
# ---------------------------------
@app.route('/')
def index():
    if 'user_id' in session:
        role = session.get('role')
        if role == 'admin':
            return redirect(url_for('admin_dashboard'))
        elif role == 'employee':
            return redirect(url_for('employee_dashboard'))
        elif role == 'passenger':
            return redirect(url_for('passenger_dashboard'))
    # If not logged in, or no role, show landing
    return render_template('landing.html') # Assuming you have a landing.html


# ---------------------------------
# Passenger registration
# ---------------------------------
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        full_name = request.form.get("full_name")
        email = request.form.get("email")
        phone = request.form.get("phone")
        password = request.form.get("password")
        confirm_password = request.form.get("confirm_password")

        if password != confirm_password:
            flash("Passwords do not match!", "error")
            return redirect(url_for("register"))

        # Check if user already exists
        existing = supabase.table("users").select("id").eq("email", email).execute()
        if existing.data:
            flash("Email already registered!", "error")
            return redirect(url_for("register"))

        # --- FIX: Hash the password ---
        hashed_password = generate_password_hash(password)

        data = {
            "full_name": full_name,
            "email": email,
            "phone": phone,
            "password": hashed_password, # Store the hash, not the plain text
            "role": "passenger"
        }

        try:
            supabase.table("users").insert(data).execute()
            flash("Registration successful! Please login.", "success")
            return redirect(url_for("login"))
        except Exception as e:
            flash(f"Error: {str(e)}", "error")
            return redirect(url_for("register"))
    return render_template("register.html")


# ---------------------------------
# Login
# ---------------------------------
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        if not email or not password:
            flash('Email and password are required', 'error')
            return redirect(url_for('login'))

        result = supabase.table('users').select('*').eq('email', email).limit(1).execute()

        if not result.data:
            flash('Invalid email or password', 'error')
            return redirect(url_for('login'))

        user = result.data[0]

        # --- FIX: Check the hashed password ---
        if user.get('password') and check_password_hash(user['password'], password):
            session.permanent = True
            session['user_id'] = user['id']
            session['email'] = user['email']
            session['full_name'] = user['full_name']
            session['role'] = user['role']
            session['employee_category'] = user.get('employee_category')

            flash(f'Welcome back, {user["full_name"]}!', 'success')

            if user['role'] == 'admin':
                return redirect(url_for('admin_dashboard'))
            elif user['role'] == 'employee':
                return redirect(url_for('employee_dashboard'))
            elif user['role'] == 'passenger':
                return redirect(url_for('passenger_dashboard'))
        else:
            flash('Invalid email or password', 'error')
    return render_template('login.html')


# ---------------------------------
# Logout
# ---------------------------------
@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out successfully', 'success')
    return redirect(url_for('index'))


# ---------------------------------
# Dashboards
# ---------------------------------
@app.route('/admin/dashboard')
@login_required(role='admin')
def admin_dashboard():
    try:
        # Use .count() for cleaner count fetching
        total_users = supabase.table('users').select('id', count='exact').execute()
        employees = supabase.table('users').select('id', count='exact').eq('role', 'employee').execute()
        passengers = supabase.table('users').select('id', count='exact').eq('role', 'passenger').execute()

        stats = {
            'total_users': total_users.count or 0,
            'employees': employees.count or 0,
            'passengers': passengers.count or 0,
        }

        return render_template('admin_dashboard.html', stats=stats)
    except Exception as e:
        flash(f'Error loading dashboard: {str(e)}', 'error')
        return render_template('admin_dashboard.html', stats={})


@app.route('/employee/dashboard')
@login_required(role='employee')
def employee_dashboard():
    category = session.get('employee_category', 'General')
    return render_template('er.html', category=category)


@app.route('/passenger/dashboard')
@login_required(role='passenger')
def passenger_dashboard():
    return render_template('passenger_dashboard.html')


@app.route('/profile')
@login_required()
def profile():
    user_id = session.get('user_id')
    try:
        data = supabase.table('users').select('*').eq('id', user_id).single().execute()
        if data.data:
            return render_template('profile.html', user=data.data)
        else:
            flash('User not found', 'error')
            return redirect(url_for('index'))
    except Exception as e:
        flash(f'Error loading profile: {str(e)}', 'error')
        return redirect(url_for('index'))


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)