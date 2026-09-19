import secrets
from datetime import datetime, timezone
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()


class User(UserMixin, db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    roll_number = db.Column(db.String(50), unique=True, nullable=True)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), default='voter')  # 'voter' | 'admin'
    is_active = db.Column(db.Boolean, default=True)
    # TOTP
    totp_secret = db.Column(db.String(64), nullable=True)
    totp_enabled = db.Column(db.Boolean, default=False)
    # Email OTP verification
    email_verified = db.Column(db.Boolean, default=False)
    otp_code = db.Column(db.String(6), nullable=True)
    otp_expiry = db.Column(db.DateTime, nullable=True)
    # Password reset
    reset_token = db.Column(db.String(100), nullable=True)
    reset_token_expiry = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    votes = db.relationship('Vote', backref='voter', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def is_admin(self):
        return self.role == 'admin'

    def generate_otp(self):
        import random
        from datetime import timedelta
        self.otp_code = f'{random.randint(0, 999999):06d}'
        self.otp_expiry = datetime.now(timezone.utc) + timedelta(minutes=15)
        return self.otp_code

    def verify_otp(self, code):
        if not self.otp_code or not self.otp_expiry:
            return False
        expiry = self.otp_expiry
        if expiry.tzinfo is None:
            expiry = expiry.replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) > expiry:
            return False
        return self.otp_code == code.strip()

    def generate_reset_token(self):
        self.reset_token = secrets.token_urlsafe(32)
        from datetime import timedelta
        self.reset_token_expiry = datetime.now(timezone.utc) + timedelta(hours=1)
        return self.reset_token


class Election(db.Model):
    __tablename__ = 'elections'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    start_time = db.Column(db.DateTime, nullable=False)
    end_time = db.Column(db.DateTime, nullable=False)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    # Eligibility: restrict by roll number prefix (e.g. "24TCS") or leave blank for all
    eligible_prefix = db.Column(db.String(50), nullable=True)

    candidates = db.relationship('Candidate', backref='election', lazy=True, cascade='all, delete-orphan')
    votes = db.relationship('Vote', backref='election', lazy=True, cascade='all, delete-orphan')

    def is_eligible(self, user):
        if not self.eligible_prefix:
            return True
        if not user.roll_number:
            return False
        return user.roll_number.upper().startswith(self.eligible_prefix.upper())

    @property
    def is_open(self):
        now = datetime.now()  # naive local time, matches stored election times
        start = self.start_time if self.start_time.tzinfo is None else self.start_time.replace(tzinfo=None)
        end = self.end_time if self.end_time.tzinfo is None else self.end_time.replace(tzinfo=None)
        return start <= now <= end

    @property
    def status(self):
        now = datetime.now()  # naive local time, matches stored election times
        start = self.start_time if self.start_time.tzinfo is None else self.start_time.replace(tzinfo=None)
        end = self.end_time if self.end_time.tzinfo is None else self.end_time.replace(tzinfo=None)
        if now < start:
            return 'upcoming'
        if now > end:
            return 'closed'
        return 'open'


class Candidate(db.Model):
    __tablename__ = 'candidates'

    id = db.Column(db.Integer, primary_key=True)
    election_id = db.Column(db.Integer, db.ForeignKey('elections.id'), nullable=False)
    name = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text)
    photo = db.Column(db.String(200), nullable=True)  # filename in static/uploads

    votes = db.relationship('Vote', backref='candidate', lazy=True)

    @property
    def vote_count(self):
        return len(self.votes)


class Vote(db.Model):
    __tablename__ = 'votes'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    election_id = db.Column(db.Integer, db.ForeignKey('elections.id'), nullable=False)
    candidate_id = db.Column(db.Integer, db.ForeignKey('candidates.id'), nullable=False)
    cast_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    # Webcam snapshot filename
    snapshot = db.Column(db.String(200), nullable=True)
    # Anonymous receipt token
    receipt_token = db.Column(db.String(64), unique=True, nullable=False,
                              default=lambda: secrets.token_urlsafe(32))

    __table_args__ = (
        db.UniqueConstraint('user_id', 'election_id', name='one_vote_per_election'),
    )


class AuditLog(db.Model):
    __tablename__ = 'audit_log'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    action = db.Column(db.String(100), nullable=False)
    detail = db.Column(db.Text)
    ip_address = db.Column(db.String(45))
    timestamp = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
