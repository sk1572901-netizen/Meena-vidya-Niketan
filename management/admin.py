from django.contrib import admin
from import_export import resources
from import_export.admin import ImportExportModelAdmin
from .models import Student, Attendance, TeacherProfile, AttendanceImage

# --- Admin Interface Customization ---
admin.site.site_header = "Meena Vidya Niketan Administration"
admin.site.site_title = "MVN Admin Portal"
admin.site.index_title = "Welcome to School Management Database"


# --- 1. Student Import-Export Resource ---
class StudentResource(resources.ModelResource):
    class Meta:
        model = Student


# --- 2. Student Model Presentation (ImportExport Enabled) ---
@admin.register(Student)
class StudentAdmin(ImportExportModelAdmin):
    resource_class = StudentResource
    list_display = ('roll_number', 'first_name', 'last_name', 'current_class', 'section')
    search_fields = ('first_name', 'last_name', 'roll_number')
    list_filter = ('current_class', 'section')
    ordering = ('current_class', 'roll_number')


# --- 3. Attendance Model Presentation ---
@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = ('date', 'student', 'status')
    list_filter = ('date', 'status', 'student__current_class')
    search_fields = ('student_first_name', 'student_last_name')


# --- 4. Teacher Profile Presentation ---
@admin.register(TeacherProfile)
class TeacherProfileAdmin(admin.ModelAdmin):
    list_display = ('user',)
    search_fields = ('user__username',)


# --- 5. Attendance Image Model Registration ---
@admin.register(AttendanceImage)
class AttendanceImageAdmin(admin.ModelAdmin):
    list_display = ('teacher', 'attendance_date', 'total_p_detected', 'total_a_detected', 'is_processed')
    list_filter = ('attendance_date', 'is_processed')
