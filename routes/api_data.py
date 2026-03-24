from datetime import date as date_type

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


@api_data_bp.route('/lecturers', methods=['POST'])
def create_lecturer():
    session = get_session()
    try:
        data = request.get_json()
        lec = Lecturer(
            name=data['name'],
            email=data.get('email', ''),
            max_weekly_hours=data.get('max_weekly_hours', 25),
            max_consecutive_days=data.get('max_consecutive_days', 5),
            prep_time_hours=data.get('prep_time_hours', 4.0),
            marking_hours_per_student=data.get('marking_hours_per_student', 0.5),
            wind_down_hours=data.get('wind_down_hours', 2.0),
        )
        session.add(lec)
        session.commit()
        return jsonify(lec.to_dict()), 201
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


@api_data_bp.route('/lecturers/<int:lecturer_id>', methods=['PUT'])
def update_lecturer(lecturer_id):
    session = get_session()
    try:
        lec = session.query(Lecturer).get(lecturer_id)
        if not lec:
            return jsonify({'error': 'Lecturer not found'}), 404
        data = request.get_json()
        for field in ('name', 'email', 'max_weekly_hours', 'max_consecutive_days',
                      'prep_time_hours', 'marking_hours_per_student', 'wind_down_hours'):
            if field in data:
                setattr(lec, field, data[field])
        session.commit()
        return jsonify(lec.to_dict())
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


@api_data_bp.route('/lecturers/<int:lecturer_id>', methods=['DELETE'])
def delete_lecturer(lecturer_id):
    session = get_session()
    try:
        lec = session.query(Lecturer).get(lecturer_id)
        if not lec:
            return jsonify({'error': 'Lecturer not found'}), 404
        session.delete(lec)
        session.commit()
        return jsonify({'deleted': True})
    except Exception:
        session.rollback()
        raise
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


@api_data_bp.route('/courses', methods=['POST'])
def create_course():
    session = get_session()
    try:
        data = request.get_json()
        course = Course(
            code=data['code'],
            name=data['name'],
            description=data.get('description', ''),
            total_weeks=data.get('total_weeks', 12),
            max_concurrent_runs=data.get('max_concurrent_runs', 2),
        )
        session.add(course)
        session.flush()
        # Add modules if provided
        for i, mod_data in enumerate(data.get('modules', [])):
            mod = Module(
                course_id=course.id,
                code=mod_data['code'],
                name=mod_data['name'],
                duration_hours=mod_data.get('duration_hours', 20),
                sequence_order=mod_data.get('sequence_order', i + 1),
                requires_lab=mod_data.get('requires_lab', False),
                max_class_size=mod_data.get('max_class_size', 30),
                exam_duration_hours=mod_data.get('exam_duration_hours'),
            )
            session.add(mod)
        session.commit()
        return jsonify(course.to_dict(include_modules=True)), 201
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


@api_data_bp.route('/courses/<int:course_id>', methods=['PUT'])
def update_course(course_id):
    session = get_session()
    try:
        course = session.query(Course).get(course_id)
        if not course:
            return jsonify({'error': 'Course not found'}), 404
        data = request.get_json()
        for field in ('code', 'name', 'description', 'total_weeks', 'max_concurrent_runs'):
            if field in data:
                setattr(course, field, data[field])
        session.commit()
        return jsonify(course.to_dict(include_modules=True))
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


@api_data_bp.route('/courses/<int:course_id>', methods=['DELETE'])
def delete_course(course_id):
    session = get_session()
    try:
        course = session.query(Course).get(course_id)
        if not course:
            return jsonify({'error': 'Course not found'}), 404
        session.delete(course)
        session.commit()
        return jsonify({'deleted': True})
    except Exception:
        session.rollback()
        raise
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


@api_data_bp.route('/modules', methods=['POST'])
def create_module():
    session = get_session()
    try:
        data = request.get_json()
        mod = Module(
            course_id=data['course_id'],
            code=data['code'],
            name=data['name'],
            duration_hours=data.get('duration_hours', 20),
            sequence_order=data.get('sequence_order', 1),
            requires_lab=data.get('requires_lab', False),
            max_class_size=data.get('max_class_size', 30),
            exam_duration_hours=data.get('exam_duration_hours'),
        )
        session.add(mod)
        session.commit()
        return jsonify(mod.to_dict()), 201
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


@api_data_bp.route('/modules/<int:module_id>', methods=['PUT'])
def update_module(module_id):
    session = get_session()
    try:
        mod = session.query(Module).get(module_id)
        if not mod:
            return jsonify({'error': 'Module not found'}), 404
        data = request.get_json()
        for field in ('code', 'name', 'duration_hours', 'sequence_order',
                      'requires_lab', 'max_class_size', 'exam_duration_hours'):
            if field in data:
                setattr(mod, field, data[field])
        session.commit()
        return jsonify(mod.to_dict())
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


@api_data_bp.route('/modules/<int:module_id>', methods=['DELETE'])
def delete_module(module_id):
    session = get_session()
    try:
        mod = session.query(Module).get(module_id)
        if not mod:
            return jsonify({'error': 'Module not found'}), 404
        session.delete(mod)
        session.commit()
        return jsonify({'deleted': True})
    except Exception:
        session.rollback()
        raise
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


@api_data_bp.route('/classrooms/<int:classroom_id>')
def get_classroom(classroom_id):
    session = get_session()
    try:
        room = session.query(Classroom).get(classroom_id)
        if not room:
            return jsonify({'error': 'Classroom not found'}), 404
        return jsonify(room.to_dict())
    finally:
        session.close()


@api_data_bp.route('/classrooms', methods=['POST'])
def create_classroom():
    session = get_session()
    try:
        data = request.get_json()
        room = Classroom(
            name=data['name'],
            building=data.get('building', ''),
            capacity=data.get('capacity', 30),
            has_lab_equipment=data.get('has_lab_equipment', False),
            has_projector=data.get('has_projector', True),
        )
        session.add(room)
        session.commit()
        return jsonify(room.to_dict()), 201
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


@api_data_bp.route('/classrooms/<int:classroom_id>', methods=['PUT'])
def update_classroom(classroom_id):
    session = get_session()
    try:
        room = session.query(Classroom).get(classroom_id)
        if not room:
            return jsonify({'error': 'Classroom not found'}), 404
        data = request.get_json()
        for field in ('name', 'building', 'capacity', 'has_lab_equipment', 'has_projector'):
            if field in data:
                setattr(room, field, data[field])
        session.commit()
        return jsonify(room.to_dict())
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


@api_data_bp.route('/classrooms/<int:classroom_id>', methods=['DELETE'])
def delete_classroom(classroom_id):
    session = get_session()
    try:
        room = session.query(Classroom).get(classroom_id)
        if not room:
            return jsonify({'error': 'Classroom not found'}), 404
        session.delete(room)
        session.commit()
        return jsonify({'deleted': True})
    except Exception:
        session.rollback()
        raise
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


@api_data_bp.route('/course-runs', methods=['POST'])
def create_course_run():
    session = get_session()
    try:
        data = request.get_json()
        run = CourseRun(
            course_id=data['course_id'],
            academic_year_id=data['academic_year_id'],
            cohort_label=data['cohort_label'],
            planned_start_date=date_type.fromisoformat(data['planned_start_date']),
            planned_end_date=date_type.fromisoformat(data['planned_end_date']),
            student_count=data.get('student_count', 20),
            status=data.get('status', 'draft'),
        )
        session.add(run)
        session.commit()
        return jsonify(run.to_dict()), 201
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


@api_data_bp.route('/course-runs/<int:run_id>', methods=['PUT'])
def update_course_run(run_id):
    session = get_session()
    try:
        run = session.query(CourseRun).get(run_id)
        if not run:
            return jsonify({'error': 'Course run not found'}), 404
        data = request.get_json()
        for field in ('cohort_label', 'student_count', 'status'):
            if field in data:
                setattr(run, field, data[field])
        if 'planned_start_date' in data:
            run.planned_start_date = date_type.fromisoformat(data['planned_start_date'])
        if 'planned_end_date' in data:
            run.planned_end_date = date_type.fromisoformat(data['planned_end_date'])
        session.commit()
        return jsonify(run.to_dict())
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


@api_data_bp.route('/course-runs/<int:run_id>', methods=['DELETE'])
def delete_course_run(run_id):
    session = get_session()
    try:
        run = session.query(CourseRun).get(run_id)
        if not run:
            return jsonify({'error': 'Course run not found'}), 404
        session.delete(run)
        session.commit()
        return jsonify({'deleted': True})
    except Exception:
        session.rollback()
        raise
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
