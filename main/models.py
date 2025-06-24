from django.db import models
from django.conf import settings
from django.contrib.auth.models import AbstractUser

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

class Schedule(models.Model):
    DAY_CHOICES = [
        ('Monday', 'Monday'),
        ('Tuesday', 'Tuesday'),
        ('Wednesday', 'Wednesday'),
        ('Thursday', 'Thursday'),
        ('Friday', 'Friday'),
        ('Saturday', 'Saturday'),
        ('Sunday', 'Sunday'),
    ]

    TYPE_CHOICES = [
        ('Pickup', 'Pickup'),
        ('Drop', 'Drop'),
    ]

    employee = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    day = models.CharField(max_length=10, choices=DAY_CHOICES)
    date = models.DateField()  # Specific date for the schedule
    
    # Legacy fields - kept for backward compatibility
    pickup_time = models.TimeField(blank=True, null=True)
    drop_time = models.TimeField(blank=True, null=True)
    
    # New fields for better structure
    type = models.CharField(max_length=10, choices=TYPE_CHOICES, blank=True, null=True)
    timing = models.CharField(max_length=20, blank=True, null=True)  # Store as HH:MM string
    
    class Meta:
        # Ensure one schedule per employee per date per type
        unique_together = ['employee', 'date', 'type']
        ordering = ['date', 'employee__employee_id', 'type']

    def __str__(self):
        if self.type and self.timing:
            return f"{self.employee.employee_id} - {self.date} - {self.type} at {self.timing}"
        return f"{self.employee.employee_id} - {self.day} - {self.date}"

    def get_time_display(self):
        """Return formatted time for display"""
        if self.timing:
            return self.timing
        elif self.type == 'Pickup' and self.pickup_time:
            return self.pickup_time.strftime('%H:%M')
        elif self.type == 'Drop' and self.drop_time:
            return self.drop_time.strftime('%H:%M')
        return ''

    def get_location(self):
        """Return employee's address/location"""
        return self.employee.address

class CutoffRecord(models.Model):
    cutoff_date = models.DateTimeField(auto_now_add=True)
    generated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    excel_file = models.FileField(upload_to='cutoff_excels/')
    
    # Additional fields for better tracking
    total_schedules = models.IntegerField(default=0)
    date_range_start = models.DateField(null=True, blank=True)
    date_range_end = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ['-cutoff_date']

    def __str__(self):
        return f"Cutoff on {self.cutoff_date.strftime('%Y-%m-%d %H:%M')} by {self.generated_by}"