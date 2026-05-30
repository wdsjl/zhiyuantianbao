import json
import mimetypes
import uuid
import urllib.request
from pathlib import Path

file_path = Path(__file__).resolve().parent / 'admission_import_template.csv'
boundary = f'----WebKitFormBoundary{uuid.uuid4().hex}'
content_type = mimetypes.guess_type(file_path.name)[0] or 'application/octet-stream'
file_content = file_path.read_bytes()

body = b''
body += f'--{boundary}\r\n'.encode()
body += f'Content-Disposition: form-data; name="file"; filename="{file_path.name}"\r\n'.encode()
body += f'Content-Type: {content_type}\r\n\r\n'.encode()
body += file_content
body += f'\r\n--{boundary}--\r\n'.encode()

request = urllib.request.Request(
    'http://127.0.0.1:8000/api/import/admissions',
    data=body,
    headers={'Content-Type': f'multipart/form-data; boundary={boundary}'}
)

with urllib.request.urlopen(request, timeout=10) as response:
    print(json.dumps(json.loads(response.read().decode('utf-8')), ensure_ascii=False, indent=2))
