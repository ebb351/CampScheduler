def test_staff_non_overlap(schedule_df):
    """
    Each row now has (group, activity, time_slot, location, staff) with exactly one staff.
    We want: In any given time_slot, a staff member cannot appear on two different activities.
    """
    violations = []

    # Group by (time_slot, staff), then count the distinct (group, activity).
    grouped = schedule_df.groupby(["time_slot", "staff"], observed=False)

    for (ts, staff), sub_df in grouped:
        # sub_df has all rows where this staff is assigned in this timeslot
        # If staff is assigned to more than 1 distinct (group, activity) => violation
        distinct_acts = sub_df[["group", "activity"]].drop_duplicates()
        if len(distinct_acts) > 1:
            # Means staff is doing >1 unique activity in the same slot
            # We can store how many or which ones if we want:
            counts = distinct_acts.value_counts().to_dict()
            violations.append((ts, staff, counts))

    return violations

def test_location_non_overlap(schedule_df):
    """
    No location is hosting >1 distinct (group, activity) combos in the same time_slot.
    """
    violations = []

    # We'll group by (time_slot, location).
    # Then for each group, we gather distinct (group, activity) combos.
    grouped = schedule_df.groupby(["time_slot", "location"], observed=False)

    for (ts, loc), sub_df in grouped:
        # sub_df might have multiple staff rows for the same group/activity,
        # so just find unique (group, activity).
        distinct_assignments = sub_df[["group","activity"]].drop_duplicates()

        if len(distinct_assignments) > 1:
            # i.e. more than 1 distinct (group, activity) is using the same location
            # at this time slot => violation
            combos = distinct_assignments.value_counts().to_dict()
            violations.append((ts, loc, combos))

    return violations

def test_activity_exclusivity(schedule_df):
    """
    Each activity can only appear in one group per time_slot.
    """
    violations = []

    # Group by (time_slot, activity). Then see how many distinct groups are using that (activity, time_slot).
    grouped = schedule_df.groupby(["time_slot", "activity"], observed=False)

    for (ts, act), sub_df in grouped:
        distinct_groups = sub_df["group"].drop_duplicates()
        if len(distinct_groups) > 1:
            # That means multiple groups are using the same activity at once
            violations.append((ts, act, distinct_groups.tolist()))
    return violations


def test_group_activity_count_with_waterfront(schedule_df, group_ids, waterfront_schedule):
    """
    For each group, each time_slot:
      - If time_slot is in waterfront_schedule[g], we expect exactly 1 distinct activity: 'waterfront'
      - Otherwise, we expect 3-4 distinct activities
    """
    violations = []

    # Group by (group, time_slot)
    grouped = schedule_df.groupby(["group", "time_slot"], observed=False)
    for (grp, ts), sub_df in grouped:
        # sub_df is all rows for group=grp, time_slot=ts, each row = 1 staff
        distinct_acts = sub_df["activity"].drop_duplicates()

        if ts in waterfront_schedule[grp]:
            # This should be a "waterfront only" slot
            if len(distinct_acts) != 1 or "waterfront" not in distinct_acts.values:
                # e.g. either 0 or 2+ distinct activities, or no 'waterfront' activity
                violations.append({
                    "group": grp,
                    "time_slot": ts,
                    "msg": f"Expected exactly 1 activity='waterfront', found {list(distinct_acts)}"
                })
        else:
            # This is a normal slot => want 3-4 distinct activities
            act_count = len(distinct_acts)
            if act_count < 3 or act_count > 4:
                violations.append({
                    "group": grp,
                    "time_slot": ts,
                    "msg": f"Expected 3-4 activities, found {act_count}: {list(distinct_acts)}"
                })

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

def test_staff_availability(schedule_df, staff_unavailable_time_slots, staff_df):
    """
    Test to ensure no staff assigned to activities during unavailable time slots
    :param schedule_df: List of scheduled activities, each containing:
                     {"activity": ..., "staff": ..., "location": ..., "time_slot": ..., "group": ...}
    :param staff_unavailable_time_slots: Dictionary mapping staffID to a list of unavailable time slots
    :param staff_df: DataFrame containing staff information (staffID, staffName)
    """
    violations = []
    for _, row in schedule_df.iterrows():
        staff_name = row["staff"]
        time_slot = row["time_slot"]

        # staff_id is a Series of all staffIDs matching 'staff_name'
        sid_series = staff_df.loc[staff_df["staffName"] == staff_name, "staffID"]

        # If no staff matched or staff_name is invalid, skip
        if sid_series.empty:
            continue

        # Extract the first (or only) match as an integer
        staff_id = sid_series.iloc[0]

        # Now staff_id is a single integer, so you can do:
        if staff_id in staff_unavailable_time_slots:
            if time_slot in staff_unavailable_time_slots[staff_id]:
                violations.append({
                    "staff": staff_name,
                    "time_slot": time_slot
                })

    return violations

def test_mandatory_leads(schedule_df, leads_mapping, staff_df, activity_df):
    """
    Test to ensure each (time_slot, group, activity) combination 
    has at least one staff who can lead that activity.
    """
    violations = []

    # Create a mapping of activityName -> activityID
    activity_name_to_id = dict(zip(activity_df["activityName"], activity_df["activityID"]))
    staff_name_to_id    = dict(zip(staff_df["staffName"], staff_df["staffID"]))

    # leads_mapping is staffID -> list_of_activityIDs they can lead
    # Convert to a set for faster "in" checks:
    staff_lead_lookup = {
        sid: set(activities) for sid, activities in leads_mapping.items()
    }

    # Group by these three columns
    grouped = schedule_df.groupby(["time_slot", "group", "activity"], observed=False)

    for (ts, grp, act), sub_df in grouped:
        # sub_df has all rows for staff assigned to (ts, grp, act)
        # Check if at least one staff is a valid lead

        activity_id = activity_name_to_id[act]

        # Collect the staffIDs from sub_df
        staff_ids = []
        for staff_name in sub_df["staff"].unique():
            # get staff_id from staff_name
            sid_array = staff_df.loc[staff_df["staffName"] == staff_name, "staffID"]
            if not sid_array.empty:
                staff_ids.append(sid_array.values[0])

        # Now see if any of these staff_ids can lead activity_id
        can_lead = False
        for sid in staff_ids:
            # If activity_id is in staff_lead_lookup[sid], this staff can lead
            if activity_id in staff_lead_lookup.get(sid, set()):
                can_lead = True
                break

        # If no staff can lead, that is a violation
        if not can_lead:
            violations.append({
                "time_slot": ts,
                "group": grp,
                "activity": act,
                "message": "No qualified lead assigned."
            })

    return violations

def test_only_leads_and_assists(schedule_df, leads_mapping, assists_mapping, staff_df, activity_df):
    """
    Test to ensure each scheduled activity only has leads and assists staff assigned
    """
    violations = []

    # Create a mapping of activityName -> activityID
    activity_name_to_id = dict(zip(activity_df["activityName"], activity_df["activityID"]))

    # leads_mapping is staffID -> list_of_activityIDs they can lead
    # Convert to a set for faster "in" checks:
    staff_lead_lookup = {
        sid: set(activities) for sid, activities in leads_mapping.items()
    }
    # assists_mapping is staffID -> list_of_activityIDs they can assist
    # Convert to a set for faster "in" checks:
    staff_assists_lookup = {
        sid: set(activities) for sid, activities in assists_mapping.items()
    }

    for _, row in schedule_df.iterrows():
        staff_name = row["staff"]
        activity_name = row["activity"]
        time_slot = row["time_slot"]
        group_id = row["group"]

        # Get the staff_id from staff_name
        staff_id_series = staff_df.loc[staff_df["staffName"] == staff_name, "staffID"]
        if staff_id_series.empty:
            # If no matching staff found, skip or treat as a violation
            violations.append({
                "staff": staff_name,
                "activity": activity_name,
                "time_slot": time_slot,
                "group": group_id,
                "violation": "Staff name not found in staff_df"
            })
            continue
        staff_id = staff_id_series.iloc[0]

        # get the activity_id from activity_name
        activity_id = activity_name_to_id.get(activity_name, None)
        if activity_id is None:
            # If no matching activity found, skip or treat as a violation
            violations.append({
                "staff": staff_name,
                "activity": activity_name,
                "time_slot": time_slot,
                "group": group_id,
                "violation": "Activity name not found in activity_df"
            })
            continue

        # Now check if staff_id can either lead or assist this activity
        can_lead = activity_id in staff_lead_lookup.get(staff_id, set())
        can_assist = activity_id in staff_assists_lookup.get(staff_id, set())

        if not (can_lead or can_assist):
            violations.append({
                "staff": staff_name,
                "activity": activity_name,
                "time_slot": time_slot,
                "group": group_id,
                "violation": "Staff not qualified to lead or assist this activity"
            })

    return violations

def run_tests(schedule_df, group_ids, location_options_df, staff_unavailable_time_slots, staff_df, activity_df, leads_mapping, assists_mapping, waterfront_schedule):
    """
    Run all test functions on the generated schedule.
    """

    print("Running Tests...")
    staff_overlap_violations = test_staff_non_overlap(schedule_df)
    staff_availability_violations = test_staff_availability(schedule_df, staff_unavailable_time_slots, staff_df)
    location_violations = test_location_non_overlap(schedule_df)
    location_activity_violations = test_location_activity_match(schedule_df, location_options_df)
    activity_violations = test_activity_exclusivity(schedule_df)
    group_wf_violations = test_group_activity_count_with_waterfront(schedule_df, group_ids, waterfront_schedule)
    leads_violations = test_mandatory_leads(schedule_df, leads_mapping, staff_df, activity_df)
    no_leads_or_assists_violations = test_only_leads_and_assists(schedule_df, leads_mapping, assists_mapping, staff_df, activity_df)

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

    if leads_violations:
        print("Mandatory Leads Violations:", leads_violations)
    else:
        print("Mandatory Leads: PASSED")

    if no_leads_or_assists_violations:
        print("Only Leads/Assists Violations:", no_leads_or_assists_violations)
    else:
        print("Only Leads/Assists: PASSED")
    if group_wf_violations:
        print("Group Activity/Waterfront Violations:", group_wf_violations)
    else:
        print("Group Activity/Waterfront Count: PASSED")