from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from supabase import create_client, Client
from datetime import datetime
import uuid
import os

# Import the shared decorator
from decorators import login_required

passenger_bp = Blueprint('passenger_bp', __name__)

# Re-create the Supabase client for this blueprint
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_KEY')
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- Helper function to generate 30-min time slots ---
def get_time_slots():
    """Generates time slots from 08:00 to 20:00 in 30-min intervals."""
    slots = []
    for hour in range(8, 21): # 8 AM to 8 PM (20:xx)
        slots.append(f"{hour:02d}:00")
        if hour != 20: # Don't add 20:30
            slots.append(f"{hour:02d}:30")
    return slots
# -----------------------------------------------------------

@passenger_bp.route('/dashboard')
@login_required(role='passenger')
def passenger_dashboard():
    """
    Main passenger dashboard.
    Now includes logic to fetch preferences and data for the form.
    """
    user_id = session.get('user_id')
    preferences = []
    terminals = []
    
    try:
        # --- MODIFIED: Fetch route name AND base_price ---
        pref_response = supabase.table('passenger_preferences').select('id, preferred_time, routes(name, base_price)') \
            .eq('passenger_id', user_id).order('preferred_time').execute()
        if pref_response.data:
            preferences = pref_response.data
            
        # Fetch all terminals for the dropdowns
        term_response = supabase.table('terminals').select('*').order('name').execute()
        if term_response.data:
            terminals = term_response.data

    except Exception as e:
        flash(f"Error loading dashboard data: {e}", "error")

    # Get the 30-minute time slots for the dropdown
    time_slots = get_time_slots()

    return render_template(
        'passenger_dashboard.html',
        preferences=preferences,
        terminals=terminals,
        time_slots=time_slots
    )

@passenger_bp.route('/save_preferences', methods=['POST'])
@login_required(role='passenger')
def save_preferences():
    """
    Saves the notification preferences from the dashboard form.
    --- MODIFIED: This function now ONLY ADDS new preferences. ---
    """
    user_id = session.get('user_id')
    
    try:
        # Get the lists of inputs from the form
        from_terminal_ids = request.form.getlist('from_terminal_id')
        to_terminal_ids = request.form.getlist('to_terminal_id')
        preferred_times = request.form.getlist('preferred_time')

        # --- MODIFIED: No longer deletes old preferences ---
        # supabase.table('passenger_preferences').delete().eq('passenger_id', user_id).execute()

        # Batch insert the new preferences
        new_prefs_data = []
        
        for from_id, to_id, time_str in zip(from_terminal_ids, to_terminal_ids, preferred_times):
            if not from_id or not to_id or not time_str:
                continue # Skip incomplete rows

            if from_id == to_id:
                flash(f"'From' and 'To' terminals cannot be the same. Skipping row.", "error")
                continue

            # Find the route that matches this from/to pair
            route_response = supabase.table('routes').select('id') \
                .eq('origin_terminal_id', from_id) \
                .eq('destination_terminal_id', to_id) \
                .limit(1).execute()

            if route_response.data:
                route_id = route_response.data[0]['id']
                
                # --- NEW: Check if this preference already exists ---
                existing_pref = supabase.table('passenger_preferences') \
                    .select('id') \
                    .eq('passenger_id', user_id) \
                    .eq('route_id', route_id) \
                    .eq('preferred_time', time_str) \
                    .limit(1).execute()
                
                if not existing_pref.data:
                    new_prefs_data.append({
                        'passenger_id': user_id,
                        'route_id': route_id,
                        'preferred_time': time_str
                    })
                else:
                    flash(f"Preference already exists and was skipped.", "info")
            else:
                flash(f"Could not find a valid route for one of your selections. Skipping.", "error")

        # Insert all new preferences in one go
        if new_prefs_data:
            supabase.table('passenger_preferences').insert(new_prefs_data).execute()

        flash("New preferences saved successfully!", "success")

    except Exception as e:
        flash(f"Error saving preferences: {e}", "error")

    return redirect(url_for('passenger_bp.passenger_dashboard'))

# --- NEW: Route to delete a single preference ---
@passenger_bp.route('/delete_preference/<preference_id>', methods=['POST'])
@login_required(role='passenger')
def delete_preference(preference_id):
    """
    Deletes a single preference entry.
    """
    user_id = session.get('user_id')
    try:
        # Delete the preference, but ONLY if it belongs to the logged-in user
        response = supabase.table('passenger_preferences').delete() \
            .eq('id', preference_id) \
            .eq('passenger_id', user_id) \
            .execute()
        
        if response.data:
            flash("Preference removed successfully.", "success")
        else:
            flash("Could not find preference to remove.", "error")
            
    except Exception as e:
        flash(f"Error removing preference: {e}", "error")

    return redirect(url_for('passenger_bp.passenger_dashboard'))
# --- END NEW ROUTE ---


# --- Feedback Routes ---

@passenger_bp.route('/feedback', methods=['GET', 'POST'])
@login_required(role='passenger')
def give_feedback():
    if request.method == 'POST':
        try:
            user_id = session.get('user_id')
            subject = request.form.get('subject')
            message = request.form.get('message')
            files = request.files.getlist('attachments')

            if not message:
                flash("Message is required.", "error")
                return redirect(url_for('passenger_bp.give_feedback'))

            # 1. Insert feedback text
            feedback_entry = {
                "passenger_id": user_id,
                "subject": subject,
                "message": message
            }
            feedback_res = supabase.table('feedbacks').insert(feedback_entry).execute()
            feedback_id = feedback_res.data[0]['id']

            # 2. Handle file uploads
            if files and feedback_id:
                attachment_entries = []
                for file in files:
                    if file.filename:
                        # Create a unique file path
                        file_ext = os.path.splitext(file.filename)[1]
                        file_name = f"{user_id}/{feedback_id}_{uuid.uuid4()}{file_ext}"
                        
                        # Upload to Supabase Storage (bucket 'pdfs')
                        supabase.storage.from_('pdfs').upload(file_name, file.read())
                        
                        # Get public URL
                        public_url = supabase.storage.from_('pdfs').get_public_url(file_name)
                        
                        attachment_entries.append({
                            "feedback_id": feedback_id,
                            "file_url": public_url,
                            "file_type": file.mimetype
                        })

                # 3. Insert attachment records
                if attachment_entries:
                    supabase.table('attachments').insert(attachment_entries).execute()

            flash("Feedback submitted successfully!", "success")
            return redirect(url_for('passenger_bp.previous_feedbacks'))

        except Exception as e:
            flash(f"Error submitting feedback: {e}", "error")
    
    return render_template('give_feedback.html')

@passenger_bp.route('/my_feedbacks')
@login_required(role='passenger')
def previous_feedbacks():
    feedbacks = []
    try:
        user_id = session.get('user_id')
        # Fetch feedbacks AND their related attachments in one query
        response = supabase.table('feedbacks').select('*, attachments(*)') \
            .eq('passenger_id', user_id).order('submitted_at', desc=True).execute()
        
        if response.data:
            feedbacks = response.data
            
    except Exception as e:
        flash(f"Error loading feedback history: {e}", "error")

    return render_template('previous_feedbacks.html', feedbacks=feedbacks)


# --- Complaint Routes ---

@passenger_bp.route('/complaint', methods=['GET', 'POST'])
@login_required(role='passenger')
def give_complaint():
    if request.method == 'POST':
        try:
            user_id = session.get('user_id')
            subject = request.form.get('subject')
            message = request.form.get('message')
            files = request.files.getlist('attachments')

            if not message:
                flash("Complaint message is required.", "error")
                return redirect(url_for('passenger_bp.give_complaint'))

            # 1. Insert complaint text
            complaint_entry = {
                "passenger_id": user_id,
                "subject": subject,
                "message": message,
                "status": "pending"
            }
            complaint_res = supabase.table('complaints').insert(complaint_entry).execute()
            complaint_id = complaint_res.data[0]['id']

            # 2. Handle file uploads
            if files and complaint_id:
                attachment_entries = []
                for file in files:
                    if file.filename:
                        file_ext = os.path.splitext(file.filename)[1]
                        file_name = f"{user_id}/complaint_{complaint_id}_{uuid.uuid4()}{file_ext}"
                        
                        supabase.storage.from_('pdfs').upload(file_name, file.read())
                        public_url = supabase.storage.from_('pdfs').get_public_url(file_name)
                        
                        attachment_entries.append({
                            "complaint_id": complaint_id,
                            "file_url": public_url,
                            "file_type": file.mimetype
                        })

                # 3. Insert attachment records
                if attachment_entries:
                    supabase.table('attachments').insert(attachment_entries).execute()

            flash("Complaint submitted successfully! We will review it shortly.", "success")
            return redirect(url_for('passenger_bp.previous_complaints'))

        except Exception as e:
            flash(f"Error submitting complaint: {e}", "error")
            
    return render_template('give_complaint.html')

@passenger_bp.route('/my_complaints')
@login_required(role='passenger')
def previous_complaints():
    complaints = []
    try:
        user_id = session.get('user_id')
        # Fetch complaints AND their related attachments
        response = supabase.table('complaints').select('*, attachments(*)') \
            .eq('passenger_id', user_id).order('submitted_at', desc=True).execute()
        
        if response.data:
            complaints = response.data
            
    except Exception as e:
        flash(f"Error loading complaint history: {e}", "error")

    return render_template('previous_complaints.html', complaints=complaints)