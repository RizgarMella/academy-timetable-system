"""Soft objective functions for the CP-SAT timetable solver.

Each function takes (model, variables, data) and returns a list of
(expression, weight) tuples to be minimized. The engine sums all weighted
terms into a single objective.
"""

from ortools.sat.python import cp_model

from solver.utils import SLOTS_PER_DAY


def add_load_balancing(model, variables, data):
    """Minimize the spread (max - min) of total teaching days across lecturers.

    Returns a list of [(term, weight)] to add to the objective.
    """
    lec_assign = variables["lecturer_assign"]
    dur_days = variables["duration_days"]

    lec_items = {}
    for (mod_id, cr_id, lec_id) in lec_assign:
        lec_items.setdefault(lec_id, []).append((mod_id, cr_id))

    if len(lec_items) < 2:
        return []

    total_days_max = sum(dur_days.values())

    # For each lecturer, compute total assigned days
    lec_totals = {}
    for lec_id, items in lec_items.items():
        terms = []
        for key in items:
            # dur_days[key] * lec_assign[(key[0], key[1], lec_id)]
            prod = model.NewIntVar(
                0, total_days_max, f"load_prod_l{lec_id}_m{key[0]}_cr{key[1]}"
            )
            assign_var = lec_assign[(key[0], key[1], lec_id)]
            model.Add(prod == dur_days[key]).OnlyEnforceIf(assign_var)
            model.Add(prod == 0).OnlyEnforceIf(assign_var.Not())
            terms.append(prod)

        total = model.NewIntVar(0, total_days_max, f"load_total_l{lec_id}")
        model.Add(total == sum(terms))
        lec_totals[lec_id] = total

    totals_list = list(lec_totals.values())

    max_load = model.NewIntVar(0, total_days_max, "load_max")
    min_load = model.NewIntVar(0, total_days_max, "load_min")
    model.AddMaxEquality(max_load, totals_list)
    model.AddMinEquality(min_load, totals_list)

    spread = model.NewIntVar(0, total_days_max, "load_spread")
    model.Add(spread == max_load - min_load)

    return [(spread, 5)]


def add_qualification_preference(model, variables, data):
    """Prefer primary-qualified lecturers over secondary and emergency.

    Penalties: primary=0, secondary=10, emergency=100 per assignment.
    Returns [(term, weight)].
    """
    lec_assign = variables["lecturer_assign"]
    qualifications = data["qualifications"]

    penalty_map = {
        "primary": 0,
        "secondary": 10,
        "emergency": 100,
    }

    penalty_terms = []
    for (mod_id, cr_id, lec_id), var in lec_assign.items():
        qual = qualifications.get((lec_id, mod_id))
        if qual is None:
            continue
        penalty = penalty_map.get(qual.proficiency_level, 0)
        if penalty > 0:
            term = model.NewIntVar(
                0, penalty, f"qual_pen_l{lec_id}_m{mod_id}_cr{cr_id}"
            )
            model.Add(term == penalty).OnlyEnforceIf(var)
            model.Add(term == 0).OnlyEnforceIf(var.Not())
            penalty_terms.append(term)

    if not penalty_terms:
        return []

    total_penalty = model.NewIntVar(
        0, sum(penalty_map.get("emergency", 100) for _ in penalty_terms),
        "qual_total_penalty",
    )
    model.Add(total_penalty == sum(penalty_terms))
    return [(total_penalty, 1)]


def add_compact_scheduling(model, variables, data):
    """Minimize gaps between consecutive modules in a course run.

    For each pair of consecutive modules in a run, we penalize the gap
    (start_{m+1} - end_m) beyond the minimum required.
    Returns [(term, weight)].
    """
    start_day = variables["start_day"]
    dur_days = variables["duration_days"]
    total_weekdays = data["total_weekdays"]

    gap_terms = []
    for cr in data["course_runs"]:
        modules = data["modules_by_run"].get(cr.id, [])
        for i in range(len(modules) - 1):
            m_cur = modules[i]
            m_next = modules[i + 1]
            key_cur = (m_cur.id, cr.id)
            key_next = (m_next.id, cr.id)

            gap = model.NewIntVar(
                0, total_weekdays,
                f"gap_cr{cr.id}_m{m_cur.id}_to_m{m_next.id}",
            )
            model.Add(
                gap == start_day[key_next]
                - start_day[key_cur]
                - dur_days[key_cur]
            )
            gap_terms.append(gap)

    if not gap_terms:
        return []

    total_gap = model.NewIntVar(
        0, total_weekdays * len(gap_terms), "compact_total_gap"
    )
    model.Add(total_gap == sum(gap_terms))
    return [(total_gap, 2)]
