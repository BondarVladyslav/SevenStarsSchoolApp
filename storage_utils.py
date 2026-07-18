from urllib.parse import quote
import mimetypes
import uuid

from django.core.files.storage import default_storage
from django.http import Http404
from django.utils.text import get_valid_filename


def presigned_download_url(file_field, expire=300):
    storage = file_field.storage
    name = file_field.name

    if not storage.exists(name):
        raise Http404

    if not hasattr(storage, 'bucket_name'):
        return storage.url(name)

    filename = name.rsplit('/', 1)[-1]
    quoted_filename = quote(filename)
    disposition = f"attachment; filename*=UTF-8''{quoted_filename}"

    return storage.url(
        name,
        parameters={
            'ResponseContentDisposition': disposition,
            'ResponseContentType': 'application/octet-stream',
        },
        expire=expire,
    )


def presigned_upload_url(key, content_type, expire=300):
    storage = default_storage

    if not hasattr(storage, 'bucket_name'):
        raise RuntimeError('presigned_upload_url requires S3-compatible storage')

    connection = storage.connection
    return connection.meta.client.generate_presigned_url(
        'put_object',
        Params={
            'Bucket': storage.bucket_name,
            'Key': key,
            'ContentType': content_type,
        },
        ExpiresIn=expire,
        HttpMethod='PUT',
    )


def build_presigned_uploads(filenames, prefix, max_files=7, expire=300):
    if not filenames or len(filenames) > max_files:
        raise ValueError('invalid filenames count')

    uploads = []
    for filename in filenames:
        safe_name = get_valid_filename(filename)
        key = f'{prefix}/{uuid.uuid4()}_{safe_name}'
        content_type = mimetypes.guess_type(safe_name)[0] or 'application/octet-stream'
        uploads.append({
            'key': key,
            'content_type': content_type,
            'upload_url': presigned_upload_url(key, content_type, expire=expire),
        })

    return uploads


def validate_uploaded_keys(keys, prefix, max_files=7):
    if len(keys) > max_files:
        raise ValueError('too many files')

    for key in keys:
        if not key.startswith(f'{prefix}/') or not default_storage.exists(key):
            raise ValueError(f'invalid key: {key}')