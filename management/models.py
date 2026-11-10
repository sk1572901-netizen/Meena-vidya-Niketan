from django.db import models
from django.contrib.auth.models import AbstractUser
from django.conf import settings 

# 1. कस्टम यूजर मॉडल (यहाँ से एडमिन, टीचर और पेरेंट्स मैनेज होंगे)
class User(AbstractUser):
    IS_ADMIN = 'ADMIN'
    IS_TEACHER = 'TEACHER'
    IS_PARENT = 'PARENT'
    
    ROLE_CHOICES = [
        (IS_ADMIN, 'Admin'),
        (IS_TEACHER, 'Teacher'),
        (IS_PARENT, 'Parent'),
    ]
    
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default=IS_PARENT)
    phone_number = models.CharField(max_length=15, blank=True, null=True)
    address = models.TextField(blank=True, null=True)

# 2. टीचर मॉडल (टीचर की अतिरिक्त जानकारी के लिए)
class TeacherProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, limit_choices_to={'role': 'TEACHER'})
    qualification = models.CharField(max_length=100)
    salary = models.DecimalField(max_digits=10, decimal_places=2)
    joining_date = models.DateField(auto_now_add=True)
    biometric_device_id = models.CharField(max_length=50, blank=True, null=True) # IoT अटेंडेंस के लिए

    def _str_(self):
        return f"Teacher: {self.user.get_full_name()}"

# 3. स्टूडेंट मॉडल
class Student(models.Model):
    parent_user = models.ForeignKey(User, on_delete=models.CASCADE, limit_choices_to={'role': 'PARENT'}, related_name="children")
    first_name = models.CharField(max_length=50)
    last_name = models.CharField(max_length=50)
    roll_number = models.CharField(max_length=20, unique=True)
    current_class = models.CharField(max_length=20) # उदा: Class 10, Class 5
    section = models.CharField(max_length=5) # उदा: A, B
    admission_date = models.DateField(auto_now_add=True)
    rfid_tag_id = models.CharField(max_length=50, blank=True, null=True) # IoT/बायोमेट्रिक अटेंडेंस के लिए

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.roll_number})"

# 4. अटेंडेंस मॉडल (बायोमेट्रिक और मोबाइल दोनों के लिए काम करेगा)
class Attendance(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE, blank=True, null=True)
    teacher = models.ForeignKey(TeacherProfile, on_delete=models.CASCADE, blank=True, null=True)
    date = models.DateField(auto_now_add=True)
    time = models.TimeField(auto_now_add=True)
    status = models.CharField(max_length=10, choices=[('PRESENT', 'Present'), ('ABSENT', 'Absent')], default='PRESENT')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
    def __str__(self):
        name = self.student.first_name if self.student else self.teacher.user.first_name
        return f"{name} - {self.date} - {self.status}"
from django.db import models
from django.contrib.auth.models import User

# Purane models (Student, Attendance, etc.) ko waisa hi rehne dein...

# --- Naya Model Photo Upload Ke Liye ---
class AttendanceImage(models.Model):
    teacher = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    uploaded_at = models.DateTimeField(auto_now_add=True) # Kis time upload hua
    attendance_date = models.DateField() # Kis din ki attendance hai
    attendance_photo = models.ImageField(upload_to='attendance_sheets/') # Photo path (Corrected 'upload_to')
    
    # AI/OCR process hone ke baad summary store karne ke liye fields
    total_p_detected = models.IntegerField(default=0)
    total_a_detected = models.IntegerField(default=0)
    is_processed = models.BooleanField(default=False) # Kya AI ne process kar liya hai?

    def __str__(self):
        return f"Sheet by {self.teacher.username} on {self.attendance_date}"