from urllib.parse import quote
import mimetypes
import uuid

from django.core.files.storage import default_storage
from django.http import Http404
from django.utils.text import get_valid_filename


def presigned_download_url(file_field, expire=300, inline=False):
    storage = file_field.storage
    name = file_field.name

    if not storage.exists(name):
        raise Http404

    if not hasattr(storage, 'bucket_name'):
        return storage.url(name)

    filename = name.rsplit('/', 1)[-1]
    quoted_filename = quote(filename)
    disposition_type = 'inline' if inline else 'attachment'
    disposition = f"{disposition_type}; filename*=UTF-8''{quoted_filename}"

    parameters = {'ResponseContentDisposition': disposition}
    if not inline:
        parameters['ResponseContentType'] = 'application/octet-stream'

    return storage.url(name, parameters=parameters, expire=expire)


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


def build_presigned_uploads(files, prefix, max_files=7, expire=300, max_size=None):
    if not files or len(files) > max_files:
        raise ValueError('Некоректна кількість файлів')

    uploads = []
    for file_info in files:
        filename = file_info.get('name')
        size = file_info.get('size')

        if not filename or not isinstance(size, int) or size < 0:
            raise ValueError('Некоректні дані файлу')

        if max_size is not None and size > max_size:
            max_mb = max_size // (1024 * 1024)
            raise ValueError(f'Файл "{filename}" перевищує ліміт {max_mb} МБ')

        safe_name = get_valid_filename(filename)
        key = f'{prefix}/{uuid.uuid4()}_{safe_name}'
        content_type = mimetypes.guess_type(safe_name)[0] or 'application/octet-stream'
        uploads.append({
            'key': key,
            'content_type': content_type,
            'upload_url': presigned_upload_url(key, content_type, expire=expire),
        })

    return uploads


def validate_uploaded_keys(keys, prefix, max_files=7, max_size=None):
    if len(keys) > max_files:
        raise ValueError('too many files')

    for key in keys:
        if not key.startswith(f'{prefix}/') or not default_storage.exists(key):
            raise ValueError(f'invalid key: {key}')

        if max_size is not None and default_storage.size(key) > max_size:
            # The client can lie about size when requesting the upload URL,
            # but not about the actual bytes that landed in storage.
            default_storage.delete(key)
            raise ValueError(f'file too large: {key}')