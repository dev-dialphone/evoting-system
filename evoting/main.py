import base64
import os
import secrets
from flask import (Blueprint, render_template, redirect, url_for, flash,
                   abort, request, current_app, jsonify)
from flask_login import login_required, current_user
from sqlalchemy.exc import IntegrityError
from models import db, Election, Candidate, Vote, AuditLog
from forms import VoteForm

main = Blueprint('main', __name__)


def _save_snapshot(data_url, election_id):
    """Decode base64 webcam image and save. Returns filename or None."""
    try:
        header, encoded = data_url.split(',', 1)
        img_bytes = base64.b64decode(encoded)
        fname = f'snap_{election_id}_{secrets.token_hex(8)}.jpg'
        path = os.path.join(current_app.config['UPLOAD_FOLDER'], fname)
        with open(path, 'wb') as f:
            f.write(img_bytes)
        return fname
    except Exception:
        return None


@main.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    return redirect(url_for('auth.login'))


@main.route('/dashboard')
@login_required
def dashboard():
    elections = Election.query.order_by(Election.start_time.desc()).all()
    voted_ids = {v.election_id for v in Vote.query.filter_by(user_id=current_user.id).all()}
    return render_template('dashboard.html', elections=elections, voted_ids=voted_ids)


@main.route('/election/<int:election_id>', methods=['GET', 'POST'])
@login_required
def election_detail(election_id):
    election = Election.query.get_or_404(election_id)

    if not election.is_eligible(current_user):
        flash('You are not eligible to vote in this election.', 'warning')
        return redirect(url_for('main.dashboard'))

    already_voted = Vote.query.filter_by(
        user_id=current_user.id, election_id=election_id
    ).first()

    form = VoteForm()
    form.candidate_id.choices = [(c.id, c.name) for c in election.candidates]

    if form.validate_on_submit():
        if not election.is_open:
            flash('This election is not open for voting.', 'warning')
            return redirect(url_for('main.election_detail', election_id=election_id))
        if already_voted:
            flash('You have already voted in this election.', 'warning')
            return redirect(url_for('main.election_detail', election_id=election_id))

        candidate = Candidate.query.get_or_404(form.candidate_id.data)
        if candidate.election_id != election_id:
            abort(400)

        snapshot_file = None
        if form.snapshot.data:
            snapshot_file = _save_snapshot(form.snapshot.data, election_id)

        vote = Vote(
            user_id=current_user.id,
            election_id=election_id,
            candidate_id=candidate.id,
            snapshot=snapshot_file,
        )
        db.session.add(vote)
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            flash('You have already voted.', 'warning')
            return redirect(url_for('main.election_detail', election_id=election_id))

        db.session.add(AuditLog(
            user_id=current_user.id,
            action='vote_cast',
            detail=f'election={election_id} candidate={candidate.id}',
            ip_address=request.remote_addr,
        ))
        db.session.commit()
        flash(f'Vote cast! Your receipt token: {vote.receipt_token}', 'success')
        return redirect(url_for('main.results', election_id=election_id))

    return render_template('election_detail.html', election=election, form=form, already_voted=already_voted)


@main.route('/vote')
@login_required
def vote_home():
    all_elections = Election.query.order_by(Election.start_time.desc()).all()
    voted_ids = {v.election_id for v in Vote.query.filter_by(user_id=current_user.id).all()}
    open_elections = [e for e in all_elections if e.is_open]
    upcoming = [e for e in all_elections if e.status == 'upcoming']
    voted_elections = [e for e in all_elections if e.id in voted_ids]
    return render_template('vote.html',
                           open_elections=open_elections,
                           upcoming=upcoming,
                           voted_elections=voted_elections,
                           voted_ids=voted_ids)


@main.route('/election/<int:election_id>/results')
@login_required
def results(election_id):
    election = Election.query.get_or_404(election_id)
    candidates = sorted(election.candidates, key=lambda c: c.vote_count, reverse=True)
    total = sum(c.vote_count for c in candidates)
    return render_template('results.html', election=election, candidates=candidates, total=total)


# Live vote count API (JSON, polled every 5 s by admin dashboard JS)
@main.route('/api/election/<int:election_id>/live')
@login_required
def live_count(election_id):
    if not current_user.is_admin:
        abort(403)
    election = Election.query.get_or_404(election_id)
    data = [{'id': c.id, 'name': c.name, 'votes': c.vote_count}
            for c in election.candidates]
    total = sum(c['votes'] for c in data)
    return jsonify({'total': total, 'candidates': data})
