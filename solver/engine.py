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
- Delivery modes: single, team teaching, split/handover
- Module-level rules (consecutive days, time-of-day, etc.)
"""

import logging
import math
import time
from collections import defaultdict
from datetime import timedelta
from itertools import combinations

from models import (
    AcademicYear, Classroom, ClassroomAvailability, Course, CourseRun,
    Lecturer, LecturerAvailability, LecturerQualification, Module,
    ModuleRule, Resit, Rule, ScheduledSession,
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
        lec_last_end = defaultdict(lambda: -100)

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

            next_available_day = run_start

            for mod in modules:
                delivery_mode = getattr(mod, 'delivery_mode', 'single') or 'single'

                if delivery_mode == 'team':
                    result = self._schedule_team(
                        mod, cr, next_available_day, run_end, data,
                        lec_occupied, room_occupied, lec_total_hours, lec_last_end,
                    )
                elif delivery_mode == 'split':
                    result = self._schedule_split(
                        mod, cr, next_available_day, run_end, data,
                        lec_occupied, room_occupied, lec_total_hours, lec_last_end,
                    )
                else:
                    result = self._schedule_single(
                        mod, cr, next_available_day, run_end, data,
                        lec_occupied, room_occupied, lec_total_hours, lec_last_end,
                    )

                sessions_created += result['sessions']
                if result['conflict']:
                    conflicts.append(result['conflict'])
                next_available_day = result['next_day']

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

    # ------------------------------------------------------------------ #
    #  Single-lecturer scheduling (original behaviour)
    # ------------------------------------------------------------------ #

    def _schedule_single(self, mod, cr, next_available_day, run_end, data,
                         lec_occupied, room_occupied, lec_total_hours, lec_last_end):
        dur_days = duration_hours_to_days(mod.duration_hours)

        qualified = self._get_qualified_lecturers(mod.id, data, lec_total_hours)
        if not qualified:
            return {
                'sessions': 0,
                'conflict': f"No qualified lecturer for {mod.code} in {cr.cohort_label}",
                'next_day': next_available_day + dur_days,
            }

        eligible_rooms = self._get_eligible_rooms(mod, cr.student_count, data)
        if not eligible_rooms:
            return {
                'sessions': 0,
                'conflict': f"No eligible classroom for {mod.code} in {cr.cohort_label}",
                'next_day': next_available_day + dur_days,
            }

        for lec_id, lec_prof in qualified:
            lec = data['lecturers_by_id'][lec_id]
            prep_days = max(1, math.ceil(lec.prep_time_hours / SLOTS_PER_DAY))
            wind_days = max(1, math.ceil(lec.wind_down_hours / SLOTS_PER_DAY))

            earliest = next_available_day
            if lec_last_end[lec_id] >= 0:
                earliest = max(earliest, lec_last_end[lec_id] + prep_days)

            for room in eligible_rooms:
                start_day = self._find_free_block(
                    earliest, dur_days, run_end,
                    lec_id, room.id,
                    lec_occupied, room_occupied,
                    data['lec_unavail'], data['room_unavail'],
                )
                if start_day is None:
                    continue

                count = self._emit_sessions(
                    cr.id, mod, lec_id, None, room.id, start_day, dur_days,
                    data['year_start_date'], lec_occupied, room_occupied,
                )
                lec_total_hours[lec_id] += mod.duration_hours
                lec_last_end[lec_id] = start_day + dur_days

                return {
                    'sessions': count,
                    'conflict': None,
                    'next_day': start_day + dur_days + wind_days,
                }

        return {
            'sessions': 0,
            'conflict': f"Could not schedule {mod.code} in {cr.cohort_label}",
            'next_day': next_available_day + dur_days,
        }

    # ------------------------------------------------------------------ #
    #  Team teaching: N lecturers simultaneously in the same room
    # ------------------------------------------------------------------ #

    def _schedule_team(self, mod, cr, next_available_day, run_end, data,
                       lec_occupied, room_occupied, lec_total_hours, lec_last_end):
        dur_days = duration_hours_to_days(mod.duration_hours)
        team_size = max(2, getattr(mod, 'team_size', 2) or 2)

        qualified = self._get_qualified_lecturers(mod.id, data, lec_total_hours)
        if len(qualified) < team_size:
            return {
                'sessions': 0,
                'conflict': f"Need {team_size} lecturers for team-taught {mod.code}, only {len(qualified)} qualified",
                'next_day': next_available_day + dur_days,
            }

        eligible_rooms = self._get_eligible_rooms(mod, cr.student_count, data)
        if not eligible_rooms:
            return {
                'sessions': 0,
                'conflict': f"No eligible classroom for {mod.code} in {cr.cohort_label}",
                'next_day': next_available_day + dur_days,
            }

        # Try combinations of lecturers (prefer top-ranked ones)
        for team_combo in combinations(qualified[:min(len(qualified), 8)], team_size):
            team_ids = [t[0] for t in team_combo]

            # Compute earliest start considering all team members
            earliest = next_available_day
            max_wind_days = 0
            for lid in team_ids:
                lec = data['lecturers_by_id'][lid]
                prep = max(1, math.ceil(lec.prep_time_hours / SLOTS_PER_DAY))
                wind = max(1, math.ceil(lec.wind_down_hours / SLOTS_PER_DAY))
                max_wind_days = max(max_wind_days, wind)
                if lec_last_end[lid] >= 0:
                    earliest = max(earliest, lec_last_end[lid] + prep)

            for room in eligible_rooms:
                start_day = self._find_free_block_multi(
                    earliest, dur_days, run_end, team_ids, room.id,
                    lec_occupied, room_occupied,
                    data['lec_unavail'], data['room_unavail'],
                )
                if start_day is None:
                    continue

                # Primary lecturer is first, secondary is second
                primary_id = team_ids[0]
                secondary_id = team_ids[1] if team_size >= 2 else None

                count = self._emit_sessions(
                    cr.id, mod, primary_id, secondary_id, room.id, start_day, dur_days,
                    data['year_start_date'], lec_occupied, room_occupied,
                    extra_lec_ids=team_ids[2:],
                )

                for lid in team_ids:
                    lec_total_hours[lid] += mod.duration_hours
                    lec_last_end[lid] = start_day + dur_days

                return {
                    'sessions': count,
                    'conflict': None,
                    'next_day': start_day + dur_days + max_wind_days,
                }

        return {
            'sessions': 0,
            'conflict': f"Could not schedule team-taught {mod.code} in {cr.cohort_label}",
            'next_day': next_available_day + dur_days,
        }

    # ------------------------------------------------------------------ #
    #  Split / handover: divide module hours between N lecturers
    # ------------------------------------------------------------------ #

    def _schedule_split(self, mod, cr, next_available_day, run_end, data,
                        lec_occupied, room_occupied, lec_total_hours, lec_last_end):
        split_count = max(2, getattr(mod, 'split_count', 2) or 2)
        total_hours = mod.duration_hours
        min_seg = getattr(mod, 'min_segment_hours', None)

        # Divide hours as evenly as possible
        base_hours = total_hours // split_count
        remainder = total_hours % split_count
        segments = []
        for i in range(split_count):
            seg_hours = base_hours + (1 if i < remainder else 0)
            if min_seg and seg_hours < min_seg and total_hours >= min_seg * split_count:
                seg_hours = min_seg
            segments.append(seg_hours)

        qualified = self._get_qualified_lecturers(mod.id, data, lec_total_hours)
        if len(qualified) < split_count:
            return {
                'sessions': 0,
                'conflict': f"Need {split_count} lecturers for split {mod.code}, only {len(qualified)} qualified",
                'next_day': next_available_day + duration_hours_to_days(total_hours),
            }

        eligible_rooms = self._get_eligible_rooms(mod, cr.student_count, data)
        if not eligible_rooms:
            return {
                'sessions': 0,
                'conflict': f"No eligible classroom for {mod.code} in {cr.cohort_label}",
                'next_day': next_available_day + duration_hours_to_days(total_hours),
            }

        total_sessions = 0
        used_lecturers = set()
        current_day = next_available_day
        last_wind_days = 0

        for seg_idx, seg_hours in enumerate(segments):
            seg_days = duration_hours_to_days(seg_hours)

            # Pick the best lecturer not yet used in another segment
            scheduled_seg = False
            for lec_id, lec_prof in qualified:
                if lec_id in used_lecturers:
                    continue
                lec = data['lecturers_by_id'][lec_id]
                prep_days = max(1, math.ceil(lec.prep_time_hours / SLOTS_PER_DAY))
                wind_days = max(1, math.ceil(lec.wind_down_hours / SLOTS_PER_DAY))

                earliest = current_day
                if lec_last_end[lec_id] >= 0:
                    earliest = max(earliest, lec_last_end[lec_id] + prep_days)

                for room in eligible_rooms:
                    start_day = self._find_free_block(
                        earliest, seg_days, run_end,
                        lec_id, room.id,
                        lec_occupied, room_occupied,
                        data['lec_unavail'], data['room_unavail'],
                    )
                    if start_day is None:
                        continue

                    count = self._emit_sessions(
                        cr.id, mod, lec_id, None, room.id, start_day, seg_days,
                        data['year_start_date'], lec_occupied, room_occupied,
                        segment=seg_idx + 1, override_hours=seg_hours,
                    )
                    total_sessions += count
                    lec_total_hours[lec_id] += seg_hours
                    lec_last_end[lec_id] = start_day + seg_days
                    used_lecturers.add(lec_id)
                    current_day = start_day + seg_days
                    last_wind_days = wind_days
                    scheduled_seg = True
                    break

                if scheduled_seg:
                    break

            if not scheduled_seg:
                return {
                    'sessions': total_sessions,
                    'conflict': f"Could not schedule segment {seg_idx+1} of split {mod.code} in {cr.cohort_label}",
                    'next_day': current_day + duration_hours_to_days(seg_hours),
                }

        return {
            'sessions': total_sessions,
            'conflict': None,
            'next_day': current_day + last_wind_days,
        }

    # ------------------------------------------------------------------ #
    #  Helper: emit ScheduledSession records for a block
    # ------------------------------------------------------------------ #

    def _emit_sessions(self, course_run_id, mod, lecturer_id, secondary_lecturer_id,
                       classroom_id, start_day, dur_days, year_start_date,
                       lec_occupied, room_occupied,
                       extra_lec_ids=None, segment=None, override_hours=None):
        remaining = override_hours if override_hours is not None else mod.duration_hours
        session_type = 'lab' if mod.requires_lab else 'lecture'
        count = 0

        for d in range(dur_days):
            day_idx = start_day + d
            session_date = day_index_to_date(day_idx, year_start_date)
            slots = min(remaining, SLOTS_PER_DAY)
            remaining -= slots

            sess = ScheduledSession(
                course_run_id=course_run_id,
                module_id=mod.id,
                lecturer_id=lecturer_id,
                secondary_lecturer_id=secondary_lecturer_id,
                classroom_id=classroom_id,
                date=session_date,
                start_slot=0,
                duration_slots=slots,
                session_type=session_type,
                is_proposal=True,
                split_segment=segment,
            )
            self.session.add(sess)
            count += 1

            lec_occupied[lecturer_id].add(day_idx)
            if secondary_lecturer_id:
                lec_occupied[secondary_lecturer_id].add(day_idx)
            if extra_lec_ids:
                for eid in extra_lec_ids:
                    lec_occupied[eid].add(day_idx)
            room_occupied[classroom_id].add(day_idx)

        return count

    # ------------------------------------------------------------------ #
    #  Data loading
    # ------------------------------------------------------------------ #

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
        quals_by_module = defaultdict(list)
        for q in quals:
            quals_by_module[q.module_id].append(
                (q.lecturer_id, q.proficiency_level, q.can_examine)
            )

        # Load module rules
        module_rules = session.query(ModuleRule).filter_by(enabled=True).all()
        rules_by_module = defaultdict(list)
        for r in module_rules:
            rules_by_module[r.module_id].append(r)

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
            'module_rules': rules_by_module,
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
        rooms.sort(key=lambda r: r.capacity)
        return rooms

    def _find_free_block(self, earliest, dur_days, latest_end,
                         lec_id, room_id,
                         lec_occupied, room_occupied,
                         lec_unavail, room_unavail):
        """Find the earliest contiguous block of dur_days free days for one lecturer."""
        max_day = latest_end - dur_days + 1
        day = earliest

        while day <= max_day:
            block_ok = True
            for d in range(dur_days):
                dd = day + d
                if dd in lec_occupied[lec_id]:
                    day = dd + 1; block_ok = False; break
                if dd in room_occupied[room_id]:
                    day = dd + 1; block_ok = False; break
                if dd in lec_unavail.get(lec_id, set()):
                    day = dd + 1; block_ok = False; break
                if dd in room_unavail.get(room_id, set()):
                    day = dd + 1; block_ok = False; break
            if block_ok:
                return day
        return None

    def _find_free_block_multi(self, earliest, dur_days, latest_end,
                               lec_ids, room_id,
                               lec_occupied, room_occupied,
                               lec_unavail, room_unavail):
        """Find the earliest contiguous block where ALL lecturers AND the room are free."""
        max_day = latest_end - dur_days + 1
        day = earliest

        while day <= max_day:
            block_ok = True
            for d in range(dur_days):
                dd = day + d
                if dd in room_occupied[room_id]:
                    day = dd + 1; block_ok = False; break
                if dd in room_unavail.get(room_id, set()):
                    day = dd + 1; block_ok = False; break
                for lid in lec_ids:
                    if dd in lec_occupied[lid]:
                        day = dd + 1; block_ok = False; break
                    if dd in lec_unavail.get(lid, set()):
                        day = dd + 1; block_ok = False; break
                if not block_ok:
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

            quals = data['quals_by_module'].get(resit.module_id, [])
            for lec_id, prof, can_exam in quals:
                if not can_exam:
                    continue
                if teacher_cannot_examine and lec_id == resit.original_lecturer_id:
                    continue

                exam_days = max(1, math.ceil(
                    (mod.exam_duration_hours or 3) / SLOTS_PER_DAY
                ))

                try:
                    target_day = date_to_day_index(
                        resit.required_by_date, data['year_start_date']
                    )
                except ValueError:
                    continue

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
