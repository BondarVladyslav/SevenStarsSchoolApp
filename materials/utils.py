from django.db.models import Q
 
from courses.models import Group
from .models import Material
 
 
def get_materials_by_group(group_ids):
    groups = Group.objects.filter(id__in=group_ids).select_related('subject', 'level')
 
    sections_by_key = {}
    for group in groups:
        key = (group.subject_id, group.level_id)
        if key not in sections_by_key:
            sections_by_key[key] = {
                'subject': group.subject,
                'level': group.level,
                'groups': [],
            }
        sections_by_key[key]['groups'].append(group)
 
    sections = []
    for (subject_id, level_id), data in sections_by_key.items():
        if level_id:
            query = Q(subject_id=subject_id) & (Q(level_id=level_id) | Q(level__isnull=True))
        else:
            query = Q(subject_id=subject_id) & Q(level__isnull=True)
 
        materials = (
            Material.objects.filter(query)
            .select_related('subject', 'level')
            .prefetch_related('files')
            .distinct()
        )
 
        sections.append({
            'subject': data['subject'],
            'level': data['level'],
            'groups': data['groups'],
            'materials': materials,
        })
 
    return sections
 
 
def get_all_materials_grouped():
    materials = (
        Material.objects.select_related('subject', 'level')
        .prefetch_related('files')
        .order_by('subject__name', 'level__order')
    )
 
    sections_by_key = {}
    for material in materials:
        key = (material.subject_id, material.level_id)
        if key not in sections_by_key:
            sections_by_key[key] = {
                'subject': material.subject,
                'level': material.level,
                'materials': [],
            }
        sections_by_key[key]['materials'].append(material)
 
    return list(sections_by_key.values())


from courses.models import Group
from users.models import Student, Teacher


def user_has_access_to_material(user, material):
    if user.is_superuser:
        return True

    student = Student.objects.filter(user=user).first()
    if student:
        group_ids = student.groups.values_list('id', flat=True)
    else:
        teacher = Teacher.objects.filter(user=user).first()
        if not teacher:
            return False
        group_ids = teacher.groups.values_list('id', flat=True)

    groups = Group.objects.filter(id__in=group_ids).select_related(None)

    for group in groups:
        if group.subject_id != material.subject_id:
            continue
        if material.level_id is None or material.level_id == group.level_id:
            return True

    return False