from flask import Blueprint, jsonify, request
from models import (
    get_session, Lecturer, Course, Module, CourseRun, AcademicYear,
    Classroom, ScheduledSession, LecturerQualification, Resit, Rule,
)

api_data_bp = Blueprint('api_data', __name__, url_prefix='/api')


# ---------- Lecturers ----------

@api_data_bp.route('/lecturers')
def list_lecturers():
    session = get_session()
    try:
        lecturers = session.query(Lecturer).all()
        result = []
        for lec in lecturers:
            d = lec.to_dict()
            d['qualification_count'] = len(lec.qualifications) if lec.qualifications else 0
            result.append(d)
        return jsonify(result)
    finally:
        session.close()


@api_data_bp.route('/lecturers/<int:lecturer_id>')
def get_lecturer(lecturer_id):
    session = get_session()
    try:
        lec = session.query(Lecturer).get(lecturer_id)
        if not lec:
            return jsonify({'error': 'Lecturer not found'}), 404
        d = lec.to_dict()
        d['qualifications'] = [q.to_dict() for q in lec.qualifications]
        return jsonify(d)
    finally:
        session.close()


# ---------- Courses ----------

@api_data_bp.route('/courses')
def list_courses():
    session = get_session()
    try:
        courses = session.query(Course).all()
        result = []
        for c in courses:
            d = c.to_dict()
            result.append(d)
        return jsonify(result)
    finally:
        session.close()


@api_data_bp.route('/courses/<int:course_id>')
def get_course(course_id):
    session = get_session()
    try:
        course = session.query(Course).get(course_id)
        if not course:
            return jsonify({'error': 'Course not found'}), 404
        return jsonify(course.to_dict(include_modules=True))
    finally:
        session.close()


# ---------- Modules ----------

@api_data_bp.route('/modules')
def list_modules():
    session = get_session()
    try:
        query = session.query(Module)
        course_id = request.args.get('course_id', type=int)
        if course_id is not None:
            query = query.filter_by(course_id=course_id)
        modules = query.order_by(Module.course_id, Module.sequence_order).all()
        return jsonify([m.to_dict() for m in modules])
    finally:
        session.close()


# ---------- Classrooms ----------

@api_data_bp.route('/classrooms')
def list_classrooms():
    session = get_session()
    try:
        classrooms = session.query(Classroom).all()
        return jsonify([c.to_dict() for c in classrooms])
    finally:
        session.close()


# ---------- Course Runs ----------

@api_data_bp.route('/course-runs')
def list_course_runs():
    session = get_session()
    try:
        query = session.query(CourseRun)
        year_id = request.args.get('year_id', type=int)
        course_id = request.args.get('course_id', type=int)
        if year_id is not None:
            query = query.filter_by(academic_year_id=year_id)
        if course_id is not None:
            query = query.filter_by(course_id=course_id)
        runs = query.all()
        return jsonify([r.to_dict() for r in runs])
    finally:
        session.close()


@api_data_bp.route('/course-runs/<int:run_id>')
def get_course_run(run_id):
    session = get_session()
    try:
        run = session.query(CourseRun).get(run_id)
        if not run:
            return jsonify({'error': 'Course run not found'}), 404
        return jsonify(run.to_dict())
    finally:
        session.close()


# ---------- Qualifications ----------

@api_data_bp.route('/qualifications')
def list_qualifications():
    session = get_session()
    try:
        query = session.query(LecturerQualification)
        lecturer_id = request.args.get('lecturer_id', type=int)
        if lecturer_id is not None:
            query = query.filter_by(lecturer_id=lecturer_id)
        quals = query.all()
        return jsonify([q.to_dict() for q in quals])
    finally:
        session.close()


# ---------- Resits ----------

@api_data_bp.route('/resits')
def list_resits():
    session = get_session()
    try:
        query = session.query(Resit)
        course_run_id = request.args.get('course_run_id', type=int)
        status = request.args.get('status')
        if course_run_id is not None:
            query = query.filter_by(course_run_id=course_run_id)
        if status is not None:
            query = query.filter_by(status=status)
        resits = query.all()
        return jsonify([r.to_dict() for r in resits])
    finally:
        session.close()


# ---------- Rules ----------

@api_data_bp.route('/rules')
def list_rules():
    session = get_session()
    try:
        rules = session.query(Rule).all()
        return jsonify([r.to_dict() for r in rules])
    finally:
        session.close()


@api_data_bp.route('/rules/<int:rule_id>', methods=['PUT'])
def update_rule(rule_id):
    session = get_session()
    try:
        rule = session.query(Rule).get(rule_id)
        if not rule:
            return jsonify({'error': 'Rule not found'}), 404
        data = request.get_json()
        if 'enabled' in data:
            rule.enabled = data['enabled']
        if 'value' in data:
            rule.value = data['value']
        session.commit()
        return jsonify(rule.to_dict())
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


# ---------- Academic Years ----------

@api_data_bp.route('/academic-years')
def list_academic_years():
    session = get_session()
    try:
        years = session.query(AcademicYear).all()
        return jsonify([y.to_dict() for y in years])
    finally:
        session.close()
