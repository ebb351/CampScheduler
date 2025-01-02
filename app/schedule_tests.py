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

def run_tests(schedule, group_ids):
    """
    Run all test functions on the generated schedule.
    """
    schedule_df = parse_schedule(schedule)

    print("Running Tests...")
    staff_violations = test_staff_non_overlap(schedule_df)
    location_violations = test_location_non_overlap(schedule_df)
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

    if activity_violations:
        print("Activity Exclusivity Violations:", activity_violations)
    else:
        print("Activity Exclusivity: PASSED")

    if group_violations:
        print("Group Activity Count Violations:", group_violations)
    else:
        print("Group Activity Count: PASSED")
