import os
import shutil
import tempfile
import zipfile
from datetime import datetime
from io import StringIO

from django.conf import settings
from django.core.management import call_command
from django.db import connection, transaction
from django.http import HttpResponse, JsonResponse, FileResponse
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin

# Name of the data file inside the backup zip
DATA_FILENAME = 'data.json'

# System tables that are recreated by migrations and must NOT be dumped/loaded.
# Excluding them keeps the backup portable between database engines
# (SQLite <-> PostgreSQL) and avoids primary-key collisions on restore.
DUMP_EXCLUDES = [
    'contenttypes',
    'auth.permission',
    'admin.logentry',
    'sessions.session',
]

# Apps whose auto-increment sequences need resetting after a PostgreSQL restore
SEQUENCE_APPS = ['auth', 'authtoken', 'vouchers']


class BackupDownloadView(LoginRequiredMixin, View):
    """
    Downloads a full backup as a .zip containing:
      - data.json  (all database data, engine-agnostic via Django dumpdata)
      - media/...  (all uploaded files)

    Works identically on SQLite and PostgreSQL because the data is exported
    as JSON rather than copying a raw database file.
    """

    def get(self, request):
        if not request.user.is_superuser:
            return HttpResponse('Forbidden', status=403)

        media_root = str(settings.MEDIA_ROOT)
        timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M')
        download_name = f'backup_{timestamp}.zip'

        tmp_dir = tempfile.mkdtemp()
        json_path = os.path.join(tmp_dir, DATA_FILENAME)
        zip_fd, zip_path = tempfile.mkstemp(suffix='.zip')
        os.close(zip_fd)

        try:
            # 1) Export all data to an engine-agnostic JSON file.
            #    output= streams directly to the file (no large in-memory buffer).
            call_command(
                'dumpdata',
                exclude=DUMP_EXCLUDES,
                indent=2,
                output=json_path,
            )

            # 2) Bundle the JSON + media folder into a single zip on disk.
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                zf.write(json_path, DATA_FILENAME)
                if os.path.isdir(media_root):
                    for dirpath, _, filenames in os.walk(media_root):
                        for fname in filenames:
                            abs_path = os.path.join(dirpath, fname)
                            rel_path = os.path.relpath(abs_path, str(settings.BASE_DIR))
                            try:
                                zf.write(abs_path, rel_path)
                            except Exception:
                                pass  # skip unreadable files
        except Exception as e:
            shutil.rmtree(tmp_dir, ignore_errors=True)
            try:
                os.unlink(zip_path)
            except OSError:
                pass
            return HttpResponse(f'Backup failed: {e}', status=500)
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

        # 3) Stream the zip in chunks (FileResponse) so nginx doesn't time out,
        #    and delete the temp file once streaming completes.
        f = open(zip_path, 'rb')
        _original_close = f.close

        def _close_and_delete():
            _original_close()
            try:
                os.unlink(zip_path)
            except OSError:
                pass

        f.close = _close_and_delete

        response = FileResponse(f, content_type='application/zip')
        response['Content-Disposition'] = f'attachment; filename="{download_name}"'
        return response


class BackupRestoreView(LoginRequiredMixin, View):
    """
    Restores a backup produced by BackupDownloadView. Imports the JSON data
    (merging by primary key) and replaces the media folder. The current media
    folder is copied aside first as a safety backup.
    """

    def post(self, request):
        if not request.user.is_superuser:
            return JsonResponse({'success': False, 'error': 'Forbidden'}, status=403)

        uploaded = request.FILES.get('backup_file')
        if not uploaded:
            return JsonResponse({'success': False, 'error': 'No file uploaded.'})
        if not uploaded.name.endswith('.zip'):
            return JsonResponse({'success': False, 'error': 'Please upload a .zip backup file.'})

        tmp_dir = tempfile.mkdtemp()
        try:
            # Save upload to disk and extract
            zip_path = os.path.join(tmp_dir, 'upload.zip')
            with open(zip_path, 'wb') as dst:
                for chunk in uploaded.chunks():
                    dst.write(chunk)

            try:
                with zipfile.ZipFile(zip_path) as zf:
                    if DATA_FILENAME not in zf.namelist():
                        return JsonResponse({
                            'success': False,
                            'error': 'Invalid backup: data.json not found in zip. '
                                     '(Old SQLite-file backups are not supported — '
                                     'please download a fresh backup.)'
                        })
                    zf.extractall(tmp_dir)
            except zipfile.BadZipFile:
                return JsonResponse({'success': False, 'error': 'The uploaded file is not a valid zip archive.'})

            json_path = os.path.join(tmp_dir, DATA_FILENAME)

            # 1) Import data (loaddata upserts by primary key). Wrapped in a
            #    transaction so a failure rolls back cleanly.
            with transaction.atomic():
                call_command('loaddata', json_path)

            # 2) On PostgreSQL, loading explicit PKs leaves sequences behind;
            #    reset them so future inserts don't collide. (No-op on SQLite.)
            if connection.vendor == 'postgresql':
                out = StringIO()
                try:
                    call_command('sqlsequencereset', *SEQUENCE_APPS, stdout=out, no_color=True)
                    sql = out.getvalue()
                    if sql.strip():
                        with connection.cursor() as cursor:
                            cursor.execute(sql)
                except Exception:
                    pass

            # 3) Restore media files (back up current media first)
            media_root = str(settings.MEDIA_ROOT)
            media_src = os.path.join(tmp_dir, 'media')
            if os.path.isdir(media_src):
                ts = datetime.now().strftime('%Y%m%d_%H%M%S')
                if os.path.isdir(media_root):
                    shutil.copytree(media_root, media_root.rstrip('/\\') + f'_bak_{ts}')
                for dirpath, _, filenames in os.walk(media_src):
                    for fname in filenames:
                        abs_src = os.path.join(dirpath, fname)
                        rel = os.path.relpath(abs_src, media_src)
                        dest = os.path.join(media_root, rel)
                        os.makedirs(os.path.dirname(dest), exist_ok=True)
                        shutil.copy2(abs_src, dest)

            return JsonResponse({
                'success': True,
                'message': 'Backup restored successfully. Data and media have been imported. '
                           'You may need to refresh the page.'
            })

        except Exception as e:
            return JsonResponse({'success': False, 'error': f'Restore failed: {e}'})
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)
