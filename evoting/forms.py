from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import (StringField, PasswordField, SubmitField, TextAreaField,
                     DateTimeLocalField, SelectField, BooleanField)
from wtforms.validators import DataRequired, Email, EqualTo, Length, Optional, ValidationError

_email = lambda: Email(check_deliverability=False)
from models import User


class RegisterForm(FlaskForm):
    name = StringField('Full Name', validators=[DataRequired(), Length(2, 120)])
    email = StringField('Email', validators=[DataRequired(), _email()])
    roll_number = StringField('Roll Number / Voter ID', validators=[Optional(), Length(max=50)])
    password = PasswordField('Password', validators=[DataRequired(), Length(8)])
    confirm = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Register')

    def validate_email(self, field):
        if User.query.filter_by(email=field.data.lower()).first():
            raise ValidationError('Email already registered.')

    def validate_roll_number(self, field):
        if field.data:
            existing = User.query.filter_by(roll_number=field.data.upper()).first()
            if existing:
                raise ValidationError('Roll number already registered.')


class LoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), _email()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Login')


class TOTPVerifyForm(FlaskForm):
    token = StringField('Authenticator Code', validators=[DataRequired(), Length(6, 6)])
    submit = SubmitField('Verify')


class TOTPSetupForm(FlaskForm):
    token = StringField('Enter code to confirm', validators=[DataRequired(), Length(6, 6)])
    submit = SubmitField('Enable 2FA')


class PasswordResetRequestForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), _email()])
    submit = SubmitField('Send Reset Link')


class PasswordResetForm(FlaskForm):
    password = PasswordField('New Password', validators=[DataRequired(), Length(8)])
    confirm = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Reset Password')


class ElectionForm(FlaskForm):
    title = StringField('Title', validators=[DataRequired(), Length(3, 200)])
    description = TextAreaField('Description')
    start_time = DateTimeLocalField('Start Time', format='%Y-%m-%dT%H:%M', validators=[DataRequired()])
    end_time = DateTimeLocalField('End Time', format='%Y-%m-%dT%H:%M', validators=[DataRequired()])
    eligible_prefix = StringField('Eligible Roll Prefix (blank = all)',
                                  validators=[Optional(), Length(max=50)])
    submit = SubmitField('Save Election')

    def validate_end_time(self, field):
        if self.start_time.data and field.data <= self.start_time.data:
            raise ValidationError('End time must be after start time.')


class CandidateForm(FlaskForm):
    name = StringField('Candidate Name', validators=[DataRequired(), Length(2, 120)])
    description = TextAreaField('About Candidate')
    photo = FileField('Photo', validators=[
        Optional(),
        FileAllowed(['png', 'jpg', 'jpeg', 'gif', 'webp'], 'Images only.')
    ])
    submit = SubmitField('Save Candidate')


class VoteForm(FlaskForm):
    candidate_id = SelectField('Select Candidate', coerce=int, validators=[DataRequired()])
    snapshot = StringField('snapshot', validators=[Optional()])  # base64 from webcam JS
    submit = SubmitField('Cast Vote')


class OTPVerifyForm(FlaskForm):
    otp = StringField('Verification Code', validators=[DataRequired(), Length(6, 6)])
    submit = SubmitField('Verify Email')


class ReceiptLookupForm(FlaskForm):
    token = StringField('Receipt Token', validators=[DataRequired()])
    submit = SubmitField('Verify Receipt')
