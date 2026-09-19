from flask import url_for, current_app
from flask_mail import Mail, Message

mail = Mail()


def send_otp_email(user):
    otp = user.generate_otp()
    msg = Message('Verify your E-Voting account', recipients=[user.email])
    msg.body = (
        f'Hi {user.name},\n\n'
        f'Your email verification code is: {otp}\n\n'
        f'It expires in 15 minutes. Do not share it.\n'
    )
    try:
        mail.send(msg)
    except Exception as e:
        current_app.logger.warning(f'OTP mail failed: {e}')


def send_reset_email(user):
    token = user.generate_reset_token()
    link = url_for('auth.password_reset', token=token, _external=True)
    msg = Message('Password Reset — E-Voting System',
                  recipients=[user.email])
    msg.body = f'Reset your password: {link}\n\nLink expires in 1 hour.'
    try:
        mail.send(msg)
    except Exception as e:
        current_app.logger.warning(f'Mail send failed: {e}')


def send_election_notification(election, subject, body_tpl):
    from models import User
    voters = User.query.filter_by(is_active=True).all()
    count = 0
    for voter in voters:
        if voter.role == 'voter':
            count += 1
            current_app.logger.info(f'[NOTIFY] {voter.email}: {subject}')
    return count
