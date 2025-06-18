# Traverse

Traverse is a Django-based employee transport management system built for organizations to streamline pickup and drop services. It offers secure, role-based authentication, an intuitive dashboard, and easy request handling for employees and team leaders.

---

## Features

- **Custom Employee Authentication**  
  Employees log in using their Employee ID and Date of Birth (first-time) or password (after setup).

- **OTP-Based Password Reset**  
  First-time users verify their email via OTP before setting a secure password.

- **Role Management**  
  Supports regular employees, team leaders (super employees), and admins.

- **Pickup & Drop Requests**  
  Employees can raise transport requests; team leaders can raise them on behalf of their team members.

- **Admin Dashboard**  
  Admins can manage all users, assign roles, and view requests.

- **Responsive Interface**  
  Mobile-friendly UI with background animations and clean Bootstrap styling.

---

## Modules Overview

- `User Model`: Extends Django's `AbstractUser` to use `employee_id` as the username field and includes DOB, address, team leader linkage, and role flags.
- `Employee Login`: Handles dual login logic (DOB/password) and redirects accordingly.
- `Password Reset`: Uses AJAX and OTP via email for secure credential setup.
- `Team Leader Functionality`: Authorized to view and manage team requests.
- `Admin Controls`: Admins can add/edit employees, assign leaders, and manage pickup/drop data.

---

## URL Paths

- `/employee_login/` — Employee login page  
- `/admin_login/` — Admin login page  
- `/reset_password/` — OTP and password setup  
- `/dashboard/` — Employee dashboard after login  
- `/admin_dashboard/` — Admin dashboard  

---

## Project Structure

- `traverse/` — Django project settings and configuration  
- `myapp/` — Application logic, models, views, forms, and templates  
- `templates/` — HTML templates for all user interfaces  
- `static/` — Assets including CSS, JS, and video background  

---

## Tech Stack

- Python + Django  
- HTML + Bootstrap 5  
- JavaScript (AJAX with Fetch API)  
- SQLite (default) / PostgreSQL (optional)

---

## Contributors

Built and maintained by **Tushar Vivek Banjan**.

---

## License

This project is licensed under the **MIT License**.
