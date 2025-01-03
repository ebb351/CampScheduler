import pandas as pd

def parse_schedule(schedule):
    """
    Parse the generated schedule into a Pandas DataFrame for easier analysis.
    """
    return pd.DataFrame(schedule)

def test_staff_non_overlap(schedule_df):
    """
    Test that no staff member is assigned to more than one activity per time slot.
    """
    violations = []
    for time_slot in schedule_df['time_slot'].unique():
        time_slot_df = schedule_df[schedule_df['time_slot'] == time_slot]
        staff_counts = time_slot_df['staff'].value_counts()
        overlapping_staff = staff_counts[staff_counts > 1]
        if not overlapping_staff.empty:
            violations.append((time_slot, overlapping_staff))
    return violations

def test_location_non_overlap(schedule_df):
    """
    Test that no location is hosting more than one activity per time slot.
    """
    violations = []
    for time_slot in schedule_df['time_slot'].unique():
        time_slot_df = schedule_df[schedule_df['time_slot'] == time_slot]
        location_counts = time_slot_df['location'].value_counts()
        overlapping_locations = location_counts[location_counts > 1]
        if not overlapping_locations.empty:
            violations.append((time_slot, overlapping_locations))
    return violations

def test_activity_exclusivity(schedule_df):
    """
    Test that each activity is only assigned to one group per time slot.
    """
    violations = []
    for time_slot in schedule_df['time_slot'].unique():
        time_slot_df = schedule_df[schedule_df['time_slot'] == time_slot]
        activity_counts = time_slot_df['activity'].value_counts()
        overlapping_activities = activity_counts[activity_counts > 1]
        if not overlapping_activities.empty:
            violations.append((time_slot, overlapping_activities))
    return violations

def test_group_activity_count(schedule_df, group_ids):
    """
    Test that each group has 3-4 activities per time slot.
    """
    violations = []
    for group in group_ids:
        group_df = schedule_df[schedule_df['group'] == group]
        for time_slot in group_df['time_slot'].unique():
            time_slot_df = group_df[group_df['time_slot'] == time_slot]
            activity_count = len(time_slot_df)
            if activity_count < 3 or activity_count > 4:
                violations.append((group, time_slot, activity_count))
    return violations

def test_location_activity_match(schedule_df, loc_options_df):
    """
    Test that each activity is assigned to a valid location from locOptions
    """
    violations = []

    # Create a set of valid (activityName, locName) pairs from locOptions
    valid_pairs = set(
        zip(loc_options_df["activityName"], loc_options_df["locName"])
    )

    # Check each row in the schedule
    for _, row in schedule_df.iterrows():
        activity_name = row["activity"]
        location_name = row["location"]

        # Check if the (activityName, locName) pair is valid
        if (activity_name, location_name) not in valid_pairs:
            violations.append({
                "activity": activity_name,
                "location": location_name,
                "time_slot": row["time_slot"],
                "group": row["group"]
            })
    return violations

def test_staff_availability(schedule, staff_unavailable_time_slots, staff_df):
    """
    Test to ensure no staff assigned to activities during unavailable time slots
    :param schedule_df: List of scheduled activities, each containing:
                     {"activity": ..., "staff": ..., "location": ..., "time_slot": ..., "group": ...}
    :param staff_unavailable_time_slots: Dictionary mapping staffID to a list of unavailable time slots
    :param staff_df: DataFrame containing staff information (staffID, staffName)
    """
    violations = []
    for entry in schedule:
        # Extract relevant information from schedule entry
        staff_name = entry["staff"]
        time_slot = entry["time_slot"]

        # Get staffID from staffName
        staff_id = staff_df.loc[staff_df["staffName"] == staff_name, "staffID"].values[0]

        # Check if the staff member is unavailable during this time slot
        if staff_id in staff_unavailable_time_slots:
            if time_slot in staff_unavailable_time_slots[staff_id]:
                violations.append(entry)
    return violations

def test_unfulfilled_leads_on_schedule(schedule, unfulfilled_leads_details, staff_ids, x, solver):
    """
    Test to ensure no unfulfilled leads are assigned to scheduled activities.
    """
    violations = []

    for dummy_var, j, k, g in unfulfilled_leads_details:
        if solver.Value(dummy_var) == 1:
            # Check if the activity j is scheduled for group g at time slot k
            activity_scheduled = any(
                solver.Value(x[i, j, k, g]) == 1 for i in staff_ids
            )
            if activity_scheduled:
                violations.append({
                    "activity_id": j,
                    "time_slot": k,
                    "group_id": g,
                    "dummy_var": solver.Value(dummy_var)
                })
    return violations


def run_tests(schedule, group_ids, location_options_df, staff_unavailable_time_slots, staff_df, unfulfilled_leads_details, x, solver):
    """
    Run all test functions on the generated schedule.
    """
    schedule_df = parse_schedule(schedule)

    print("Running Tests...")
    staff_overlap_violations = test_staff_non_overlap(schedule_df)
    staff_availability_violations = test_staff_availability(schedule, staff_unavailable_time_slots, staff_df)
    location_violations = test_location_non_overlap(schedule_df)
    location_activity_violations = test_location_activity_match(schedule_df, location_options_df)
    activity_violations = test_activity_exclusivity(schedule_df)
    group_violations = test_group_activity_count(schedule_df, group_ids)
    unfulfilled_leads_violations = test_unfulfilled_leads_on_schedule(schedule, unfulfilled_leads_details, staff_df["staffID"].tolist(), x, solver)

    print("Test Results:")
    if staff_overlap_violations:
        print("Staff Non-Overlap Violations:", staff_overlap_violations)
    else:
        print("Staff Non-Overlap: PASSED")

    if staff_availability_violations:
        print("Staff Availability Violations:", staff_availability_violations)
    else:
        print("Staff Availability: PASSED")

    if location_violations:
        print("Location Non-Overlap Violations:", location_violations)
    else:
        print("Location Non-Overlap: PASSED")

    if location_activity_violations:
        print("Location Activity Match Violations:", location_activity_violations)
    else:
        print("Location Activity Match: PASSED")

    if activity_violations:
        print("Activity Exclusivity Violations:", activity_violations)
    else:
        print("Activity Exclusivity: PASSED")

    if group_violations:
        print("Group Activity Count Violations:", group_violations)
    else:
        print("Group Activity Count: PASSED")

    if unfulfilled_leads_violations:
        print("Unfulfilled Leads Violations:", unfulfilled_leads_violations)
    else:
        print("Unfulfilled Leads: PASSED")
