from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db import models
from django.conf import settings



class User(AbstractUser):
    is_super_employee = models.BooleanField(default=False)
    employee_id = models.CharField(max_length=6, unique=True, blank=True)
    dob = models.DateField(null=True, blank=True)
    address = models.CharField(max_length=100, choices=[
        ('Borivali', 'Borivali'),
        ('Andheri', 'Andheri'),
        ('Dadar', 'Dadar'),
        ('Bandra', 'Bandra'),
        ('Churchgate', 'Churchgate'),
    ])
    team_leader = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='team_members'
    )

    groups = models.ManyToManyField(
        'auth.Group',
        related_name='custom_user_set',
        blank=True,
        help_text='The groups this user belongs to.',
        verbose_name='groups'
    )
    user_permissions = models.ManyToManyField(
        'auth.Permission',
        related_name='custom_user_permissions_set',
        blank=True,
        help_text='Specific permissions for this user.',
        verbose_name='user permissions'
    )

    USERNAME_FIELD = 'employee_id'
    REQUIRED_FIELDS = ['username']

    def __str__(self):
        return f"{self.get_full_name()} ({self.employee_id})"
    

from django.db import models
from django.conf import settings

class Schedule(models.Model):
    DAY_CHOICES = [
        ('Monday', 'Monday'),
        ('Tuesday', 'Tuesday'),
        ('Wednesday', 'Wednesday'),
        ('Thursday', 'Thursday'),
        ('Friday', 'Friday'),
    ]

    TYPE_CHOICES = [
        ('Pickup', 'Pickup'),
        ('Drop', 'Drop'),
    ]

    employee = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    day = models.CharField(max_length=10, choices=DAY_CHOICES)
    pickup_time = models.TimeField(blank=True, null=True)
    drop_time = models.TimeField(blank=True, null=True)
    date = models.DateField(auto_now_add=True)
    type = models.CharField(max_length=10, choices=TYPE_CHOICES, blank=True, null=True)
    timing = models.CharField(max_length=20, blank=True, null=True)

    def __str__(self):
        return f"{self.employee.employee_id} - {self.day}"


class CutoffRecord(models.Model):
    cutoff_date = models.DateTimeField(auto_now_add=True)
    generated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    excel_file = models.FileField(upload_to='cutoff_excels/')

    def __str__(self):
        return f"Cutoff on {self.cutoff_date.strftime('%Y-%m-%d %H:%M')}"

