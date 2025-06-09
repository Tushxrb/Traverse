from django.contrib.auth.models import AbstractUser
from django.db import models

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
