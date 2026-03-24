from flask import Blueprint, render_template

views_bp = Blueprint('views', __name__)


@views_bp.route('/')
def index():
    return render_template('index.html')


@views_bp.route('/gantt')
def gantt():
    return render_template('gantt.html')


@views_bp.route('/courses')
def courses():
    return render_template('courses.html')


@views_bp.route('/lecturers')
def lecturers():
    return render_template('lecturers.html')


@views_bp.route('/rules')
def rules():
    return render_template('rules.html')


@views_bp.route('/solver')
def solver():
    return render_template('solver.html')
