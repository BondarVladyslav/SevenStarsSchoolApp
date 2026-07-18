from users.models import Parent, Student, Teacher
 
 
def user_role(request):
    is_parent_user = False
    is_student_user = False
    is_teacher_user = False
 
    if request.user.is_authenticated:
        is_parent_user = Parent.objects.filter(user=request.user).exists()
        is_student_user = Student.objects.filter(user=request.user).exists()
        is_teacher_user = Teacher.objects.filter(user=request.user).exists()
 
    return {
        'is_parent_user': is_parent_user,
        'is_student_user': is_student_user,
        'is_teacher_user': is_teacher_user,
    }