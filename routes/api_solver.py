import threading
import uuid
import traceback

from flask import Blueprint, jsonify, request

from models import get_session
from solver.engine import TimetableSolver

api_solver_bp = Blueprint('api_solver', __name__, url_prefix='/api/solver')

# Module-level dict to store job state
_jobs = {}


def _run_solver(job_id, academic_year_id, timeout_seconds):
    """Run the solver in a background thread and update job state."""
    try:
        _jobs[job_id]['status'] = 'running'
        session = get_session()
        try:
            solver = TimetableSolver(session)
            result = solver.solve(academic_year_id, timeout_seconds=timeout_seconds)
            session.commit()
            _jobs[job_id]['status'] = 'completed'
            _jobs[job_id]['stats'] = result
        except Exception as e:
            session.rollback()
            _jobs[job_id]['status'] = 'failed'
            _jobs[job_id]['stats'] = {
                'error': str(e),
                'traceback': traceback.format_exc(),
            }
        finally:
            session.close()
    except Exception as e:
        _jobs[job_id]['status'] = 'failed'
        _jobs[job_id]['stats'] = {
            'error': str(e),
            'traceback': traceback.format_exc(),
        }


@api_solver_bp.route('/run', methods=['POST'])
def run_solver():
    data = request.get_json()
    academic_year_id = data.get('academic_year_id')
    timeout_seconds = data.get('timeout_seconds', 120)

    if academic_year_id is None:
        return jsonify({'error': 'academic_year_id is required'}), 400

    job_id = str(uuid.uuid4())
    _jobs[job_id] = {
        'status': 'running',
        'stats': {},
    }

    thread = threading.Thread(
        target=_run_solver,
        args=(job_id, academic_year_id, timeout_seconds),
        daemon=True,
    )
    thread.start()

    return jsonify({
        'job_id': job_id,
        'status': 'running',
    })


@api_solver_bp.route('/status/<job_id>')
def solver_status(job_id):
    job = _jobs.get(job_id)
    if job is None:
        return jsonify({'error': 'Job not found'}), 404
    return jsonify({
        'status': job['status'],
        'stats': job['stats'],
    })
