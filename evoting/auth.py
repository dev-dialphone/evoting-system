import io
import base64
import pyotp
import qrcode
from datetime import datetime, timezone
from flask import (Blueprint, render_template, redirect, url_for, flash,
                   request, session, make_response)
from flask_login import login_user, logout_user, login_required, current_user
from models import db, User, AuditLog
from forms import (RegisterForm, LoginForm, TOTPVerifyForm, TOTPSetupForm,
                   PasswordResetRequestForm, PasswordResetForm, OTPVerifyForm)

auth = Blueprint('auth', __name__)


def _log(action, detail=None, uid=None):
    entry = AuditLog(
        user_id=uid or (current_user.id if current_user.is_authenticated else None),
        action=action,
        detail=detail,
        ip_address=request.remote_addr,
    )
    db.session.add(entry)
    db.session.commit()


# ── Register ──────────────────────────────────────────────────────────────────

@auth.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    form = RegisterForm()
    if form.validate_on_submit():
        rn = form.roll_number.data.upper() if form.roll_number.data else None
        user = User(name=form.name.data, email=form.email.data.lower(),
                    roll_number=rn, email_verified=False)
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.flush()   # get user.id before commit
        otp = user.generate_otp()
        db.session.commit()
        _log('register', f'New voter (pending verify): {user.email}', uid=user.id)
        session['verify_user_id'] = user.id
        session['demo_otp'] = otp
        flash('Account created! Enter the verification code shown below.', 'info')
        return redirect(url_for('auth.verify_email'))
    return render_template('register.html', form=form)


@auth.route('/verify-email', methods=['GET', 'POST'])
def verify_email():
    uid = session.get('verify_user_id')
    if not uid:
        return redirect(url_for('auth.register'))
    user = User.query.get_or_404(uid)
    if user.email_verified:
        session.pop('verify_user_id', None)
        session.pop('demo_otp', None)
        flash('Already verified. Please log in.', 'info')
        return redirect(url_for('auth.login'))

    form = OTPVerifyForm()
    if form.validate_on_submit():
        if user.verify_otp(form.otp.data):
            user.email_verified = True
            user.otp_code = None
            user.otp_expiry = None
            db.session.commit()
            session.pop('verify_user_id', None)
            session.pop('demo_otp', None)
            _log('email_verified', uid=user.id)
            flash('Account verified! You can now log in.', 'success')
            return redirect(url_for('auth.login'))
        flash('Invalid or expired code.', 'danger')

    demo_otp = session.get('demo_otp')
    return render_template('verify_email.html', form=form, email=user.email, demo_otp=demo_otp)


@auth.route('/verify-email/resend', methods=['POST'])
def resend_otp():
    uid = session.get('verify_user_id')
    if not uid:
        return redirect(url_for('auth.register'))
    user = User.query.get_or_404(uid)
    if user.email_verified:
        return redirect(url_for('auth.login'))
    otp = user.generate_otp()
    db.session.commit()
    session['demo_otp'] = otp
    flash('A new verification code has been generated.', 'info')
    return redirect(url_for('auth.verify_email'))


# ── Login (with optional 2FA) ─────────────────────────────────────────────────

@auth.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data.lower()).first()
        if user and user.check_password(form.password.data) and user.is_active:
            if not user.email_verified:
                otp = user.generate_otp()
                db.session.commit()
                session['verify_user_id'] = user.id
                session['demo_otp'] = otp
                flash('Please verify your account first.', 'warning')
                return redirect(url_for('auth.verify_email'))
            if user.totp_enabled:
                session['pending_user_id'] = user.id
                return redirect(url_for('auth.totp_verify'))
            login_user(user)
            _log('login', uid=user.id)
            return redirect(request.args.get('next') or url_for('main.dashboard'))
        flash('Invalid credentials.', 'danger')
    return render_template('login.html', form=form)


@auth.route('/login/2fa', methods=['GET', 'POST'])
def totp_verify():
    uid = session.get('pending_user_id')
    if not uid:
        return redirect(url_for('auth.login'))
    user = User.query.get_or_404(uid)
    form = TOTPVerifyForm()
    if form.validate_on_submit():
        totp = pyotp.TOTP(user.totp_secret)
        if totp.verify(form.token.data, valid_window=1):
            session.pop('pending_user_id', None)
            login_user(user)
            _log('login_2fa', uid=user.id)
            return redirect(url_for('main.dashboard'))
        flash('Invalid authenticator code.', 'danger')
    return render_template('totp_verify.html', form=form)


# ── Logout ────────────────────────────────────────────────────────────────────

@auth.route('/logout')
@login_required
def logout():
    _log('logout')
    logout_user()
    flash('Logged out.', 'info')
    return redirect(url_for('auth.login'))


# ── 2FA Setup (admin or any user) ─────────────────────────────────────────────

@auth.route('/settings/2fa', methods=['GET', 'POST'])
@login_required
def totp_setup():
    if current_user.totp_enabled:
        flash('2FA already enabled. Disable first to reconfigure.', 'info')
        return redirect(url_for('main.dashboard'))

    secret = session.get('totp_setup_secret') or pyotp.random_base32()
    session['totp_setup_secret'] = secret

    totp = pyotp.TOTP(secret)
    uri = totp.provisioning_uri(name=current_user.email, issuer_name='E-Voting')
    img = qrcode.make(uri)
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    qr_b64 = base64.b64encode(buf.getvalue()).decode()

    form = TOTPSetupForm()
    if form.validate_on_submit():
        if totp.verify(form.token.data, valid_window=1):
            current_user.totp_secret = secret
            current_user.totp_enabled = True
            db.session.commit()
            session.pop('totp_setup_secret', None)
            _log('2fa_enabled')
            flash('Two-factor authentication enabled.', 'success')
            return redirect(url_for('main.dashboard'))
        flash('Invalid code. Try again.', 'danger')

    return render_template('totp_setup.html', form=form, qr_b64=qr_b64, secret=secret)


@auth.route('/settings/2fa/disable', methods=['POST'])
@login_required
def totp_disable():
    current_user.totp_secret = None
    current_user.totp_enabled = False
    db.session.commit()
    _log('2fa_disabled')
    flash('Two-factor authentication disabled.', 'info')
    return redirect(url_for('main.dashboard'))


# ── Password Reset ─────────────────────────────────────────────────────────────

@auth.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    form = PasswordResetRequestForm()
    reset_token = session.get('reset_token_display')
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data.lower()).first()
        if user:
            token = user.generate_reset_token()
            db.session.commit()
            session['reset_token_display'] = token
            reset_token = token
        else:
            flash('If that email is registered, a reset code will appear here.', 'info')
    return render_template('forgot_password.html', form=form, reset_token=reset_token)


@auth.route('/forgot-password/use-token', methods=['POST'])
def use_reset_token():
    token = request.form.get('token', '').strip()
    session.pop('reset_token_display', None)
    return redirect(url_for('auth.password_reset', token=token))


@auth.route('/reset-password/<token>', methods=['GET', 'POST'])
def password_reset(token):
    user = User.query.filter_by(reset_token=token).first()
    now = datetime.now(timezone.utc)
    if not user:
        flash('Reset link is invalid or expired.', 'danger')
        return redirect(url_for('auth.forgot_password'))
    expiry = user.reset_token_expiry
    if expiry and expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=timezone.utc)
    if not expiry or now > expiry:
        flash('Reset link is invalid or expired.', 'danger')
        return redirect(url_for('auth.forgot_password'))
    form = PasswordResetForm()
    if form.validate_on_submit():
        user.set_password(form.password.data)
        user.reset_token = None
        user.reset_token_expiry = None
        db.session.commit()
        _log('password_reset', uid=user.id)
        flash('Password updated. Please log in.', 'success')
        return redirect(url_for('auth.login'))
    return render_template('reset_password.html', form=form)


# ── Vote Receipt Verify ────────────────────────────────────────────────────────

@auth.route('/receipt', methods=['GET', 'POST'])
@login_required
def receipt_verify():
    from forms import ReceiptLookupForm
    from models import Vote
    form = ReceiptLookupForm()
    vote = None
    if form.validate_on_submit():
        vote = Vote.query.filter_by(receipt_token=form.token.data.strip()).first()
        if not vote:
            flash('No vote found for that receipt token.', 'warning')
    return render_template('receipt_verify.html', form=form, vote=vote)
