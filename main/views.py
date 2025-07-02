from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout, get_user_model
from django.contrib.auth.hashers import make_password
from django.core.mail import send_mail
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.conf import settings
from django.contrib.auth.decorators import login_required, user_passes_test
from django.views.decorators.csrf import ensure_csrf_cookie
from django.core.files.base import ContentFile

import json
import random
import logging
import datetime
import razorpay
import pandas as pd
from io import BytesIO

from .models import User, Schedule, CutoffRecord

# ----------------------
# Utility functions
# ----------------------

def is_admin(user):
    # Check if the user is an admin (superuser)
    return user.is_superuser

def get_week_dates():
    # Get all dates and day names for next week (Monday to Sunday)
    today = datetime.date.today()
    # Find next week's Monday
    days_until_next_monday = 7 - today.weekday()
    next_monday = today + datetime.timedelta(days=days_until_next_monday)
    return [((next_monday + datetime.timedelta(days=i)).strftime('%Y-%m-%d'), (next_monday + datetime.timedelta(days=i)).strftime('%A')) for i in range(7)]

# ----------------------
# Views
# ----------------------

def index(req):
    # Show the home page
    return render(req, "index.html")

def employee_login(req):
    # Employee login view
    try:
        if req.method == 'POST':
            emp_id = req.POST.get('employee_id', '').strip()
            input_value = req.POST.get('password', '').strip()

            # Check if both fields are filled
            if not emp_id or not input_value:
                messages.error(req, 'Employee ID and Password are required.')
                return render(req, 'employee_login.html')

            # Find user by employee ID
            user = User.objects.filter(employee_id=emp_id).first()

            if not user:
                messages.error(req, 'No employee found with this Employee ID.')
                return render(req, 'employee_login.html')

            # Prevent admin login from employee login page
            if user.is_superuser:
                messages.error(req, 'You are an admin. Please use the Admin Login page.')
                return render(req, 'employee_login.html')

            # If user has no email, use DOB as password for first login
            if not user.email or not user.email.strip():
                try:
                    expected_dob = user.dob.strftime('%d%m%Y')
                except Exception:
                    messages.error(req, 'User record is missing Date of Birth. Please contact admin.')
                    return render(req, 'employee_login.html')
                if input_value == expected_dob:
                    req.session['emp_id'] = emp_id
                    req.session['dob'] = expected_dob
                    return redirect('reset_password')
                else:
                    messages.error(req, 'Incorrect Date of Birth.')
                    return render(req, 'employee_login.html')

            # Authenticate user with employee_id and password
            auth_user = authenticate(req, employee_id=emp_id, password=input_value)
            if auth_user:
                login(req, auth_user)
                return redirect('dashboard')
            else:
                messages.error(req, 'Invalid Employee ID or Password.')
                return render(req, 'employee_login.html')

        # Show login page for GET request
        return render(req, 'employee_login.html')

    except Exception as e:
        logging.exception("Error in employee_login view:")
        messages.error(req, f"Unexpected error: {str(e)}")
        return render(req, 'employee_login.html')  # Changed from index.html

def reset_password(req):
    # Reset password for first-time login or forgot password
    emp_id = req.session.get('emp_id')
    dob = req.session.get('dob')

    if not emp_id or not dob:
        messages.error(req, "Session expired or invalid. Please login again.")
        return redirect('employee_login')

    try:
        dob_obj = datetime.datetime.strptime(dob, "%d%m%Y").date()
    except ValueError:
        messages.error(req, "Invalid DOB format.")
        return redirect('employee_login')

    user = get_object_or_404(User, employee_id=emp_id, dob=dob_obj)

    if req.method == 'POST':
        email = req.POST.get('email', '').strip()
        otp = req.POST.get('otp', '').strip()
        password1 = req.POST.get('password1', '')
        password2 = req.POST.get('password2', '')

        session_otp = req.session.get('otp')
        session_email = req.session.get('reset_email')

        # Check OTP and email
        if not session_otp or otp != str(session_otp) or email != session_email: 
            return render(req, 'reset_password.html', { 'emp_id': emp_id, 'otp_verified': False, 'error': 'Invalid OTP or email mismatch.' }) 
        
        # Check if passwords match
        if password1 != password2:
            return render(req, 'reset_password.html', { 'emp_id': emp_id, 'otp_verified': True, 'email': email, 'error': 'Passwords do not match.' }) 
        
        # Check if email is provided
        if not email: 
            return render(req, 'reset_password.html', { 'emp_id': emp_id, 'otp_verified': True, 'error': 'Email is required.' }) 
        
        # Set email and new password
        user.email = email 
        user.password = make_password(password1) 
        user.save() # Save user

        # Clear session data
        req.session.pop('otp', None) 
        req.session.pop('reset_email', None) 
        req.session.pop('emp_id', None) 
        req.session.pop('dob', None) 

        messages.success(req, "Password set successfully. Please login with your new password.") 
        return redirect('employee_login') 
    
    # Show reset password page
    return render(req, 'reset_password.html', {'emp_id': emp_id, 'otp_verified': False})

@ensure_csrf_cookie
def verify_otp(req):
    # Send OTP to email for verification
    if req.method == "POST":
        try:
            data = json.loads(req.body)
            email = data.get("email", "").strip()
        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'message': 'Invalid JSON.'}, status=400)

        if not email:
            return JsonResponse({'success': False, 'message': 'Email is required.'}, status=400)

        # Check if email already exists
        if User.objects.filter(email=email).exists():
            return JsonResponse({'success': False, 'message': 'Email already in use.'}, status=400)

        # Generate OTP and save in session
        otp = str(random.randint(100000, 999999))
        req.session['otp'] = otp
        req.session['reset_email'] = email

        try:
            subject = f"#{otp}: OTP for Email Verification - Traverse"
            message = (
                f"Dear User,\n\n"
                f"We received a request to verify your email address for Traverse. Please use the following One-Time Password (OTP) to complete the verification:\n\n"
                f"🔐 OTP: {otp}\n\n"
                f"This OTP is valid for the current session and should not be shared with anyone.\n\n"
                f"If you did not initiate this request, please contact your company's administrator.\n\n"
                f"Regards,\n"
                f"Team Traverse"
            )
            from_email = settings.EMAIL_HOST_USER
            send_mail(subject, message, from_email, [email])
            return JsonResponse({'success': True, 'message': 'OTP sent to your email.'})
        except Exception as e:
            return JsonResponse({'success': False, 'message': 'Failed to send OTP. Please try again.'})

    return JsonResponse({'success': False, 'message': 'Invalid request method.'}, status=405)

def verify_otp_check(req):
    # Check if OTP and email match session
    if req.method == "POST":
        try:
            data = json.loads(req.body)
            email = data.get('email', '').strip()
            otp = data.get('otp', '').strip()
        except json.JSONDecodeError:
            return JsonResponse({'valid': False})

        if email == req.session.get('reset_email') and otp == req.session.get('otp'):
            return JsonResponse({'valid': True})
        return JsonResponse({'valid': False})

    return JsonResponse({'valid': False})

def admin_login(request):
    # Admin login view
    if request.method == 'POST':
        emp_id = request.POST.get('employee_id', '').strip()
        password = request.POST.get('password', '')
        
        # Check if both fields are filled
        if not emp_id or not password:
            messages.error(request, 'Employee ID and Password are required.')
            return render(request, 'admin_login.html')
            
        # Authenticate admin
        user = authenticate(request, employee_id=emp_id, password=password)
        if user and user.is_superuser:
            login(request, user)
            return redirect('admin_dashboard')
        else:
            messages.error(request, "Invalid credentials or not an admin.")
            return render(request, 'admin_login.html')
            
    # Show admin login page
    return render(request, 'admin_login.html')

@login_required
@user_passes_test(is_admin)
def admin_dashboard(req):
    # Admin dashboard for managing employees
    addresses = ['Borivali', 'Andheri', 'Dadar', 'Bandra', 'Churchgate']

    if req.method == "POST":
        first_name = req.POST.get("first_name", "").strip()
        last_name = req.POST.get("last_name", "").strip()
        digits = req.POST.get("employee_id_digits", "").strip()

        # Validation for required fields
        if not first_name or not last_name:
            messages.error(req, "First name and last name are required.")
            return render(req, "admin_dashboard.html", {
                "employees": User.objects.filter(is_superuser=False),
                "team_leaders": User.objects.filter(is_super_employee=True),
                "addresses": addresses
            })

        if not digits.isdigit() or len(digits) != 4:
            messages.error(req, "Employee ID digits must be exactly 4 numbers.")
            return render(req, "admin_dashboard.html", {
                "employees": User.objects.filter(is_superuser=False),
                "team_leaders": User.objects.filter(is_super_employee=True),
                "addresses": addresses
            })

        # Generate employee ID
        employee_id = first_name[0].upper() + last_name[0].upper() + digits

        # Check if employee ID already exists
        if User.objects.filter(employee_id=employee_id).exists():
            messages.error(req, f"Employee ID {employee_id} already exists.")
            return render(req, "admin_dashboard.html", {
                "employees": User.objects.filter(is_superuser=False),
                "team_leaders": User.objects.filter(is_super_employee=True),
                "addresses": addresses
            })

        dob = req.POST.get("dob")
        if not dob:
            messages.error(req, "Date of birth is required.")
            return render(req, "admin_dashboard.html", {
                "employees": User.objects.filter(is_superuser=False),
                "team_leaders": User.objects.filter(is_super_employee=True),
                "addresses": addresses
            })

        address = req.POST.get("address", "")
        if not address:
            messages.error(req, "Address is required.")
            return render(req, "admin_dashboard.html", {
                "employees": User.objects.filter(is_superuser=False),
                "team_leaders": User.objects.filter(is_super_employee=True),
                "addresses": addresses
            })

        is_super_emp = req.POST.get("is_super_employee") == "on"
        team_leader_id = req.POST.get("team_leader")

        try:
            # Create new user
            user = User.objects.create_user(
                username=employee_id,
                first_name=first_name,
                last_name=last_name,
                dob=dob,
                employee_id=employee_id,
                address=address,
                is_super_employee=is_super_emp,
                team_leader_id=team_leader_id if team_leader_id else None,
                password="temp@1234"
            )
            messages.success(req, f"{user.get_full_name()} added successfully with ID {user.employee_id}")
        except Exception as e:
            messages.error(req, f"Error creating user: {str(e)}")

        # Show dashboard again with updated list
        return render(req, "admin_dashboard.html", {
            "employees": User.objects.filter(is_superuser=False),
            "team_leaders": User.objects.filter(is_super_employee=True),
            "addresses": addresses
        })

    # Show dashboard with employees and team leaders
    employees = User.objects.filter(is_superuser=False)
    team_leaders = User.objects.filter(is_super_employee=True)

    return render(req, "admin_dashboard.html", {
        "employees": employees,
        "team_leaders": team_leaders,
        "addresses": addresses
    })

@login_required
@user_passes_test(is_admin)
def delete_user(req, user_id):
    # Delete a user (admin only)
    if req.method == "POST":
        try:
            user = get_object_or_404(User, id=user_id)
            user_name = user.get_full_name()
            user.delete()
            messages.success(req, f"{user_name} deleted successfully.")
        except Exception as e:
            messages.error(req, f"Error deleting user: {str(e)}")
    return redirect("admin_dashboard")

@login_required
@user_passes_test(is_admin)
def update_users(req):
    # Update user details (admin only)
    if req.method == "POST":
        user_id = req.POST.get("save_id")
        try:
            user = get_object_or_404(User, id=user_id)

            # Get the form data
            first_name = req.POST.get(f"first_name_{user_id}", "").strip()
            last_name = req.POST.get(f"last_name_{user_id}", "").strip()
            dob = req.POST.get(f"dob_{user_id}")
            address = req.POST.get(f"address_{user_id}")
            is_super_employee = req.POST.get(f"is_super_employee_{user_id}") == "on"
            team_leader_id = req.POST.get(f"team_leader_{user_id}") or None

            # Validation for required fields
            if not first_name or not last_name:
                messages.error(req, "First name and last name are required.")
                return redirect("admin_dashboard")

            if not dob:
                messages.error(req, "Date of birth is required.")
                return redirect("admin_dashboard")

            if not address:
                messages.error(req, "Address is required.")
                return redirect("admin_dashboard")

            # Update user fields
            user.first_name = first_name
            user.last_name = last_name
            user.dob = dob
            user.address = address
            user.is_super_employee = is_super_employee
            user.team_leader_id = team_leader_id

            user.save()
            messages.success(req, f"{user.get_full_name()} updated successfully.")

        except Exception as e:
            messages.error(req, f"Error updating user: {str(e)}")

    return redirect("admin_dashboard")

def admin_logout(request):
    # Log out admin
    logout(request)
    return redirect('index')

def employee_logout(request):
    # Log out employee
    logout(request)
    return redirect('index')

@login_required
def save_schedule(request):
    # Save employee's weekly schedule
    if request.method == "POST":
        user = request.user
        dates = request.POST.getlist('dates')
        types = request.POST.getlist('types')
        timings = request.POST.getlist('timings')

        try:
            # Delete existing schedules for this user for the week
            Schedule.objects.filter(employee=user).delete()

            # Save new schedules for each day
            saved_count = 0
            for date_str, schedule_type, timing in zip(dates, types, timings):
                if date_str and schedule_type and timing:
                    # Convert date string to date object
                    date_obj = datetime.datetime.strptime(date_str, '%Y-%m-%d').date()
                    day_name = date_obj.strftime('%A')
                    
                    Schedule.objects.create(
                        employee=user,
                        date=date_obj,
                        day=day_name,
                        type=schedule_type,
                        timing=timing
                    )
                    saved_count += 1

            if saved_count > 0:
                messages.success(request, f"Schedule saved successfully for {saved_count} days.")
            else:
                messages.warning(request, "No schedule entries were saved. Please fill in the required fields.")

        except Exception as e:
            messages.error(request, f"Error saving schedule: {str(e)}")

    return redirect("dashboard")

# Add this decorator to the cutoff_schedule function
@login_required
@user_passes_test(is_admin)
def cutoff_schedule(request):
    # Export all schedules for next week to Excel (admin only)
    if request.method == "POST":
        try:
            today = datetime.date.today()
            # Get all schedules for next week (to match the dashboard and form logic)
            days_until_next_monday = 7 - today.weekday()
            next_monday = today + datetime.timedelta(days=days_until_next_monday)
            week_start = next_monday
            week_end = next_monday + datetime.timedelta(days=6)

            schedules = Schedule.objects.filter(
                date__gte=week_start,
                date__lte=week_end
            ).select_related('employee')

            if not schedules.exists():
                messages.warning(request, "No schedules found for next week.")
                return redirect("admin_dashboard")

            records = []
            for schedule in schedules:
                emp = schedule.employee
                records.append({
                    'Employee ID': emp.employee_id,
                    'Name': emp.get_full_name(),
                    'Address': emp.address,
                    'Date': schedule.date.strftime('%Y-%m-%d'),
                    'Day': schedule.day,
                    'Type': schedule.type,
                    'Timing': schedule.timing,
                })

            df = pd.DataFrame(records)
            # Group by address and type for better organization
            grouped = df.groupby(['Address', 'Type'])

            output = BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                # Write all data to main sheet
                df.to_excel(writer, sheet_name='All_Schedules', index=False)
                # Write grouped data to separate sheets
                for (addr, schedule_type), group in grouped:
                    sheet_name = f"{addr[:10]}_{schedule_type}"
                    group.to_excel(writer, sheet_name=sheet_name[:31], index=False)

            output.seek(0)
            filename = f"weekly_schedule_{week_start.strftime('%Y%m%d')}.xlsx"
            # Save to database
            cutoff_file = ContentFile(output.read(), name=filename)
            CutoffRecord.objects.create(
                generated_by=request.user,
                excel_file=cutoff_file
            )

            # Reset output position for download
            output.seek(0)
            response = HttpResponse(
                output.read(),
                content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            messages.success(request, f"Schedule exported successfully as {filename}")
            return response

        except Exception as e:
            messages.error(request, f"Error exporting schedule: {str(e)}")
            return redirect("admin_dashboard")

    return redirect("admin_dashboard")

def save_team_schedule(request):
    # Team leader saves schedule for their team member
    if request.method == 'POST' and request.user.is_super_employee:
        user_id = request.POST.get('team_member_id')
        dates = request.POST.getlist('dates')
        types = request.POST.getlist('types')
        timings = request.POST.getlist('timings')

        try:
            user = get_object_or_404(User, id=user_id, team_leader=request.user)
            
            # Delete existing schedules for this team member
            Schedule.objects.filter(employee=user).delete()

            saved_count = 0
            for date_str, schedule_type, timing in zip(dates, types, timings):
                if date_str and schedule_type and timing:
                    date_obj = datetime.datetime.strptime(date_str, '%Y-%m-%d').date()
                    day_name = date_obj.strftime('%A')
                    
                    Schedule.objects.create(
                        employee=user,
                        date=date_obj,
                        day=day_name,
                        type=schedule_type,
                        timing=timing
                    )
                    saved_count += 1

            if saved_count > 0:
                messages.success(request, f"Team member schedule saved successfully for {saved_count} days.")
            else:
                messages.warning(request, "No schedule entries were saved for team member.")

        except Exception as e:
            messages.error(request, f"Error saving team schedule: {str(e)}")

    return redirect('dashboard')


@login_required
def get_current_schedule(request):
    """API endpoint to fetch current user's schedule"""
    user = request.user
    today = datetime.date.today()
    
    # Get current week's schedules
    week_start = today - datetime.timedelta(days=today.weekday())
    week_end = week_start + datetime.timedelta(days=6)
    
    schedules = Schedule.objects.filter(
        employee=user,
        date__gte=week_start,
        date__lte=week_end
    ).order_by('date', 'type')
    
    schedule_data = []
    for schedule in schedules:
        schedule_data.append({
            'date': schedule.date.strftime('%Y-%m-%d'),
            'day': schedule.day,
            'type': schedule.type,
            'timing': schedule.timing,
            'display_date': schedule.date.strftime('%a, %b %d')
        })
    
    return JsonResponse({'schedules': schedule_data})

# Update your existing dashboard view to include current schedule data
@login_required
def dashboard(request):
    user = request.user
    is_super_employee = user.is_super_employee

    week_dates = get_week_dates()
    week_dates_json = json.dumps([(str(d), day) for d, day in week_dates])

    # Get current schedule for the week
    week_start = week_dates[0][0]  # First date of the week
    week_end = week_dates[-1][0]   # Last date of the week
    
    current_schedules = Schedule.objects.filter(
        employee=user,
        date__gte=week_start,
        date__lte=week_end
    ).order_by('date')

    team_members = []
    if is_super_employee:
        team_members = User.objects.filter(team_leader=user)

    return render(request, 'dashboard.html', {
        'user': user,
        'week_dates': week_dates,
        'week_dates_json': week_dates_json,
        'current_schedules': current_schedules,
        'is_super_employee': is_super_employee,
        'team_members': team_members,
    })

def pricing(request):
    # Show pricing page
    return render(request, 'pricing.html')

# Plan amounts in paise (for Razorpay)
PLAN_AMOUNTS = {
    'starter': 50000,   # 500.00 INR
    'popular': 100000,  # 1000.00 INR
    'premium': 150000,  # 1500.00 INR (fixed amount to match pricing page)
}

def start_payment(request):
    # Start Razorpay payment for selected plan
    if request.method == "POST":
        plan = request.POST.get("plan")
        amount_paise = PLAN_AMOUNTS.get(plan)
        if not amount_paise:
            messages.error(request, "Invalid plan selected.")
            return render(request, "pricing.html")

        amount_rupees = amount_paise // 100  # For display

        try:
            # Create Razorpay order
            client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
            order = client.order.create({
                "amount": amount_paise,
                "currency": "INR",
                "payment_capture": 1
            })

            context = {
                "order_id": order["id"],
                "amount": amount_paise,  # For Razorpay
                "display_amount": amount_rupees,  # For user display
                "razorpay_key_id": settings.RAZORPAY_KEY_ID,
            }
            return render(request, "payment.html", context)
            
        except Exception as e:
            messages.error(request, f"Error creating payment order: {str(e)}")
            return render(request, "pricing.html")
            
    # Show pricing page for GET request
    return render(request, "pricing.html")

def services(request):
    return render(request, "services.html")