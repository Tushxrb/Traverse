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

# Utility functions
def is_admin(user):
    return user.is_superuser

def get_week_dates():
    today = datetime.date.today()
    start = today - datetime.timedelta(days=today.weekday())  # Monday
    return [(start + datetime.timedelta(days=i), (start + datetime.timedelta(days=i)).strftime('%A')) for i in range(7)]

# Views
def index(req):
    return render(req, "index.html")

def employee_login(req):
    try:
        if req.method == 'POST':
            emp_id = req.POST.get('employee_id', '').strip()
            input_value = req.POST.get('password', '').strip()

            if not emp_id or not input_value:
                messages.error(req, 'Employee ID and Password are required.')
                return render(req, 'employee_login.html')

            user = User.objects.filter(employee_id=emp_id).first()
            if not user:
                messages.error(req, 'Employee not found.')
                return render(req, 'employee_login.html')

            if not user.email or not user.email.strip():
                expected_dob = user.dob.strftime('%d%m%Y')
                if input_value == expected_dob:
                    req.session['emp_id'] = emp_id
                    req.session['dob'] = expected_dob
                    return redirect('reset_password')
                else:
                    messages.error(req, 'Incorrect Date of Birth.')
                    return render(req, 'employee_login.html')

            auth_user = authenticate(req, employee_id=emp_id, password=input_value)
            if auth_user:
                login(req, auth_user)
                return redirect('dashboard')
            else:
                messages.error(req, 'Invalid credentials.')
                return render(req, 'employee_login.html')

        return render(req, 'employee_login.html')

    except Exception as e:
        logging.exception("Error in employee_login view:")
        messages.error(req, f"Unexpected error: {str(e)}")
        return render(req, 'index.html')

def reset_password(req):
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

        if not session_otp or otp != str(session_otp) or email != session_email:
            messages.error(req, "Invalid OTP or email mismatch.")
            return render(req, 'reset_password.html', {'emp_id': emp_id, 'otp_verified': False})

        if password1 != password2:
            messages.error(req, "Passwords do not match.")
            return render(req, 'reset_password.html', {'emp_id': emp_id, 'otp_verified': True, 'email': email})

        if not email:
            messages.error(req, "Email is required.")
            return render(req, 'reset_password.html', {'emp_id': emp_id, 'otp_verified': True})

        user.email = email
        user.password = make_password(password1)
        user.save()

        req.session.pop('otp', None)
        req.session.pop('reset_email', None)

        messages.success(req, "Password set successfully. Please login with your new password.")
        return redirect('employee_login')

    return render(req, 'reset_password.html', {'emp_id': emp_id, 'otp_verified': False})

@ensure_csrf_cookie
def verify_otp(req):
    if req.method == "POST":
        try:
            data = json.loads(req.body)
            email = data.get("email", "").strip()
        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'message': 'Invalid JSON.'}, status=400)

        if not email:
            return JsonResponse({'success': False, 'message': 'Email is required.'}, status=400)

        if User.objects.filter(email=email).exists():
            return JsonResponse({'success': False, 'message': 'Email already in use.'}, status=400)

        otp = str(random.randint(100000, 999999))
        req.session['otp'] = otp
        req.session['reset_email'] = email

        subject = "Traverse - OTP for Email Verification"
        message = f"Your OTP to verify email for Traverse is: {otp}"
        from_email = settings.EMAIL_HOST_USER
        send_mail(subject, message, from_email, [email])

        return JsonResponse({'success': True, 'message': 'OTP sent to your email.'})

    return JsonResponse({'success': False, 'message': 'Invalid request method.'}, status=405)

def verify_otp_check(req):
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
    if request.method == 'POST':
        emp_id = request.POST.get('employee_id', '').strip()
        password = request.POST.get('password', '')
        user = authenticate(request, employee_id=emp_id, password=password)
        if user and user.is_superuser:
            login(request, user)
            return redirect('admin_dashboard')
        messages.error(request, "Invalid credentials or not an admin.")
    return render(request, 'admin_login.html')

@login_required
@user_passes_test(is_admin)
def admin_dashboard(req):
    addresses = ['Borivali', 'Andheri', 'Dadar', 'Bandra', 'Churchgate']

    if req.method == "POST":
        first_name = req.POST.get("first_name", "").strip()
        last_name = req.POST.get("last_name", "").strip()
        digits = req.POST.get("employee_id_digits", "").strip()

        if not digits.isdigit() or len(digits) != 4:
            messages.error(req, "Employee ID digits must be exactly 4 numbers.")
            return redirect("admin_dashboard")

        employee_id = first_name[0].upper() + last_name[0].upper() + digits

        if User.objects.filter(employee_id=employee_id).exists():
            messages.error(req, f"Employee ID {employee_id} already exists.")
            return redirect("admin_dashboard")

        dob = req.POST.get("dob")
        address = req.POST.get("address", "")
        is_super_emp = req.POST.get("is_super_employee") == "on"
        team_leader_id = req.POST.get("team_leader")

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
        messages.success(req, f"{user.get_full_name()} added with ID {user.employee_id}")
        return redirect("admin_dashboard")

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
    if req.method == "POST":
        User.objects.filter(id=user_id).delete()
    return redirect("admin_dashboard")

@login_required
@user_passes_test(is_admin)
def update_users(req):
    if req.method == "POST":
        user_id = req.POST.get("save_id")
        user = get_object_or_404(User, id=user_id)

        user.first_name = req.POST.get(f"first_name_{user_id}", "").strip()
        user.last_name = req.POST.get(f"last_name_{user_id}", "").strip()
        user.dob = req.POST.get(f"dob_{user_id}")
        user.address = req.POST.get(f"address_{user_id}")
        user.is_super_employee = req.POST.get(f"is_super_employee_{user_id}") == "on"
        user.team_leader_id = req.POST.get(f"team_leader_{user_id}") or None

        user.save()
        messages.success(req, f"{user.get_full_name()} updated.")

    return redirect("admin_dashboard")

def admin_logout(request):
    logout(request)
    return redirect('admin_login')

def employee_logout(request):
    logout(request)
    return redirect('employee_login')

@login_required
def dashboard(request):
    user = request.user
    is_super_employee = user.is_super_employee

    week_dates = get_week_dates()
    week_dates_json = json.dumps([(str(d), day) for d, day in week_dates])

    team_members = []
    if is_super_employee:
        team_members = User.objects.filter(team_leader=user)

    return render(request, 'dashboard.html', {
        'user': user,
        'week_dates': week_dates,
        'week_dates_json': week_dates_json,
        'is_super_employee': is_super_employee,
        'team_members': team_members,
    })

@login_required
def save_schedule(request):
    if request.method == "POST":
        user = request.user
        for day in ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']:
            pickup_time = request.POST.get(f'pickup_{day.lower()}')
            drop_time = request.POST.get(f'drop_{day.lower()}')

            schedule, created = Schedule.objects.get_or_create(employee=user, day=day)
            schedule.pickup_time = pickup_time
            schedule.drop_time = drop_time
            schedule.save()

        messages.success(request, "Schedule saved successfully.")
    return redirect("dashboard")

@login_required
def cutoff_view(request):
    today = datetime.date.today()
    schedules = Schedule.objects.filter(date=today).select_related('employee')

    records = []
    for schedule in schedules:
        emp = schedule.employee
        records.append({
            'Employee ID': emp.employee_id,
            'Name': emp.get_full_name(),
            'Address': emp.address,
            'Day': schedule.day,
            'Pickup Time': schedule.pickup_time.strftime("%H:%M") if schedule.pickup_time else '',
            'Drop Time': schedule.drop_time.strftime("%H:%M") if schedule.drop_time else '',
        })

    df = pd.DataFrame(records)
    grouped = df.groupby(['Address', 'Pickup Time', 'Drop Time'])

    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        for (addr, ptime, dtime), group in grouped:
            sheet_name = f"{addr[:10]}_{ptime or 'NoPU'}_{dtime or 'NoDR'}"
            group.to_excel(writer, sheet_name=sheet_name[:31], index=False)

    output.seek(0)
    filename = f"cutoff_{today.strftime('%Y%m%d')}.xlsx"
    cutoff_file = ContentFile(output.read(), name=filename)
    CutoffRecord.objects.create(
        generated_by=request.user,
        excel_file=cutoff_file
    )

    response = HttpResponse(cutoff_file, content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response

def save_team_schedule(request):
    if request.method == 'POST':
        user_id = request.POST.get('team_member_id')
        dates = request.POST.getlist('dates')
        types = request.POST.getlist('types')
        timings = request.POST.getlist('timings')

        user = get_object_or_404(User, id=user_id)
        Schedule.objects.filter(employee=user).delete()

        for d, t, tm in zip(dates, types, timings):
            if d and t and tm:
                Schedule.objects.create(
                    employee=user,
                    date=d,
                    day=datetime.datetime.strptime(d, '%Y-%m-%d').strftime('%A'),
                    type=t,
                    timing=tm
                )

    return redirect('dashboard')

def pricing(request):
    return render(request, 'pricing.html')

PLAN_AMOUNTS = {
    'starter': 50000,   # 500.00 INR
    'popular': 100000,  # 1000.00 INR
    'premium': 200000,  # 2000.00 INR
}

def start_payment(request):
    if request.method == "POST":
        plan = request.POST.get("plan")
        amount_paise = PLAN_AMOUNTS.get(plan)
        if not amount_paise:
            return render(request, "pricing.html", {"error": "Invalid plan selected."})

        amount_rupees = amount_paise // 100  # For display

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
    return render(request, "pricing.html")
