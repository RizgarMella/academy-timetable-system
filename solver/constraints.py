"""Hard constraint functions for the CP-SAT timetable solver.

Each function takes (model, variables, data) and adds constraints to the
CP-SAT model. ``variables`` and ``data`` are dicts built by the engine.

Variables dict keys:
    start_day[(module_id, course_run_id)]  - IntVar: weekday index the block starts
    lecturer_assign[(module_id, course_run_id, lecturer_id)] - BoolVar
    classroom_assign[(module_id, course_run_id, classroom_id)] - BoolVar
    duration_days[(module_id, course_run_id)] - int constant (ceil(hours/8))

Data dict keys:
    course_runs      - list of CourseRun ORM objects
    modules_by_run   - {course_run_id: [Module, ...] ordered by sequence_order}
    lecturers         - list of Lecturer ORM objects
    classrooms        - list of Classroom ORM objects
    qualifications    - {(lecturer_id, module_id): LecturerQualification}
    resits            - list of Resit ORM objects
    rules             - {key: Rule}
    year_start_date   - date
    run_start_day     - {course_run_id: int}  (day index of planned_start_date)
    run_end_day       - {course_run_id: int}   (day index of planned_end_date)
    total_weekdays    - int  (total weekdays in the academic year)
"""

from ortools.sat.python import cp_model

from solver.utils import SLOTS_PER_DAY, DAYS_PER_WEEK, get_week_number


# ---------------------------------------------------------------------------
# 1. Module sequencing within a course run
# ---------------------------------------------------------------------------

def add_module_sequencing(model, variables, data):
    """Modules in a course run must follow their sequence_order.

    Module m+1 cannot start until module m has finished its block of days.
    """
    start_day = variables["start_day"]
    dur_days = variables["duration_days"]

    for cr in data["course_runs"]:
        modules = data["modules_by_run"].get(cr.id, [])
        for i in range(len(modules) - 1):
            m_cur = modules[i]
            m_next = modules[i + 1]
            key_cur = (m_cur.id, cr.id)
            key_next = (m_next.id, cr.id)
            # next module starts on or after the day the current module ends
            model.Add(
                start_day[key_next] >= start_day[key_cur] + dur_days[key_cur]
            )


# ---------------------------------------------------------------------------
# 2. Lecturer assignment - exactly one qualified lecturer per module delivery
# ---------------------------------------------------------------------------

def add_lecturer_assignment(model, variables, data):
    """Exactly one lecturer is assigned to each (module, course_run).

    Only lecturers who hold a qualification for the module may be assigned.
    """
    lec_assign = variables["lecturer_assign"]

    for cr in data["course_runs"]:
        for mod in data["modules_by_run"].get(cr.id, []):
            qualified_vars = []
            for lec in data["lecturers"]:
                key = (mod.id, cr.id, lec.id)
                if key in lec_assign:
                    qualified_vars.append(lec_assign[key])
            if qualified_vars:
                model.AddExactlyOne(qualified_vars)
            else:
                # No qualified lecturer exists -- model is infeasible
                model.AddBoolOr([])  # always false -> infeasible


# ---------------------------------------------------------------------------
# 3. No lecturer overlap -- a lecturer cannot teach two blocks on the same day
# ---------------------------------------------------------------------------

def add_no_lecturer_overlap(model, variables, data):
    """A lecturer cannot be teaching two different module blocks on the same day.

    For every pair of (module, course_run) items that could share a lecturer,
    if the lecturer IS assigned to both, their day ranges must not overlap.
    """
    start_day = variables["start_day"]
    dur_days = variables["duration_days"]
    lec_assign = variables["lecturer_assign"]

    # Collect all (mod_id, cr_id) pairs each lecturer COULD teach
    lec_items = {}  # lecturer_id -> [(mod_id, cr_id), ...]
    for (mod_id, cr_id, lec_id) in lec_assign:
        lec_items.setdefault(lec_id, []).append((mod_id, cr_id))

    for lec_id, items in lec_items.items():
        for i in range(len(items)):
            for j in range(i + 1, len(items)):
                key_a = items[i]
                key_b = items[j]
                assign_a = lec_assign[(*key_a, lec_id)]
                assign_b = lec_assign[(*key_b, lec_id)]

                dur_a = dur_days[key_a]
                dur_b = dur_days[key_b]

                # If both assigned, blocks must not overlap:
                #   start_a + dur_a <= start_b  OR  start_b + dur_b <= start_a
                # Encode with a helper bool: if both_assigned then no-overlap
                both = model.NewBoolVar(
                    f"both_lec{lec_id}_{'_'.join(str(x) for x in key_a)}_"
                    f"{'_'.join(str(x) for x in key_b)}"
                )
                model.AddBoolAnd([assign_a, assign_b]).OnlyEnforceIf(both)
                model.AddBoolOr([assign_a.Not(), assign_b.Not()]).OnlyEnforceIf(
                    both.Not()
                )

                # When both assigned, enforce non-overlap via intervals
                a_before_b = model.NewBoolVar(
                    f"a_before_b_lec{lec_id}_"
                    f"{'_'.join(str(x) for x in key_a)}_"
                    f"{'_'.join(str(x) for x in key_b)}"
                )
                model.Add(
                    start_day[key_a] + dur_a <= start_day[key_b]
                ).OnlyEnforceIf([both, a_before_b])
                model.Add(
                    start_day[key_b] + dur_b <= start_day[key_a]
                ).OnlyEnforceIf([both, a_before_b.Not()])


# ---------------------------------------------------------------------------
# 4. No classroom overlap
# ---------------------------------------------------------------------------

def add_no_classroom_overlap(model, variables, data):
    """A classroom cannot host two module blocks on the same day.

    Uses the same pairwise non-overlap approach as lecturer overlap.
    """
    start_day = variables["start_day"]
    dur_days = variables["duration_days"]
    room_assign = variables["classroom_assign"]

    room_items = {}  # classroom_id -> [(mod_id, cr_id), ...]
    for (mod_id, cr_id, room_id) in room_assign:
        room_items.setdefault(room_id, []).append((mod_id, cr_id))

    for room_id, items in room_items.items():
        for i in range(len(items)):
            for j in range(i + 1, len(items)):
                key_a = items[i]
                key_b = items[j]
                assign_a = room_assign[(*key_a, room_id)]
                assign_b = room_assign[(*key_b, room_id)]

                dur_a = dur_days[key_a]
                dur_b = dur_days[key_b]

                both = model.NewBoolVar(
                    f"both_room{room_id}_{'_'.join(str(x) for x in key_a)}_"
                    f"{'_'.join(str(x) for x in key_b)}"
                )
                model.AddBoolAnd([assign_a, assign_b]).OnlyEnforceIf(both)
                model.AddBoolOr(
                    [assign_a.Not(), assign_b.Not()]
                ).OnlyEnforceIf(both.Not())

                a_before_b = model.NewBoolVar(
                    f"a_before_b_room{room_id}_"
                    f"{'_'.join(str(x) for x in key_a)}_"
                    f"{'_'.join(str(x) for x in key_b)}"
                )
                model.Add(
                    start_day[key_a] + dur_a <= start_day[key_b]
                ).OnlyEnforceIf([both, a_before_b])
                model.Add(
                    start_day[key_b] + dur_b <= start_day[key_a]
                ).OnlyEnforceIf([both, a_before_b.Not()])


# ---------------------------------------------------------------------------
# 5. Classroom capacity and lab requirements
# ---------------------------------------------------------------------------

def add_classroom_capacity(model, variables, data):
    """Room capacity >= student_count, and lab modules need lab rooms.

    Exactly one classroom must be assigned per (module, course_run).
    Rooms that are too small or lack required lab equipment are excluded during
    variable creation, so here we just enforce exactly-one selection.
    """
    room_assign = variables["classroom_assign"]

    for cr in data["course_runs"]:
        for mod in data["modules_by_run"].get(cr.id, []):
            eligible_vars = []
            for room in data["classrooms"]:
                key = (mod.id, cr.id, room.id)
                if key in room_assign:
                    eligible_vars.append(room_assign[key])
            if eligible_vars:
                model.AddExactlyOne(eligible_vars)
            else:
                model.AddBoolOr([])  # infeasible


# ---------------------------------------------------------------------------
# 6. Prep time -- gap before a lecturer starts a new module
# ---------------------------------------------------------------------------

def add_prep_time(model, variables, data):
    """Enforce a gap of prep_time_hours (in day slots) before a lecturer
    starts teaching a different module.

    If lecturer L teaches module A (ending at start_A + dur_A) and then
    module B, there must be at least ceil(prep_time_hours / SLOTS_PER_DAY)
    days gap between end of A and start of B.
    """
    import math
    start_day = variables["start_day"]
    dur_days = variables["duration_days"]
    lec_assign = variables["lecturer_assign"]

    lec_items = {}
    for (mod_id, cr_id, lec_id) in lec_assign:
        lec_items.setdefault(lec_id, []).append((mod_id, cr_id))

    lec_prep = {lec.id: lec.prep_time_hours for lec in data["lecturers"]}

    for lec_id, items in lec_items.items():
        prep_days = max(1, math.ceil(lec_prep.get(lec_id, 0) / SLOTS_PER_DAY))
        if prep_days <= 0:
            continue
        for i in range(len(items)):
            for j in range(len(items)):
                if i == j:
                    continue
                key_a = items[i]
                key_b = items[j]
                assign_a = lec_assign[(*key_a, lec_id)]
                assign_b = lec_assign[(*key_b, lec_id)]

                # If both assigned AND a ends before b starts,
                # then start_b >= end_a + prep_days
                both = model.NewBoolVar(
                    f"prep_both_l{lec_id}_"
                    f"{'_'.join(str(x) for x in key_a)}_"
                    f"{'_'.join(str(x) for x in key_b)}"
                )
                model.AddBoolAnd([assign_a, assign_b]).OnlyEnforceIf(both)
                model.AddBoolOr(
                    [assign_a.Not(), assign_b.Not()]
                ).OnlyEnforceIf(both.Not())

                a_before_b = model.NewBoolVar(
                    f"prep_ord_l{lec_id}_"
                    f"{'_'.join(str(x) for x in key_a)}_"
                    f"{'_'.join(str(x) for x in key_b)}"
                )
                end_a = dur_days[key_a]
                model.Add(
                    start_day[key_a] + end_a <= start_day[key_b]
                ).OnlyEnforceIf([both, a_before_b])
                # When a is before b, enforce prep gap
                model.Add(
                    start_day[key_b] >= start_day[key_a] + end_a + prep_days
                ).OnlyEnforceIf([both, a_before_b])

                # The opposite order is handled when (j, i) is processed
                model.Add(
                    start_day[key_b] + dur_days[key_b] <= start_day[key_a]
                ).OnlyEnforceIf([both, a_before_b.Not()])


# ---------------------------------------------------------------------------
# 7. Wind-down time -- gap after module block ends (for marking)
# ---------------------------------------------------------------------------

def add_wind_down_time(model, variables, data):
    """After a lecturer finishes a module block, there is a wind-down period
    (wind_down_hours) before they can start the next.

    This is very similar to prep time but uses wind_down_hours from the
    Lecturer model. We combine it with the existing prep time by taking
    the maximum of the two gaps when both apply.

    In practice this constraint is enforced as:
        start_b >= end_a + max(prep_days, wind_down_days)
    Since prep_time already does the ordering work, here we just bump the
    gap up if wind_down is larger. To avoid double-constraining, this
    function replaces the prep_time gap with the larger of the two.
    """
    # This is handled jointly with prep_time in a combined manner.
    # We implement it as an additive constraint: the gap must be at least
    # wind_down_days. If prep_time was already applied, the solver takes the
    # tightest (largest) of the two constraints automatically.
    import math
    start_day = variables["start_day"]
    dur_days = variables["duration_days"]
    lec_assign = variables["lecturer_assign"]

    lec_items = {}
    for (mod_id, cr_id, lec_id) in lec_assign:
        lec_items.setdefault(lec_id, []).append((mod_id, cr_id))

    lec_wd = {lec.id: lec.wind_down_hours for lec in data["lecturers"]}

    for lec_id, items in lec_items.items():
        wd_days = max(1, math.ceil(lec_wd.get(lec_id, 0) / SLOTS_PER_DAY))
        if wd_days <= 0:
            continue
        for i in range(len(items)):
            for j in range(i + 1, len(items)):
                key_a = items[i]
                key_b = items[j]
                assign_a = lec_assign[(*key_a, lec_id)]
                assign_b = lec_assign[(*key_b, lec_id)]

                both = model.NewBoolVar(
                    f"wd_both_l{lec_id}_"
                    f"{'_'.join(str(x) for x in key_a)}_"
                    f"{'_'.join(str(x) for x in key_b)}"
                )
                model.AddBoolAnd([assign_a, assign_b]).OnlyEnforceIf(both)
                model.AddBoolOr(
                    [assign_a.Not(), assign_b.Not()]
                ).OnlyEnforceIf(both.Not())

                a_before_b = model.NewBoolVar(
                    f"wd_ord_l{lec_id}_"
                    f"{'_'.join(str(x) for x in key_a)}_"
                    f"{'_'.join(str(x) for x in key_b)}"
                )
                # a before b
                model.Add(
                    start_day[key_a] + dur_days[key_a] <= start_day[key_b]
                ).OnlyEnforceIf([both, a_before_b])
                model.Add(
                    start_day[key_b]
                    >= start_day[key_a] + dur_days[key_a] + wd_days
                ).OnlyEnforceIf([both, a_before_b])
                # b before a
                model.Add(
                    start_day[key_b] + dur_days[key_b] <= start_day[key_a]
                ).OnlyEnforceIf([both, a_before_b.Not()])
                model.Add(
                    start_day[key_a]
                    >= start_day[key_b] + dur_days[key_b] + wd_days
                ).OnlyEnforceIf([both, a_before_b.Not()])


# ---------------------------------------------------------------------------
# 8. Max weekly teaching hours per lecturer
# ---------------------------------------------------------------------------

def add_max_weekly_hours(model, variables, data):
    """A lecturer's total teaching days in any given week must not exceed
    their max_weekly_hours / SLOTS_PER_DAY.

    Uses CP-SAT cumulative constraint with weekly capacity. For each
    (module, course_run) that a lecturer may teach, we create an optional
    interval. Then for each week boundary we enforce that the number of
    overlapping intervals does not exceed the lecturer's weekly day limit.

    To keep the model tractable we use AddCumulative per lecturer with
    a capacity of max_days_per_week, applied per-week by creating
    per-week sub-intervals.
    """
    import math
    start_day = variables["start_day"]
    dur_days = variables["duration_days"]
    lec_assign = variables["lecturer_assign"]
    total_weekdays = data["total_weekdays"]

    num_weeks = max(1, (total_weekdays + DAYS_PER_WEEK - 1) // DAYS_PER_WEEK)

    lec_items = {}
    for (mod_id, cr_id, lec_id) in lec_assign:
        lec_items.setdefault(lec_id, []).append((mod_id, cr_id))

    for lec in data["lecturers"]:
        max_days_per_week = max(
            1, math.floor(lec.max_weekly_hours / SLOTS_PER_DAY)
        )
        items = lec_items.get(lec.id, [])
        if not items:
            continue

        for w in range(num_weeks):
            week_start = w * DAYS_PER_WEEK
            week_end = week_start + DAYS_PER_WEEK  # exclusive

            overlap_vars = []
            for key in items:
                mod_id, cr_id = key
                assign_var = lec_assign[(*key, lec.id)]
                d = dur_days[key]

                # Compute overlap of block [start, start+d) with [week_start, week_end)
                # overlap = max(0, min(start+d, week_end) - max(start, week_start))
                # We create an IntVar for the overlap, conditional on assignment.
                overlap = model.NewIntVar(
                    0, DAYS_PER_WEEK,
                    f"wkovlp_l{lec.id}_m{mod_id}_cr{cr_id}_w{w}"
                )

                # Auxiliary vars for the min/max computations
                # a = min(start+d, week_end) => use AddMinEquality
                # b = max(start, week_start) => use AddMaxEquality
                a = model.NewIntVar(
                    0, total_weekdays,
                    f"wka_l{lec.id}_m{mod_id}_cr{cr_id}_w{w}"
                )
                b = model.NewIntVar(
                    0, total_weekdays,
                    f"wkb_l{lec.id}_m{mod_id}_cr{cr_id}_w{w}"
                )
                end_expr = model.NewIntVar(
                    0, total_weekdays,
                    f"wkend_l{lec.id}_m{mod_id}_cr{cr_id}_w{w}"
                )
                model.Add(end_expr == start_day[key] + d)
                model.AddMinEquality(a, [end_expr, model.NewConstant(week_end)])
                model.AddMaxEquality(b, [start_day[key], model.NewConstant(week_start)])

                # raw_overlap = a - b (can be negative => no overlap)
                raw_overlap = model.NewIntVar(
                    -total_weekdays, DAYS_PER_WEEK,
                    f"wkraw_l{lec.id}_m{mod_id}_cr{cr_id}_w{w}"
                )
                model.Add(raw_overlap == a - b)
                model.AddMaxEquality(overlap, [raw_overlap, model.NewConstant(0)])

                # Only count overlap if lecturer is assigned
                counted = model.NewIntVar(
                    0, DAYS_PER_WEEK,
                    f"wkcnt_l{lec.id}_m{mod_id}_cr{cr_id}_w{w}"
                )
                model.Add(counted == overlap).OnlyEnforceIf(assign_var)
                model.Add(counted == 0).OnlyEnforceIf(assign_var.Not())
                overlap_vars.append(counted)

            if overlap_vars:
                model.Add(sum(overlap_vars) <= max_days_per_week)


# ---------------------------------------------------------------------------
# 9. Teacher cannot examine (for resits)
# ---------------------------------------------------------------------------

def add_teacher_cannot_examine(model, variables, data):
    """For resit exams, the examiner must not be the original teacher.

    This is enforced by preventing the original_lecturer from being assigned
    as the examiner in the resit scheduling. If the resit has already been
    given an examiner_id in the DB, this constraint is informational. For
    solver-assigned resit examiners, we block the original lecturer.
    """
    lec_assign = variables.get("resit_examiner_assign", {})
    for resit in data.get("resits", []):
        key = (resit.module_id, resit.course_run_id, resit.original_lecturer_id)
        if key in lec_assign:
            model.Add(lec_assign[key] == 0)


# ---------------------------------------------------------------------------
# 10. Date window -- all sessions within course run planned dates
# ---------------------------------------------------------------------------

def add_date_window(model, variables, data):
    """Every module block must start and end within the course run's planned
    start and end dates.
    """
    start_day = variables["start_day"]
    dur_days = variables["duration_days"]

    for cr in data["course_runs"]:
        run_start = data["run_start_day"][cr.id]
        run_end = data["run_end_day"][cr.id]
        for mod in data["modules_by_run"].get(cr.id, []):
            key = (mod.id, cr.id)
            model.Add(start_day[key] >= run_start)
            # Block must finish within the window
            model.Add(start_day[key] + dur_days[key] - 1 <= run_end)
