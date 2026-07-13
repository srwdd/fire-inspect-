'''CORS configuration — restrict to known origins in production.'''
import os

_raw = os.environ.get('CORS_ORIGINS', 'https://ai-bang.top,http://localhost:3008,http://localhost:5173')
ALLOWED_ORIGINS = [o.strip() for o in _raw.split(',') if o.strip()]

cors_config = {
    'allow_origins': ALLOWED_ORIGINS,
    'allow_credentials': False,
    'allow_methods': ['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'],
    'allow_headers': ['Authorization', 'Content-Type', 'X-Admin-Token'],
}
