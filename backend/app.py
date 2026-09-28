"""WSGI entry point. Development: python app.py; production: waitress-serve app:app."""

from datahub.web import create_app

app = create_app()
if __name__ == "__main__":
    import os
    from waitress import serve
    
    serve(app, host=os.getenv("CONCN_HOST", "127.0.0.1"), port=int(os.getenv("CONCN_PORT", "8000")), threads=8)
