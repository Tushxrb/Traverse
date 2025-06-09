from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.hashers import make_password
from django.core.mail import send_mail
from django.contrib import messages
from .models import User
from django.contrib.auth.decorators import login_required, user_passes_test
from datetime import datetime
import random
import logging
from django.http import JsonResponse
from django.conf import settings
import json


def index(req):
    return render(req, "index.html", {})


def employee_login(req):
    try:
        if req.method == 'POST':
            emp_id = req.POST.get('employee_id')
            input_value = req.POST.get('password')  # DOB or password

            if not emp_id or not input_value:
                messages.error(req, 'Employee ID and Password are required.')
                return render(req, 'employee_login.html')

            user = User.objects.filter(employee_id=emp_id).first()

            if not user:
                messages.error(req, 'Employee not found.')
                return render(req, 'employee_login.html')

            # First-time user: no email, verify DOB in ddmmyyyy format
            if not user.email or not user.email.strip():
                expected_dob = user.dob.strftime('%d%m%Y')
                if input_value == expected_dob:
                    req.session['emp_id'] = emp_id
                    req.session['dob'] = expected_dob
                    return redirect('reset_password')
                else:
                    messages.error(req, 'Incorrect Date of Birth.')
                    return render(req, 'employee_login.html')

            # Returning user: authenticate normally
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
        messages.error(req, f"An unexpected error occurred: {str(e)}")
        return render(req, 'index.html')


def reset_password(req):
    emp_id = req.session.get('emp_id')
    dob = req.session.get('dob')  # 'ddmmyyyy'

    if not emp_id or not dob:
        messages.error(req, "Session expired or invalid. Please login again.")
        return redirect('employee_login')

    try:
        dob_obj = datetime.strptime(dob, "%d%m%Y").date()
    except ValueError:
        messages.error(req, "Invalid DOB format. Please login again.")
        return redirect('employee_login')

    user = get_object_or_404(User, employee_id=emp_id, dob=dob_obj)

    if req.method == 'POST':
        email = req.POST.get('email')
        otp = req.POST.get('otp')
        password1 = req.POST.get('password1')
        password2 = req.POST.get('password2')

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

        # Clear OTP session data
        req.session.pop('otp', None)
        req.session.pop('reset_email', None)

        messages.success(req, "Password set successfully. Please login with your new password.")
        return redirect('employee_login')

    return render(req, 'reset_password.html', {'emp_id': emp_id, 'otp_verified': False})


from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.csrf import ensure_csrf_cookie

@ensure_csrf_cookie
def verify_otp(req):
    if req.method == "POST":
        try:
            data = json.loads(req.body)
            email = data.get("email")
        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'message': 'Invalid JSON.'}, status=400)

        if not email:
            return JsonResponse({'success': False, 'message': 'Email is required.'}, status=400)

        if User.objects.filter(email=email).exists():
            return JsonResponse({'success': False, 'message': 'Email already in use. Use another email.'}, status=400)

        otp = str(random.randint(100000, 999999))
        req.session['otp'] = otp
        req.session['reset_email'] = email

        subject = "Traverse - OTP for Email Verification"
        message = f"Your OTP to verify email for Traverse is: {otp}"
        from_email = settings.EMAIL_HOST_USER
        recipient_list = [email]

        send_mail(subject, message, from_email, recipient_list)

        return JsonResponse({'success': True, 'message': 'OTP sent to your email.'})

    return JsonResponse({'success': False, 'message': 'Invalid request method.'}, status=405)


def verify_otp_check(req):
    if req.method == "POST":
        try:
            data = json.loads(req.body)
            email = data.get('email')
            otp = data.get('otp')
        except json.JSONDecodeError:
            return JsonResponse({'valid': False})

        session_otp = req.session.get('otp')
        session_email = req.session.get('reset_email')

        if email == session_email and otp == session_otp:
            return JsonResponse({'valid': True})
        else:
            return JsonResponse({'valid': False})

    return JsonResponse({'valid': False})


def admin_login(request):
    if request.method == 'POST':
        employee_id = request.POST.get('employee_id')
        password = request.POST.get('password')
        user = authenticate(request, employee_id=employee_id, password=password)
        if user is not None and user.is_superuser:
            login(request, user)
            return redirect('admin_dashboard')
        else:
            messages.error(request, "Invalid credentials or not an admin.")
    return render(request, 'admin_login.html')


def is_admin(user):
    return user.is_superuser


@login_required
@user_passes_test(is_admin)
def admin_dashboard(req):
    employees = User.objects.filter(is_superuser=False)
    team_leaders = User.objects.filter(is_super_employee=True)
    addresses = ['Borivali', 'Andheri', 'Dadar', 'Bandra', 'Churchgate']

    if req.method == "POST":
        first_name = req.POST.get("first_name")
        last_name = req.POST.get("last_name")
        digits = req.POST.get("employee_id_digits")

        if not digits or not digits.isdigit() or len(digits) != 4:
            messages.error(req, "Employee ID digits must be exactly 4 numeric characters.")
            return redirect("admin_dashboard")

        employee_id = first_name[0].upper() + last_name[0].upper() + digits

        if User.objects.filter(employee_id=employee_id).exists():
            messages.error(req, f"Employee ID {employee_id} already exists. Please choose different digits.")
            return redirect("admin_dashboard")

        dob = req.POST.get("dob")
        address = req.POST.get("address")
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

    return render(req, "admin_dashboard.html", {
        "employees": employees,
        "team_leaders": team_leaders,
        "addresses": addresses
    })


def delete_user(req, user_id):
    if req.method == "POST":
        User.objects.filter(id=user_id).delete()
    return redirect("admin_dashboard")


def update_users(req):
    if req.method == "POST":
        user_id = req.POST.get("save_id")
        user = get_object_or_404(User, id=user_id)

        first_name = req.POST.get(f"first_name_{user_id}", "").strip()
        last_name = req.POST.get(f"last_name_{user_id}", "").strip()
        dob = req.POST.get(f"dob_{user_id}")
        address = req.POST.get(f"address_{user_id}")
        is_super = req.POST.get(f"is_super_employee_{user_id}") == "on"
        team_leader = req.POST.get(f"team_leader_{user_id}")

        user.first_name = first_name
        user.last_name = last_name
        user.dob = dob
        user.address = address
        user.is_super_employee = is_super
        user.team_leader_id = team_leader if team_leader else None
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
def dashboard(req):
    return render(req, 'dashboard.html')
