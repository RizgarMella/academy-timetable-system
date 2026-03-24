"""Timetable scheduling engine.

Uses a greedy heuristic scheduler that reliably produces valid schedules.
Processes course runs by start date, schedules modules sequentially,
and assigns the best available lecturer and classroom for each module block.

The scheduler respects:
- Module sequencing within course runs
- Lecturer qualifications and availability
- Classroom capacity and lab requirements
- No double-booking of lecturers or classrooms
- Prep time and wind-down/marking time gaps
- Teacher-cannot-examine rule for resits
- Load balancing across lecturers
"""

import logging
import math
import time
from collections import defaultdict
from datetime import timedelta

from models import (
    AcademicYear, Classroom, ClassroomAvailability, Course, CourseRun,
    Lecturer, LecturerAvailability, LecturerQualification, Module,
    Resit, Rule, ScheduledSession,
)
from solver.utils import (
    SLOTS_PER_DAY, date_to_day_index, day_index_to_date,
    duration_hours_to_days, get_total_weekdays,
)

logger = logging.getLogger(__name__)


class TimetableSolver:
    def __init__(self, session):
        self.session = session

    def solve(self, academic_year_id, timeout_seconds=120):
        start_time = time.time()

        data = self._load_data(academic_year_id)
        if not data['course_runs']:
            return {
                'status': 'NO_DATA', 'sessions': 0,
                'wall_time': 0.0, 'objective': 0.0,
                'stats': {'message': 'No course runs found.'},
            }

        # Build occupation tracking structures
        lec_occupied = defaultdict(set)     # lecturer_id -> set of day_indices
        room_occupied = defaultdict(set)    # classroom_id -> set of day_indices
        lec_total_hours = defaultdict(int)  # for load balancing

        # Track lecturer's last module end day (for prep/wind-down)
        lec_last_end = defaultdict(lambda: -100)  # lecturer_id -> last end day

        # Sort course runs by start date
        course_runs = sorted(data['course_runs'], key=lambda cr: cr.planned_start_date)

        sessions_created = 0
        conflicts = []

        # Clear previous proposals
        cr_ids = [cr.id for cr in course_runs]
        self.session.query(ScheduledSession).filter(
            ScheduledSession.course_run_id.in_(cr_ids),
            ScheduledSession.is_proposal == True,
        ).delete(synchronize_session='fetch')

        rules = data['rules']
        teacher_cannot_examine = rules.get('teacher_cannot_examine', None)
        teacher_cannot_examine_enabled = (
            teacher_cannot_examine and teacher_cannot_examine.enabled
            and teacher_cannot_examine.value.lower() == 'true'
        )

        for cr in course_runs:
            modules = data['modules_by_run'].get(cr.id, [])
            run_start = data['run_start_day'][cr.id]
            run_end = data['run_end_day'][cr.id]

            # Track the earliest day the next module can start
            next_available_day = run_start

            for mod in modules:
                dur_days = duration_hours_to_days(mod.duration_hours)

                # Find qualified lecturers, sorted by preference
                qualified = self._get_qualified_lecturers(
                    mod.id, data, lec_total_hours
                )
                if not qualified:
                    conflicts.append(
                        f"No qualified lecturer for {mod.code} in {cr.cohort_label}"
                    )
                    next_available_day += dur_days
                    continue

                # Find eligible classrooms
                eligible_rooms = self._get_eligible_rooms(
                    mod, cr.student_count, data
                )
                if not eligible_rooms:
                    conflicts.append(
                        f"No eligible classroom for {mod.code} in {cr.cohort_label}"
                    )
                    next_available_day += dur_days
                    continue

                # Try to schedule this module block
                scheduled = False
                for lec_id, lec_prof in qualified:
                    lec = data['lecturers_by_id'][lec_id]
                    prep_days = max(1, math.ceil(lec.prep_time_hours / SLOTS_PER_DAY))
                    wind_days = max(1, math.ceil(lec.wind_down_hours / SLOTS_PER_DAY))

                    # Earliest start considering prep time after lecturer's last block
                    earliest = next_available_day
                    if lec_last_end[lec_id] >= 0:
                        earliest = max(earliest, lec_last_end[lec_id] + prep_days)

                    for room in eligible_rooms:
                        # Find a contiguous block of dur_days where both
                        # lecturer and room are free
                        start_day = self._find_free_block(
                            earliest, dur_days, run_end,
                            lec_id, room.id,
                            lec_occupied, room_occupied,
                            data['lec_unavail'], data['room_unavail'],
                        )
                        if start_day is None:
                            continue

                        # Schedule it
                        remaining = mod.duration_hours
                        session_type = 'lab' if mod.requires_lab else 'lecture'

                        for d in range(dur_days):
                            day_idx = start_day + d
                            session_date = day_index_to_date(
                                day_idx, data['year_start_date']
                            )
                            slots = min(remaining, SLOTS_PER_DAY)
                            remaining -= slots

                            sess = ScheduledSession(
                                course_run_id=cr.id,
                                module_id=mod.id,
                                lecturer_id=lec_id,
                                classroom_id=room.id,
                                date=session_date,
                                start_slot=0,
                                duration_slots=slots,
                                session_type=session_type,
                                is_proposal=True,
                            )
                            self.session.add(sess)
                            sessions_created += 1

                            lec_occupied[lec_id].add(day_idx)
                            room_occupied[room.id].add(day_idx)

                        lec_total_hours[lec_id] += mod.duration_hours
                        lec_last_end[lec_id] = start_day + dur_days

                        # Next module starts after this one plus wind-down
                        next_available_day = start_day + dur_days + wind_days

                        scheduled = True
                        break

                    if scheduled:
                        break

                if not scheduled:
                    conflicts.append(
                        f"Could not schedule {mod.code} in {cr.cohort_label}"
                    )
                    next_available_day += dur_days

                # Check timeout
                if time.time() - start_time > timeout_seconds:
                    conflicts.append('Solver timed out')
                    break

        # Schedule resits
        resit_count = self._schedule_resits(
            data, lec_occupied, room_occupied,
            teacher_cannot_examine_enabled,
        )
        sessions_created += resit_count

        self.session.flush()

        wall_time = time.time() - start_time
        status = 'OPTIMAL' if not conflicts else 'FEASIBLE'

        logger.info(
            "Scheduled %d sessions in %.1fs (%d conflicts)",
            sessions_created, wall_time, len(conflicts),
        )

        return {
            'status': status,
            'sessions': sessions_created,
            'wall_time': wall_time,
            'objective': sum(lec_total_hours.values()),
            'stats': {
                'conflicts': conflicts,
                'wall_time': wall_time,
                'lecturer_hours': dict(lec_total_hours),
                'resit_sessions': resit_count,
            },
        }

    def _load_data(self, academic_year_id):
        session = self.session
        ay = session.query(AcademicYear).filter_by(id=academic_year_id).one_or_none()
        if ay is None:
            raise ValueError(f"Academic year {academic_year_id} not found.")

        year_start = ay.start_date
        year_end = ay.end_date

        course_runs = session.query(CourseRun).filter_by(
            academic_year_id=academic_year_id
        ).all()

        modules_by_run = {}
        course_ids = {cr.course_id for cr in course_runs}
        all_modules = []
        for cid in course_ids:
            mods = session.query(Module).filter_by(
                course_id=cid
            ).order_by(Module.sequence_order).all()
            all_modules.extend(mods)

        for cr in course_runs:
            modules_by_run[cr.id] = [
                m for m in all_modules if m.course_id == cr.course_id
            ]

        lecturers = session.query(Lecturer).all()
        lecturers_by_id = {l.id: l for l in lecturers}
        classrooms = session.query(Classroom).all()

        quals = session.query(LecturerQualification).all()
        # module_id -> [(lecturer_id, proficiency_level, can_examine)]
        quals_by_module = defaultdict(list)
        for q in quals:
            quals_by_module[q.module_id].append(
                (q.lecturer_id, q.proficiency_level, q.can_examine)
            )

        resits = (
            session.query(Resit).join(CourseRun)
            .filter(CourseRun.academic_year_id == academic_year_id)
            .all()
        )

        rules_list = session.query(Rule).all()
        rules = {r.key: r for r in rules_list}

        total_weekdays = get_total_weekdays(year_start, year_end)
        run_start_day = {}
        run_end_day = {}
        for cr in course_runs:
            try:
                run_start_day[cr.id] = date_to_day_index(
                    max(cr.planned_start_date, year_start), year_start
                )
                run_end_day[cr.id] = date_to_day_index(
                    min(cr.planned_end_date, year_end), year_start
                )
            except ValueError:
                run_start_day[cr.id] = 0
                run_end_day[cr.id] = total_weekdays - 1

        lec_unavail = defaultdict(set)
        for la in session.query(LecturerAvailability).filter_by(available=False).all():
            if year_start <= la.date <= year_end:
                try:
                    lec_unavail[la.lecturer_id].add(
                        date_to_day_index(la.date, year_start)
                    )
                except ValueError:
                    pass

        room_unavail = defaultdict(set)
        for ra in session.query(ClassroomAvailability).filter_by(available=False).all():
            if year_start <= ra.date <= year_end:
                try:
                    room_unavail[ra.classroom_id].add(
                        date_to_day_index(ra.date, year_start)
                    )
                except ValueError:
                    pass

        return {
            'academic_year': ay,
            'year_start_date': year_start,
            'year_end_date': year_end,
            'course_runs': course_runs,
            'modules_by_run': modules_by_run,
            'lecturers': lecturers,
            'lecturers_by_id': lecturers_by_id,
            'classrooms': classrooms,
            'quals_by_module': quals_by_module,
            'resits': resits,
            'rules': rules,
            'run_start_day': run_start_day,
            'run_end_day': run_end_day,
            'total_weekdays': total_weekdays,
            'lec_unavail': lec_unavail,
            'room_unavail': room_unavail,
        }

    def _get_qualified_lecturers(self, module_id, data, lec_total_hours):
        """Get qualified lecturers sorted by proficiency then load balance."""
        quals = data['quals_by_module'].get(module_id, [])
        prof_order = {'primary': 0, 'secondary': 1, 'emergency': 2}

        result = []
        for lec_id, prof, can_exam in quals:
            result.append((
                lec_id, prof,
                prof_order.get(prof, 3),
                lec_total_hours.get(lec_id, 0),
            ))

        # Sort: primary first, then least loaded
        result.sort(key=lambda x: (x[2], x[3]))
        return [(r[0], r[1]) for r in result]

    def _get_eligible_rooms(self, module, student_count, data):
        """Get classrooms that meet capacity and lab requirements."""
        rooms = []
        for room in data['classrooms']:
            if room.capacity < student_count:
                continue
            if module.requires_lab and not room.has_lab_equipment:
                continue
            rooms.append(room)
        # Prefer smallest adequate room
        rooms.sort(key=lambda r: r.capacity)
        return rooms

    def _find_free_block(self, earliest, dur_days, latest_end,
                         lec_id, room_id,
                         lec_occupied, room_occupied,
                         lec_unavail, room_unavail):
        """Find the earliest contiguous block of dur_days free days."""
        max_day = latest_end - dur_days + 1
        day = earliest

        while day <= max_day:
            # Check all days in the block
            block_ok = True
            for d in range(dur_days):
                dd = day + d
                if dd in lec_occupied[lec_id]:
                    day = dd + 1
                    block_ok = False
                    break
                if dd in room_occupied[room_id]:
                    day = dd + 1
                    block_ok = False
                    break
                if dd in lec_unavail.get(lec_id, set()):
                    day = dd + 1
                    block_ok = False
                    break
                if dd in room_unavail.get(room_id, set()):
                    day = dd + 1
                    block_ok = False
                    break

            if block_ok:
                return day

        return None

    def _schedule_resits(self, data, lec_occupied, room_occupied,
                         teacher_cannot_examine):
        """Schedule resit exams, respecting the teacher-cannot-examine rule."""
        count = 0
        for resit in data.get('resits', []):
            if resit.status != 'pending':
                continue

            mod = None
            for cr in data['course_runs']:
                if cr.id == resit.course_run_id:
                    for m in data['modules_by_run'].get(cr.id, []):
                        if m.id == resit.module_id:
                            mod = m
                            break
                    break

            if mod is None:
                continue

            # Find an examiner (not the original teacher if rule enabled)
            quals = data['quals_by_module'].get(resit.module_id, [])
            for lec_id, prof, can_exam in quals:
                if not can_exam:
                    continue
                if teacher_cannot_examine and lec_id == resit.original_lecturer_id:
                    continue

                # Find a day and room for a 1-day exam
                exam_days = max(1, math.ceil(
                    (mod.exam_duration_hours or 3) / SLOTS_PER_DAY
                ))

                try:
                    target_day = date_to_day_index(
                        resit.required_by_date, data['year_start_date']
                    )
                except ValueError:
                    continue

                # Search backwards from required_by_date
                eligible_rooms = self._get_eligible_rooms(mod, 5, data)
                scheduled = False
                for room in eligible_rooms:
                    start = self._find_free_block(
                        max(0, target_day - 20), exam_days, target_day,
                        lec_id, room.id,
                        lec_occupied, room_occupied,
                        data['lec_unavail'], data['room_unavail'],
                    )
                    if start is not None:
                        for d in range(exam_days):
                            day_idx = start + d
                            session_date = day_index_to_date(
                                day_idx, data['year_start_date']
                            )
                            sess = ScheduledSession(
                                course_run_id=resit.course_run_id,
                                module_id=resit.module_id,
                                lecturer_id=lec_id,
                                classroom_id=room.id,
                                date=session_date,
                                start_slot=0,
                                duration_slots=mod.exam_duration_hours or 3,
                                session_type='resit',
                                is_proposal=True,
                            )
                            self.session.add(sess)
                            count += 1
                            lec_occupied[lec_id].add(day_idx)
                            room_occupied[room.id].add(day_idx)

                        scheduled = True
                        break

                if scheduled:
                    break

        return count
