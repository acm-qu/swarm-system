"""Builds the Flask app from the hub's parts."""

from flask import Flask

from . import api, auth, robots, storage


def create_app():
    app = Flask(__name__)
    app.secret_key = storage.get_secret_key()
    app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax")

    app.register_blueprint(auth.bp)
    app.register_blueprint(api.bp)
    app.register_blueprint(robots.bp)
    robots.sock.init_app(app)

    @app.after_request
    def no_cache(resp):
        resp.headers["Cache-Control"] = "no-store"
        return resp

    return app
