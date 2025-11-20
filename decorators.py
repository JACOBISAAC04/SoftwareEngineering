from functools import wraps
from flask import session, flash, redirect, url_for

def login_required(role=None):
    """
    Decorator to require login and optionally a specific role.
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session:
                flash('Please login to access this page', 'error')
                return redirect(url_for('login'))
            if role == 'any':
                return f(*args, **kwargs)
            if role and session.get('role') != role:
                flash('Unauthorized access. You do not have permission to view this page.', 'error')
                # Redirect to their own dashboard or index
                user_role = session.get('role', 'passenger')
                if user_role == 'admin':
                    return redirect(url_for('admin_dashboard'))
                elif user_role == 'employee':
                    return redirect(url_for('employee_dashboard'))
                else:
                    return redirect(url_for('passenger_dashboard'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator