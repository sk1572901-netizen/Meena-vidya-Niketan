import csv
import cv2
import easyocr
import numpy as np
import re  # Bounding box text pattern match karne ke liye
from datetime import date, datetime
from django.http import HttpResponse
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from .models import TeacherProfile, Student, Attendance, AttendanceImage

# ==========================================
# 1. Main Home Page View
# ==========================================
def home(request):
    return render(request, 'management/home.html')


# ==========================================
# 2. Teacher Login View
# ==========================================
def teacher_login(request):
    error = None
    if request.method == 'POST':
        login_identity = request.POST.get('login_identity')
        pass_word = request.POST.get('password')
        
        username = login_identity
        
        # चेक करें कि क्या यूजर ने मोबाइल नंबर डाला है (सिर्फ नंबर्स)
        if login_identity.isdigit():
            try:
                profile = TeacherProfile.objects.get(mobile=login_identity)
                username = profile.user.username
            except TeacherProfile.DoesNotExist:
                username = None

        # अगर यूजर मिल गया या यूजरनेम डायरेक्ट डाला था, तो ऑथेंटिकेट करें
        if username:
            user = authenticate(request, username=username, password=pass_word)
            if user is not None:
                login(request, user)
                return redirect('teacher_dashboard')
            else:
                error = "Invalid Username/Mobile or Password!"
        else:
            error = "No user found with this Mobile Number!"
            
    return render(request, 'management/login.html', {'error': error})


# ==========================================
# 3. Teacher Dashboard View (Dynamic Summary)
# ==========================================
def teacher_dashboard(request):
    if not request.user.is_authenticated:
        return redirect('teacher_login')
        
    today = date.today()
    
    # Aaj ki date mein kul kitne bacche Present (P) aur Absent (A) hain
    total_present = Attendance.objects.filter(date=today, status='P').count()
    total_absent = Attendance.objects.filter(date=today, status='A').count()
    total_students = Student.objects.count()
    
    context = {
        'total_present': total_present,
        'total_absent': total_absent,
        'total_students': total_students,
        'today': today.strftime('%d-%m-%Y'),
    }
    return render(request, 'management/dashboard.html', context)


# ==========================================
# 4. Attendance Lene Ka View (Manual)
# ==========================================
def mark_attendance(request):
    if not request.user.is_authenticated:
        return redirect('teacher_login')
        
    students = Student.objects.all()
    today = date.today()
    success = False

    if request.method == 'POST':
        for student in students:
            status = request.POST.get(f'student_{student.id}')
            # पुरानी आज की अटेंडेंस डिलीट करके नई सेव करेंगे
            Attendance.objects.filter(student=student, date=today).delete()
            Attendance.objects.create(student=student, date=today, status=status)
        success = True

    return render(request, 'management/attendance.html', {'students': students, 'today': today, 'success': success})


# ==========================================
# 5. Saved Attendance Dekhne Ka View
# ==========================================
def view_attendance(request):
    if not request.user.is_authenticated:
        return redirect('teacher_login')
    
    selected_date = request.GET.get('date_filter')
    selected_class = request.GET.get('class_filter')
    selected_section = request.GET.get('section_filter')
    
    if not selected_date:
        selected_date = str(date.today())
        
    records = Attendance.objects.filter(date=selected_date)
    
    if selected_class:
        records = records.filter(student__current_class=selected_class)
        
    if selected_section:
        records = records.filter(student__section=selected_section)
        
    records = records.order_by('student__roll_number')
        
    context = {
        'records': records,
        'selected_date': selected_date,
        'selected_class': selected_class,
        'selected_section': selected_section
    }
    return render(request, 'management/view_attendance.html', context)


# ==========================================
# 6. Student Management (Add & List) View
# ==========================================
def manage_students(request):
    if not request.user.is_authenticated:
        return redirect('teacher_login')
    
    if request.method == "POST":
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        roll_number = request.POST.get('roll_number')
        current_class = request.POST.get('current_class')
        section = request.POST.get('section')
        
        try:
            Student.objects.create(
                first_name=first_name,
                last_name=last_name,
                roll_number=roll_number,
                current_class=current_class,
                section=section,
                parent_user=request.user 
            )
            messages.success(request, f"छात्र {first_name} {last_name} को सफलतापूर्वक जोड़ दिया गया है!")
        except Exception as e:
            messages.error(request, f"Asli Error: {e}")
            
        return redirect('manage_students')

    students = Student.objects.all().order_by('current_class', 'roll_number')
    
    context = {
        'students': students
    }
    return render(request, 'management/manage_students.html', context)


# ==========================================
# 7. Teacher Logout View
# ==========================================
def teacher_logout(request):
    logout(request)
    return redirect('home')


# ==========================================
# 8. UPGRADED: AI Logic for Grid Register
# ==========================================
def upload_and_process_sheet(request):
    if not request.user.is_authenticated:
        return redirect('teacher_login')

    if request.method == 'POST':
        attendance_date_str = request.POST.get('attendance_date')
        photo = request.FILES.get('attendance_photo')
        
        # Date string ko Python date object mein badalna
        attendance_date = datetime.strptime(attendance_date_str, '%Y-%m-%d').date()

        # 1. Database mein Entry save karna
        bulk_entry = AttendanceImage.objects.create(
            teacher=request.user,
            attendance_date=attendance_date,
            attendance_photo=photo
        )

        # 2. Advanced OpenCV Image Processing
        image_path = bulk_entry.attendance_photo.path
        img = cv2.imread(image_path)
        
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        processed_img = cv2.adaptiveThreshold(
            gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2
        )
        cv2.imwrite(image_path, processed_img)

        # 3. EasyOCR Reader Initialize karna
        reader = easyocr.Reader(['en'])
        results = reader.readtext(image_path)

        roll_rows = {}  
        attendance_tokens = []  

        # 4. Bounding Box coordinates parse karna
        for (bbox, text, prob) in results:
            clean_text = text.strip().upper()
            if not clean_text:
                continue
            
            (top_left, top_right, bottom_right, bottom_left) = bbox
            center_x = int((top_left[0] + bottom_right[0]) / 2)
            center_y = int((top_left[1] + bottom_right[1]) / 2)

            # Agar text sirf Roll Number hai (Left side of image margin)
            if clean_text.isdigit() and center_x < (img.shape[1] * 0.25):
                roll_rows[center_y] = int(clean_text)
            
            # Agar text P ya A hai
            elif clean_text in ['P', 'A']:
                attendance_tokens.append((center_x, center_y, clean_text))

        matched_students_count = 0
        p_count = 0
        a_count = 0

        # 5. Row Matching Logic (Y-axis vertical coordinate map karna)
        for token_x, token_y, status_char in attendance_tokens:
            closest_roll = None
            min_y_diff = 25  # Pixels margin for grid row alignment

            for roll_y, roll_no in roll_rows.items():
                y_diff = abs(token_y - roll_y)
                if y_diff < min_y_diff:
                    min_y_diff = y_diff
                    closest_roll = roll_no

            if closest_roll is not None:
                if status_char == 'P':
                    status = 'P'  # Aapke dashboard models ke format ke mutabik 'P'
                    p_count += 1
                else:
                    status = 'A'  # 'A' for Absent
                    a_count += 1

                try:
                    student = Student.objects.get(roll_number=closest_roll)
                    Attendance.objects.update_or_create(
                        student=student,
                        date=attendance_date,
                        defaults={'status': status}
                    )
                    matched_students_count += 1
                except Student.DoesNotExist:
                    continue

        # 6. Database data update
        bulk_entry.total_p_detected = p_count
        bulk_entry.total_a_detected = a_count
        bulk_entry.is_processed = True
        bulk_entry.save()

        messages.success(
            request, 
            f"🎯 Register Scan Complete! AI ne line-grid matching se {matched_students_count} bacchon ki attendance direct register se update kar di hai! (Present: {p_count}, Absent: {a_count})"
        )
        return redirect('teacher_dashboard')

    return render(request, 'management/upload_sheet.html')


# ==========================================
# 9. Monthly Report Download (Excel/CSV Export)
# ==========================================
def export_attendance_csv(request):
    if not request.user.is_authenticated:
        return redirect('teacher_login')
        
    selected_month = request.GET.get('month', date.today().month)
    selected_year = request.GET.get('year', date.today().year)
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="Attendance_Report_{selected_month}_{selected_year}.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['Roll Number', 'First Name', 'Last Name', 'Class', 'Section', 'Date', 'Status'])
    
    records = Attendance.objects.filter(
        date__month=selected_month, 
        date__year=selected_year
    ).order_by('date', 'student__roll_number')
    
    for record in records:
        writer.writerow([
            record.student.roll_number,
            record.student.first_name,
            record.student.last_name,
            record.student.current_class,
            record.student.section,
            record.date.strftime('%d-%m-%Y'),
            record.status
        ])
        
    return response