from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import render, get_object_or_404, redirect

from courses.templatetags.file_extras import is_image
from SevenStarsSchool.storage_utils import presigned_download_url
from .models import Material, MaterialFile
from users.models import Student, Teacher
from .utils import get_all_materials_grouped, get_materials_by_group, user_has_access_to_material

@login_required
def materials_view(request):
    user = request.user
 
    if user.is_superuser:
        context = {
            'sections': get_all_materials_grouped(),
        }
        return render(request, 'materials/materials_list.html', context)
 
    student = Student.objects.filter(user=user).first()
    if student:
        group_ids = student.groups.values_list('id', flat=True)
        context = {
            'sections': get_materials_by_group(group_ids),
        }
        return render(request, 'materials/materials_list.html', context)
 
    teacher = Teacher.objects.filter(user=user).first()
    if teacher:
        group_ids = teacher.groups.values_list('id', flat=True)
        context = {
            'sections': get_materials_by_group(group_ids),
        }
        return render(request, 'materials/materials_list.html', context)
 
    raise PermissionDenied

@login_required
def material_detail_view(request, material_id):
    material = get_object_or_404(Material, id=material_id)

    if not user_has_access_to_material(request.user, material):
        raise PermissionDenied

    context = {
        'material': material,
        'files': material.files.all(),
    }
    return render(request, 'materials/materials_detail.html', context)


@login_required
def download_material_file(request, file_id):
    material_file = get_object_or_404(MaterialFile, id=file_id)

    if not user_has_access_to_material(request.user, material_file.material):
        raise PermissionDenied

    url = presigned_download_url(material_file.file, inline=is_image(material_file.file.name))
    return redirect(url)