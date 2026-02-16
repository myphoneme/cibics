import os

import uvicorn

DEFAULT_HOST = os.getenv('API_HOST', '0.0.0.0')
DEFAULT_PORT = int(os.getenv('API_PORT', '8200'))
RELOAD = os.getenv('API_RELOAD', 'true').lower() not in {'0', 'false', 'no'}

if __name__ == '__main__':
    uvicorn.run('app.main:app', host=DEFAULT_HOST, port=DEFAULT_PORT, reload=RELOAD)
