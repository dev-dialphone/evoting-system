import os
from datetime import timezone, timedelta
from flask import Flask, render_template
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from config import Config
from models import db, User
from mail_utils import mail

_IST = timezone(timedelta(hours=5, minutes=30))

csrf = CSRFProtect()


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

    db.init_app(app)
    mail.init_app(app)
    csrf.init_app(app)

    login_manager = LoginManager(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message_category = 'warning'

    # Permanent sessions for idle timeout
    app.config['PERMANENT_SESSION_LIFETIME'] = Config.PERMANENT_SESSION_LIFETIME

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    from auth import auth
    from main import main
    from admin import admin_bp

    app.register_blueprint(auth)
    app.register_blueprint(main)
    app.register_blueprint(admin_bp)

    @app.template_filter('ist')
    def to_ist(dt):
        """For UTC-stored datetimes (cast_at, created_at): convert to IST."""
        if dt is None:
            return ''
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(_IST).strftime('%d %b %Y %I:%M %p IST')

    @app.template_filter('localdt')
    def to_localdt(dt):
        """For naive local-time datetimes (election start/end entered by admin): display as-is."""
        if dt is None:
            return ''
        return dt.strftime('%d %b %Y %I:%M %p')

    @app.errorhandler(403)
    def forbidden(e):
        return render_template('403.html'), 403

    @app.errorhandler(404)
    def not_found(e):
        return render_template('404.html'), 404

    with app.app_context():
        db.create_all()
        _seed_admin()

    return app


def _seed_admin():
    # Update existing old admin email if present
    old = User.query.filter_by(email='admin@evoting.local').first()
    if old:
        old.email = 'admin@gmail.com'
        db.session.commit()
    if not User.query.filter_by(email='admin@gmail.com').first():
        admin = User(name='Administrator', email='admin@gmail.com',
                     role='admin', email_verified=True)
        admin.set_password('Admin@1234')
        db.session.add(admin)
        db.session.commit()


if __name__ == '__main__':
    app = create_app()
    app.run(debug=True, host='0.0.0.0')
