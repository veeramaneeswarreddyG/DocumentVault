"""Flask extensions module.
Provides database (SQLAlchemy), migration (Flask-Migrate), and CSRF protection.
Includes a native SQLAlchemy 2.0 / CSRF adapter fallback when running in minimal test environments.
"""
import os
import hmac
import hashlib
import secrets
from flask import request, session, abort, g

try:
    from flask_sqlalchemy import SQLAlchemy as _FlaskSQLAlchemy
    from flask_migrate import Migrate
    from flask_wtf.csrf import CSRFProtect as _FlaskCSRFProtect
    USE_NATIVE_EXTENSIONS = True
except ModuleNotFoundError:
    USE_NATIVE_EXTENSIONS = False

if USE_NATIVE_EXTENSIONS:
    db = _FlaskSQLAlchemy()
    migrate = Migrate()
    csrf = _FlaskCSRFProtect()
else:
    # High-compatibility native adapter using installed SQLAlchemy 2.0 + standard library
    from sqlalchemy import create_engine, Column, String, BigInteger, DateTime
    from sqlalchemy.orm import declarative_base, scoped_session, sessionmaker
    from sqlalchemy.sql import func

    Base = declarative_base()

    class SQLAlchemy:
        def __init__(self, app=None):
            self.Model = Base
            self.Column = Column
            self.String = String
            self.BigInteger = BigInteger
            self.DateTime = DateTime
            self.engine = None
            self.session_factory = None
            self.session = None
            self._app = None
            if app:
                self.init_app(app)

        def init_app(self, app):
            self._app = app
            uri = app.config.get("SQLALCHEMY_DATABASE_URI", "sqlite:///:memory:")
            engine_options = app.config.get("SQLALCHEMY_ENGINE_OPTIONS", {})
            self.engine = create_engine(uri, **engine_options)
            self.session_factory = sessionmaker(bind=self.engine)
            self.session = scoped_session(self.session_factory)

            # Bind model query property
            self.Model.query = self.session.query_property()

            @app.teardown_appcontext
            def shutdown_session(exception=None):
                self.session.remove()

        def create_all(self):
            self.Model.metadata.create_all(bind=self.engine)

        def drop_all(self):
            self.Model.metadata.drop_all(bind=self.engine)

    class Migrate:
        def __init__(self, app=None, db=None):
            pass
        def init_app(self, app, db):
            pass

    class CSRFProtect:
        def __init__(self, app=None):
            self.exempt_views = set()
            self.exempt_blueprints = set()
            if app:
                self.init_app(app)

        def exempt(self, target):
            if hasattr(target, "name"):
                self.exempt_blueprints.add(target.name)
            else:
                self.exempt_views.add(target)
            return target

        def generate_csrf_token(self):
            if "_csrf_token" not in session:
                session["_csrf_token"] = secrets.token_hex(32)
            return session["_csrf_token"]

        def init_app(self, app):
            app.jinja_env.globals["csrf_token"] = self.generate_csrf_token

            @app.before_request
            def check_csrf():
                if not app.config.get("WTF_CSRF_ENABLED", True):
                    return
                if request.method not in ["POST", "PUT", "PATCH", "DELETE"]:
                    return
                if request.blueprint in self.exempt_blueprints:
                    return
                if request.endpoint in self.exempt_views:
                    return

                token = (
                    request.headers.get("X-CSRFToken")
                    or request.headers.get("X-CSRF-Token")
                    or request.form.get("csrf_token")
                )
                expected_token = session.get("_csrf_token")
                if not token or not expected_token or not hmac.compare_digest(token, expected_token):
                    abort(400, description="CSRF validation failed: token missing or invalid.")

    db = SQLAlchemy()
    migrate = Migrate()
    csrf = CSRFProtect()
