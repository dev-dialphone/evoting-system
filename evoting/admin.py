import io
import os
import secrets
from functools import wraps
from flask import (Blueprint, render_template, redirect, url_for, flash, abort,
                   request, current_app, send_file)
from flask_login import login_required, current_user
from models import db, User, Election, Candidate, Vote, AuditLog
from forms import ElectionForm, CandidateForm
from mail_utils import send_election_notification

admin_bp = Blueprint('admin_bp', __name__, url_prefix='/admin')

ALLOWED_EXT = {'png', 'jpg', 'jpeg', 'gif', 'webp'}


def _allowed(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXT


def admin_required(f):
    @wraps(f)
    @login_required
    def decorated(*args, **kwargs):
        if not current_user.is_admin:
            abort(403)
        return f(*args, **kwargs)
    return decorated


# ── Dashboard ─────────────────────────────────────────────────────────────────

@admin_bp.route('/')
@admin_required
def dashboard():
    stats = {
        'users': User.query.count(),
        'elections': Election.query.count(),
        'votes': Vote.query.count(),
    }
    elections = Election.query.order_by(Election.start_time.desc()).all()
    return render_template('admin/dashboard.html', stats=stats, elections=elections)


# ── Elections ─────────────────────────────────────────────────────────────────

@admin_bp.route('/elections/new', methods=['GET', 'POST'])
@admin_required
def election_new():
    form = ElectionForm()
    if form.validate_on_submit():
        election = Election(
            title=form.title.data,
            description=form.description.data,
            start_time=form.start_time.data,
            end_time=form.end_time.data,
            eligible_prefix=form.eligible_prefix.data.upper() if form.eligible_prefix.data else None,
            created_by=current_user.id,
        )
        db.session.add(election)
        db.session.commit()
        count = send_election_notification(
            election,
            f'New Election: {election.title}',
            'Hi {name},\n\nA new election "{title}" has been created. Log in to vote.\n'
        )
        flash(f'Election created. Notification recorded for {count} voter(s).', 'success')
        return redirect(url_for('admin_bp.election_edit', election_id=election.id))
    return render_template('admin/election_form.html', form=form, title='New Election')


@admin_bp.route('/elections/<int:election_id>/edit', methods=['GET', 'POST'])
@admin_required
def election_edit(election_id):
    election = Election.query.get_or_404(election_id)
    form = ElectionForm(obj=election)
    if form.validate_on_submit():
        election.title = form.title.data
        election.description = form.description.data
        election.start_time = form.start_time.data
        election.end_time = form.end_time.data
        election.eligible_prefix = form.eligible_prefix.data.upper() if form.eligible_prefix.data else None
        db.session.commit()
        flash('Election updated.', 'success')
    return render_template('admin/election_form.html', form=form, election=election, title='Edit Election')


@admin_bp.route('/elections/<int:election_id>/delete', methods=['POST'])
@admin_required
def election_delete(election_id):
    election = Election.query.get_or_404(election_id)
    db.session.delete(election)
    db.session.commit()
    flash('Election deleted.', 'info')
    return redirect(url_for('admin_bp.dashboard'))


@admin_bp.route('/elections/<int:election_id>/notify', methods=['POST'])
@admin_required
def election_notify(election_id):
    election = Election.query.get_or_404(election_id)
    count = send_election_notification(
        election,
        f'Election Reminder: {election.title}',
        'Hi {name},\n\nReminder: election "{title}" is open. Log in to cast your vote.\n'
    )
    flash(f'Notification recorded for {count} voter(s) — "{election.title}". '
          f'(Email delivery is disabled; voters will see this election when they log in.)', 'success')
    return redirect(url_for('admin_bp.election_edit', election_id=election_id))


# ── Candidates ────────────────────────────────────────────────────────────────

@admin_bp.route('/elections/<int:election_id>/candidates/add', methods=['GET', 'POST'])
@admin_required
def candidate_add(election_id):
    election = Election.query.get_or_404(election_id)
    form = CandidateForm()
    if form.validate_on_submit():
        photo_fname = None
        if form.photo.data and form.photo.data.filename:
            f = form.photo.data
            if _allowed(f.filename):
                ext = f.filename.rsplit('.', 1)[1].lower()
                photo_fname = f'cand_{secrets.token_hex(8)}.{ext}'
                f.save(os.path.join(current_app.config['UPLOAD_FOLDER'], photo_fname))

        candidate = Candidate(
            election_id=election_id,
            name=form.name.data,
            description=form.description.data,
            photo=photo_fname,
        )
        db.session.add(candidate)
        db.session.commit()
        flash('Candidate added.', 'success')
        return redirect(url_for('admin_bp.election_edit', election_id=election_id))
    return render_template('admin/candidate_form.html', form=form, election=election)


@admin_bp.route('/candidates/<int:candidate_id>/delete', methods=['POST'])
@admin_required
def candidate_delete(candidate_id):
    candidate = Candidate.query.get_or_404(candidate_id)
    election_id = candidate.election_id
    db.session.delete(candidate)
    db.session.commit()
    flash('Candidate removed.', 'info')
    return redirect(url_for('admin_bp.election_edit', election_id=election_id))


# ── Users ─────────────────────────────────────────────────────────────────────

@admin_bp.route('/users')
@admin_required
def users():
    q = request.args.get('q', '').strip()
    query = User.query
    if q:
        like = f'%{q}%'
        query = query.filter(
            db.or_(User.name.ilike(like), User.email.ilike(like), User.roll_number.ilike(like))
        )
    all_users = query.order_by(User.created_at.desc()).all()
    return render_template('admin/users.html', users=all_users, q=q)


@admin_bp.route('/users/<int:user_id>/toggle', methods=['POST'])
@admin_required
def user_toggle(user_id):
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        flash('Cannot deactivate yourself.', 'warning')
    else:
        user.is_active = not user.is_active
        db.session.commit()
        flash(f'User {"activated" if user.is_active else "deactivated"}.', 'info')
    return redirect(url_for('admin_bp.users'))


@admin_bp.route('/users/<int:user_id>/make-admin', methods=['POST'])
@admin_required
def user_make_admin(user_id):
    user = User.query.get_or_404(user_id)
    user.role = 'admin' if user.role == 'voter' else 'voter'
    db.session.commit()
    flash(f'Role updated to {user.role}.', 'info')
    return redirect(url_for('admin_bp.users'))


# ── Audit Log ─────────────────────────────────────────────────────────────────

@admin_bp.route('/audit')
@admin_required
def audit():
    q = request.args.get('q', '').strip()
    query = AuditLog.query
    if q:
        like = f'%{q}%'
        query = query.filter(
            db.or_(AuditLog.action.ilike(like), AuditLog.detail.ilike(like))
        )
    logs = query.order_by(AuditLog.timestamp.desc()).limit(300).all()
    return render_template('admin/audit.html', logs=logs, q=q)


# ── Reports + PDF Export ──────────────────────────────────────────────────────

@admin_bp.route('/reports')
@admin_required
def reports():
    elections = Election.query.all()
    data = []
    for e in elections:
        candidates = sorted(e.candidates, key=lambda c: c.vote_count, reverse=True)
        total = sum(c.vote_count for c in candidates)
        data.append({'election': e, 'candidates': candidates, 'total': total})
    return render_template('admin/reports.html', data=data)


@admin_bp.route('/reports/pdf')
@admin_required
def reports_pdf():
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib import colors

    elections = Election.query.all()
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4)
    styles = getSampleStyleSheet()
    story = [Paragraph('E-Voting System — Election Report', styles['Title']), Spacer(1, 12)]

    for e in elections:
        candidates = sorted(e.candidates, key=lambda c: c.vote_count, reverse=True)
        total = sum(c.vote_count for c in candidates)
        story.append(Paragraph(e.title, styles['Heading2']))
        story.append(Paragraph(f'Status: {e.status.capitalize()} | Total votes: {total}', styles['Normal']))
        story.append(Spacer(1, 6))
        table_data = [['Candidate', 'Votes', '%']]
        for c in candidates:
            pct = f'{c.vote_count / total * 100:.1f}%' if total else '0%'
            table_data.append([c.name, str(c.vote_count), pct])
        t = Table(table_data, colWidths=[300, 80, 80])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0d6efd')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f0f5ff')]),
        ]))
        story.append(t)
        story.append(Spacer(1, 18))

    doc.build(story)
    buf.seek(0)
    return send_file(buf, mimetype='application/pdf',
                     download_name='election_report.pdf', as_attachment=True)


# ── Live count page ───────────────────────────────────────────────────────────

@admin_bp.route('/live/<int:election_id>')
@admin_required
def live_dashboard(election_id):
    election = Election.query.get_or_404(election_id)
    return render_template('admin/live.html', election=election)
