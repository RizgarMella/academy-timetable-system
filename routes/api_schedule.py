import math
from collections import defaultdict
from datetime import timedelta

from flask import Blueprint, jsonify, request
from sqlalchemy.orm import joinedload

from models import (
    get_session, Lecturer, Course, Module, CourseRun, AcademicYear,
    Classroom, ScheduledSession, LecturerQualification, Resit, Rule,
)

api_schedule_bp = Blueprint('api_schedule', __name__, url_prefix='/api/schedule')


# ---------- List scheduled sessions ----------

@api_schedule_bp.route('')
def list_sessions():
    session = get_session()
    try:
        query = session.query(ScheduledSession).options(
            joinedload(ScheduledSession.module),
            joinedload(ScheduledSession.lecturer),
            joinedload(ScheduledSession.classroom),
            joinedload(ScheduledSession.course_run).joinedload(CourseRun.course),
        )

        year_id = request.args.get('year_id', type=int)
        lecturer_id = request.args.get('lecturer_id', type=int)
        course_id = request.args.get('course_id', type=int)
        course_run_id = request.args.get('course_run_id', type=int)
        classroom_id = request.args.get('classroom_id', type=int)
        session_type = request.args.get('session_type')
        is_proposal = request.args.get('is_proposal')

        if year_id is not None:
            query = query.join(CourseRun).filter(
                CourseRun.academic_year_id == year_id
            )
        if lecturer_id is not None:
            query = query.filter(ScheduledSession.lecturer_id == lecturer_id)
        if course_id is not None:
            if year_id is None:
                query = query.join(CourseRun)
            query = query.filter(CourseRun.course_id == course_id)
        if course_run_id is not None:
            query = query.filter(ScheduledSession.course_run_id == course_run_id)
        if classroom_id is not None:
            query = query.filter(ScheduledSession.classroom_id == classroom_id)
        if session_type is not None:
            query = query.filter(ScheduledSession.session_type == session_type)
        if is_proposal is not None:
            query = query.filter(
                ScheduledSession.is_proposal == (is_proposal.lower() in ('true', '1', 'yes'))
            )

        sessions_list = query.order_by(ScheduledSession.date, ScheduledSession.start_slot).all()
        return jsonify([s.to_dict() for s in sessions_list])
    finally:
        session.close()


# ---------- Gantt data ----------

@api_schedule_bp.route('/gantt')
def gantt_data():
    session = get_session()
    try:
        year_id = request.args.get('year_id', type=int)
        lecturer_id = request.args.get('lecturer_id', type=int)
        course_id = request.args.get('course_id', type=int)
        classroom_id = request.args.get('classroom_id', type=int)
        group_by = request.args.get('group_by', 'course_run')

        # Load academic year for date range
        year_start = None
        year_end = None
        if year_id is not None:
            ay = session.query(AcademicYear).get(year_id)
            if ay:
                year_start = ay.start_date.isoformat()
                year_end = ay.end_date.isoformat()

        # Build query
        query = session.query(ScheduledSession).options(
            joinedload(ScheduledSession.module),
            joinedload(ScheduledSession.lecturer),
            joinedload(ScheduledSession.classroom),
            joinedload(ScheduledSession.course_run).joinedload(CourseRun.course),
            joinedload(ScheduledSession.course_run).joinedload(CourseRun.academic_year),
        )

        if year_id is not None:
            query = query.join(CourseRun).filter(
                CourseRun.academic_year_id == year_id
            )
        if lecturer_id is not None:
            query = query.filter(ScheduledSession.lecturer_id == lecturer_id)
        if course_id is not None:
            if year_id is None:
                query = query.join(CourseRun)
            query = query.filter(CourseRun.course_id == course_id)
        if classroom_id is not None:
            query = query.filter(ScheduledSession.classroom_id == classroom_id)

        all_sessions = query.order_by(ScheduledSession.date).all()

        # Determine year_start/year_end from data if not set via year_id
        if year_start is None and all_sessions:
            ay = all_sessions[0].course_run.academic_year
            year_start = ay.start_date.isoformat()
            year_end = ay.end_date.isoformat()

        # Group sessions into rows based on group_by
        rows_dict = defaultdict(list)

        for s in all_sessions:
            if group_by == 'lecturer':
                row_key = s.lecturer_id
            elif group_by == 'classroom':
                row_key = s.classroom_id
            else:
                row_key = s.course_run_id
            rows_dict[row_key].append(s)

        rows = []
        for row_key, row_sessions in rows_dict.items():
            # Build row label and sublabel
            sample = row_sessions[0]
            if group_by == 'lecturer':
                row_id = f'lec-{row_key}'
                label = sample.lecturer.name if sample.lecturer else f'Lecturer {row_key}'
                sublabel = sample.lecturer.email if sample.lecturer else ''
            elif group_by == 'classroom':
                row_id = f'room-{row_key}'
                label = sample.classroom.name if sample.classroom else f'Room {row_key}'
                sublabel = sample.classroom.building if sample.classroom else ''
            else:
                row_id = f'run-{row_key}'
                cr = sample.course_run
                label = f'{cr.course.code} {cr.cohort_label}' if cr and cr.course else f'Run {row_key}'
                sublabel = cr.course.name if cr and cr.course else ''

            # Aggregate consecutive sessions for the same (course_run, module) into blocks
            blocks = _aggregate_blocks(row_sessions)

            rows.append({
                'id': row_id,
                'label': label,
                'sublabel': sublabel,
                'blocks': blocks,
            })

        return jsonify({
            'year_start': year_start,
            'year_end': year_end,
            'rows': rows,
        })
    finally:
        session.close()


def _aggregate_blocks(sessions):
    """Group consecutive ScheduledSession records for the same (course_run_id, module_id)
    into a single block with start_date and end_date."""
    # Sort by course_run_id, module_id, date
    sorted_sessions = sorted(sessions, key=lambda s: (s.course_run_id, s.module_id, s.date))

    blocks = []
    current_block = None

    for s in sorted_sessions:
        block_key = (s.course_run_id, s.module_id)

        if (current_block is not None
                and current_block['_key'] == block_key
                and (s.date - current_block['_last_date']).days <= 3):
            # Extend current block (allow weekend gaps of up to 3 days)
            current_block['end_date'] = s.date.isoformat()
            current_block['_last_date'] = s.date
        else:
            # Save previous block
            if current_block is not None:
                del current_block['_key']
                del current_block['_last_date']
                blocks.append(current_block)

            cr = s.course_run
            current_block = {
                'id': s.id,
                'module_name': s.module.name if s.module else None,
                'module_code': s.module.code if s.module else None,
                'start_date': s.date.isoformat(),
                'end_date': s.date.isoformat(),
                'lecturer': s.lecturer.name if s.lecturer else None,
                'classroom': s.classroom.name if s.classroom else None,
                'session_type': s.session_type,
                'is_proposal': s.is_proposal,
                'course_code': cr.course.code if cr and cr.course else None,
                'student_count': cr.student_count if cr else None,
                '_key': block_key,
                '_last_date': s.date,
            }

    if current_block is not None:
        del current_block['_key']
        del current_block['_last_date']
        blocks.append(current_block)

    return blocks


# ---------- Lecturer loading ----------

@api_schedule_bp.route('/loading')
def lecturer_loading():
    session = get_session()
    try:
        year_id = request.args.get('year_id', type=int)

        if year_id is None:
            return jsonify({'error': 'year_id is required'}), 400

        ay = session.query(AcademicYear).get(year_id)
        if not ay:
            return jsonify({'error': 'Academic year not found'}), 404

        # Generate week labels from year start to end
        weeks = []
        week_start_dates = []
        current = ay.start_date
        # Align to Monday
        current = current - timedelta(days=current.weekday())
        while current <= ay.end_date:
            iso_year, iso_week, _ = current.isocalendar()
            weeks.append(f'{iso_year}-W{iso_week:02d}')
            week_start_dates.append(current)
            current += timedelta(weeks=1)

        num_weeks = len(weeks)

        # Load all sessions for this year
        all_sessions = (
            session.query(ScheduledSession)
            .options(
                joinedload(ScheduledSession.module),
                joinedload(ScheduledSession.course_run).joinedload(CourseRun.course),
            )
            .join(CourseRun)
            .filter(CourseRun.academic_year_id == year_id)
            .all()
        )

        # Group by lecturer
        sessions_by_lecturer = defaultdict(list)
        for s in all_sessions:
            sessions_by_lecturer[s.lecturer_id].append(s)

        lecturers = session.query(Lecturer).all()
        lecturer_data = []
        all_total_hours = []

        for lec in lecturers:
            lec_sessions = sessions_by_lecturer.get(lec.id, [])
            weekly_hours = [0] * num_weeks
            weekly_details = [[] for _ in range(num_weeks)]

            for s in lec_sessions:
                # Determine which week index this session falls in
                week_idx = _date_to_week_index(s.date, week_start_dates)
                if week_idx is not None and 0 <= week_idx < num_weeks:
                    weekly_hours[week_idx] += s.duration_slots
                    # Add detail
                    cr = s.course_run
                    course_code = cr.course.code if cr and cr.course else 'Unknown'
                    module_name = s.module.name if s.module else 'Unknown'

                    # Merge into existing detail or add new
                    found = False
                    for detail in weekly_details[week_idx]:
                        if detail['course'] == course_code and detail['module'] == module_name:
                            detail['hours'] += s.duration_slots
                            found = True
                            break
                    if not found:
                        weekly_details[week_idx].append({
                            'course': course_code,
                            'module': module_name,
                            'hours': s.duration_slots,
                        })

            total_hours = sum(weekly_hours)
            max_weekly = lec.max_weekly_hours or 25
            total_capacity = max_weekly * num_weeks
            capacity_pct = round((total_hours / total_capacity) * 100) if total_capacity > 0 else 0

            all_total_hours.append(total_hours)

            lecturer_data.append({
                'id': lec.id,
                'name': lec.name,
                'max_weekly_hours': max_weekly,
                'total_hours': total_hours,
                'capacity_pct': capacity_pct,
                'weekly_hours': weekly_hours,
                'weekly_details': weekly_details,
            })

        # Calculate balance score: 1 - (std_dev / mean), clamped to 0-1
        balance_score = 0.0
        if all_total_hours and len(all_total_hours) > 1:
            mean_hours = sum(all_total_hours) / len(all_total_hours)
            if mean_hours > 0:
                variance = sum((h - mean_hours) ** 2 for h in all_total_hours) / len(all_total_hours)
                std_dev = math.sqrt(variance)
                balance_score = max(0.0, min(1.0, 1.0 - (std_dev / mean_hours)))

        return jsonify({
            'lecturers': lecturer_data,
            'balance_score': round(balance_score, 2),
            'weeks': weeks,
        })
    finally:
        session.close()


def _date_to_week_index(date, week_start_dates):
    """Find which week index a date falls into."""
    for i, ws in enumerate(week_start_dates):
        week_end = ws + timedelta(days=6)
        if ws <= date <= week_end:
            return i
    return None


# ---------- Confirm proposals ----------

@api_schedule_bp.route('/confirm', methods=['POST'])
def confirm_proposals():
    session = get_session()
    try:
        data = request.get_json()
        year_id = data.get('year_id')
        if year_id is None:
            return jsonify({'error': 'year_id is required'}), 400

        count = (
            session.query(ScheduledSession)
            .join(CourseRun)
            .filter(
                CourseRun.academic_year_id == year_id,
                ScheduledSession.is_proposal == True,
            )
            .update({ScheduledSession.is_proposal: False}, synchronize_session='fetch')
        )
        session.commit()

        return jsonify({
            'confirmed': count,
            'message': f'Confirmed {count} sessions.',
        })
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
