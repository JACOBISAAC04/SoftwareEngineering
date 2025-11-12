from flask import Blueprint, render_template, request, redirect, url_for, flash
from supabase import create_client, Client
from datetime import datetime
import uuid
import os
from werkzeug.security import generate_password_hash

# Import the shared decorator
from decorators import login_required

add_employee_bp = Blueprint('add_employee_bp', __name__)

# This is redundant if app.py already creates a client, but fixing
# it requires a larger app restructure (e.g., app factory or extensions.py).
# For now, this will work, but it's not ideal.
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_KEY')
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


# ----------------------------------------------
# Show Add Employee form
# ----------------------------------------------
@add_employee_bp.route('/add_employee', methods=['GET'])
@login_required(role='admin') # --- FIX: Use decorator for auth ---
def add_employee_form():
    # The decorator handles the auth check now
    return render_template('add_employee.html')


# ----------------------------------------------
# Handle Add Employee form submission
# ----------------------------------------------
@add_employee_bp.route('/add_employee', methods=['POST'])
@login_required(role='admin') # --- FIX: Use decorator for auth ---
def add_employee_submit():
    # The decorator handles the auth check now
    try:
        full_name = request.form['full_name']
        email = request.form['email']
        phone = request.form['phone']
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        employee_category = request.form['employee_category']
        terminal_id = request.form.get('terminal_id')

        if password != confirm_password:
            flash("Passwords do not match!", "error")
            # --- FIX: Correct url_for for blueprint ---
            return redirect(url_for('add_employee_bp.add_employee_form'))

        # Check if email already exists
        existing = supabase.table("users").select("id").eq("email", email).execute()
        if existing.data:
            flash("Email already exists!", "error")
            # --- FIX: Correct url_for for blueprint ---
            return redirect(url_for("add_employee_bp.add_employee_form"))

        # --- FIX: Hash the password ---
        hashed_password = generate_password_hash(password)

        data = {
            'id': str(uuid.uuid4()),
            'email': email,
            'password': hashed_password, # Store the hash
            'full_name': full_name,
            'phone': phone,
            'role': 'employee',
            'employee_category': employee_category,
            'terminal_id': terminal_id if terminal_id else None,
            'created_at': datetime.utcnow().isoformat(),
            'updated_at': datetime.utcnow().isoformat(),
            'is_active': True
        }

        supabase.table('users').insert(data).execute()
        flash("✅ Employee added successfully!", "success")
        return redirect(url_for('admin_dashboard'))

    except Exception as e:
        flash(f"❌ Error adding employee: {e}", "error")
        # --- FIX: Correct url_for for blueprint ---
        return redirect(url_for('add_employee_bp.add_employee_form'))