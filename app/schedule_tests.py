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

def run_tests(schedule, group_ids, location_options_df):
    """
    Run all test functions on the generated schedule.
    """
    schedule_df = parse_schedule(schedule)

    print("Running Tests...")
    staff_violations = test_staff_non_overlap(schedule_df)
    location_violations = test_location_non_overlap(schedule_df)
    location_activity_violations = test_location_activity_match(schedule_df, location_options_df)
    activity_violations = test_activity_exclusivity(schedule_df)
    group_violations = test_group_activity_count(schedule_df, group_ids)

    print("Test Results:")
    if staff_violations:
        print("Staff Non-Overlap Violations:", staff_violations)
    else:
        print("Staff Non-Overlap: PASSED")

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
