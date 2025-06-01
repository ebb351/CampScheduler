import pandas as pd

def test_staff_non_overlap(schedule_df):
    """
    Tests that each staff member is not assigned to multiple activities in the same time slot.
    
    A fundamental constraint in the schedule is that a staff member cannot be in two places
    at once. This test verifies that no staff member is assigned to more than one unique 
    (group, activity) combination in any given time slot.
    
    Validates Constraint 2: Staff non-overlap across activities and groups.
    
    :param schedule_df: DataFrame containing the generated schedule
    :return: List of violations, each as a tuple (time_slot, staff_name, counts_dict)
    """
    violations = []

    # Group by (time_slot, staff) to find all assignments for eac
    # h staff in each time slot
    grouped = schedule_df.groupby(["time_slot", "staff"], observed=False)

    for (ts, staff), sub_df in grouped:
        # Find all distinct group/activity combinations this staff is assigned to in this time slot
        distinct_acts = sub_df[["group", "activity"]].drop_duplicates()
        
        # If more than one distinct assignment exists, this is a violation
        if len(distinct_acts) > 1:
            # Record the specific conflicting assignments
            counts = distinct_acts.value_counts().to_dict()
            violations.append((ts, staff, counts))

    return violations

def test_location_non_overlap(schedule_df):
    """
    Tests that each location is not used by multiple activities in the same time slot.
    
    A location can only host one activity at a time. This test verifies that no location 
    is assigned to more than one unique (group, activity) combination in any given time slot.
    
    Validates Constraint 3: Location non-overlap across activities and groups.
    
    :param schedule_df: DataFrame containing the generated schedule
    :return: List of violations, each as a tuple (time_slot, location, counts_dict)
    """
    violations = []

    # Exclude placeholder location "NA" (used for special activities like inspection)
    schedule_df = schedule_df[schedule_df["location"] != "NA"]

    # Group by (time_slot, location) to find all assignments for each location in each time slot
    grouped = schedule_df.groupby(["time_slot", "location"], observed=False)

    for (ts, loc), sub_df in grouped:
        # Find distinct group/activity combinations assigned to this location in this time slot
        # (Multiple staff may be assigned to the same activity, so we need to find unique combinations)
        distinct_assignments = sub_df[["group","activity"]].drop_duplicates()

        # If more than one distinct assignment exists, this is a violation
        if len(distinct_assignments) > 1:
            # Record the specific conflicting assignments
            combos = distinct_assignments.value_counts().to_dict()
            violations.append((ts, loc, combos))

    return violations

def test_activity_exclusivity(schedule_df):
    """
    Tests that each activity is assigned to at most one group in each time slot.
    
    Activities are exclusive resources - only one group can do a particular activity
    at a given time. This test verifies that no activity is assigned to multiple groups
    in the same time slot.
    
    Validates Constraint 1: Activity exclusivity across groups in the same time slot.
    
    :param schedule_df: DataFrame containing the generated schedule
    :return: List of violations, each as a tuple (time_slot, activity, [group_list])
    """
    violations = []

    # Group by (time_slot, activity) to find all group assignments for each activity in each time slot
    grouped = schedule_df.groupby(["time_slot", "activity"], observed=False)

    for (ts, act), sub_df in grouped:
        # Find all distinct groups assigned to this activity in this time slot
        distinct_groups = sub_df["group"].drop_duplicates()
        
        # If more than one group is assigned to this activity, this is a violation
        if len(distinct_groups) > 1:
            violations.append((ts, act, distinct_groups.tolist()))
            
    return violations

def test_group_activity_count_with_waterfront_and_golf_tennis(schedule_df, group_ids, waterfront_schedule):
    """
    Tests that each group has the correct number of activities in each time slot.
    
    The schedule has specific rules for how many activities each group should have 
    scheduled in each time slot:
    1. In waterfront time slots: Exactly 1 activity ('waterfront')
    2. In golf+tennis time slots: Exactly 2 activities ('golf' and 'tennis')
    3. In all other time slots: Exactly 4 activities
    
    Validates Constraint 5: Group-specific activity assignment.
    Validates Constraint 11: Waterfront scheduling.
    Validates Constraint 12: Golf and Tennis pairing requirement.
    
    :param schedule_df: DataFrame containing the generated schedule
    :param group_ids: List of group IDs
    :param waterfront_schedule: Dictionary mapping group IDs to their waterfront time slots
    :return: List of violations, each as a dictionary with details
    """
    violations = []

    # Group by (group, time_slot) to analyze each group's activities in each time slot
    grouped = schedule_df.groupby(["group", "time_slot"], observed=False)
    
    for (grp, ts), sub_df in grouped:
        # Skip inspection and other special activities with "NA" group
        if grp == "NA":
            continue

        # Get distinct activities assigned to this group in this time slot
        distinct_acts = set(sub_df["activity"].drop_duplicates())

        # CASE 1: Check waterfront slots (should be exactly one activity: 'waterfront')
        if ts in waterfront_schedule[grp]:
            if len(distinct_acts) != 1 or "waterfront" not in distinct_acts:
                violations.append({
                    "group": grp,
                    "time_slot": ts,
                    "msg": f"Expected exactly 1 activity='waterfront', found {list(distinct_acts)}"
                })
        
        # CASE 2: Check for golf+tennis slots (should be exactly two activities: 'golf' and 'tennis')
        elif distinct_acts == {"golf", "tennis"}:
            # This is a valid golf+tennis slot - no violation
            continue
        
        # CASE 3: Regular slots should have exactly 4 activities
        else:
            act_count = len(distinct_acts)
            if act_count != 4:
                violations.append({
                    "group": grp,
                    "time_slot": ts,
                    "msg": f"Expected 4 activities, found {act_count}: {list(distinct_acts)}"
                })

    return violations



def test_location_activity_match(schedule_df, loc_options_df):
    """
    Tests that each activity is assigned to a valid location according to location options.
    
    Activities can only be conducted at specific locations that have the appropriate 
    facilities. This test verifies that each activity in the schedule is assigned to a 
    location that is valid for that activity type according to the location options data.
    
    Validates Constraint 4: Activities only take place in valid locations.
    
    :param schedule_df: DataFrame containing the generated schedule
    :param loc_options_df: DataFrame containing the valid activity-location pairs
    :return: List of violations, each as a dictionary with details
    """
    violations = []

    # Create a set of valid (activityName, locName) pairs from location options data
    # This is used for fast lookup to check if an activity-location pair is valid
    valid_pairs = set(
        zip(loc_options_df["activityName"], loc_options_df["locName"])
    )

    # Check each row in the schedule
    for _, row in schedule_df.iterrows():
        activity_name = row["activity"]
        location_name = row["location"]

        # Skip special activities with placeholder location "NA"
        if location_name == "NA":
            continue

        # Check if the activity-location pair is valid
        if (activity_name, location_name) not in valid_pairs:
            violations.append({
                "activity": activity_name,
                "location": location_name,
                "time_slot": row["time_slot"],
                "group": row["group"]
            })
            
    return violations

def test_staff_availability(schedule_df, staff_off_time_slots, staff_df):
    """
    Tests that no staff members are assigned to activities during their time off.
    
    Staff members have designated times when they are unavailable (time off, trips,
    other commitments). This test verifies that no staff member is scheduled for
    any activity during their designated unavailable time slots.
    
    Validates Constraint 7: Staff availability.
    Validates Constraint 23: Trip assignment enforcement.
    Validates Constraint 24: Trip exclusivity.
    
    :param schedule_df: DataFrame containing the generated schedule
    :param staff_off_time_slots: Dictionary mapping staff IDs to lists of unavailable time slots
    :param staff_df: DataFrame containing staff information (including IDs and names)
    :return: List of violations, each as a dictionary with details
    """
    violations = []
    
    for _, row in schedule_df.iterrows():
        staff_name = row["staff"]
        time_slot = row["time_slot"]

        # Find the staff ID corresponding to this staff name
        sid_series = staff_df.loc[staff_df["staffName"] == staff_name, "staffID"]

        # Skip if staff name doesn't exist in the database
        if sid_series.empty:
            continue

        # Get the staff ID from the series
        staff_id = sid_series.iloc[0]

        # Check if this staff member is assigned during their time off
        if staff_id in staff_off_time_slots and time_slot in staff_off_time_slots[staff_id]:
            violations.append({
                "staff": staff_name,
                "time_slot": time_slot,
                "activity": row["activity"],
                "group": row["group"]
            })

    return violations

def test_mandatory_leads(schedule_df, leads_mapping, staff_df, activity_df):
    """
    Tests that each activity has at least one qualified leader assigned.
    
    For safety and quality reasons, each scheduled activity must have at least
    one staff member who is qualified to lead that activity type. This test verifies
    that every activity in the schedule has at least one assigned staff member who
    is designated as a qualified leader for that activity.
    
    Validates Constraint 10: Leadership requirement for activities.
    
    :param schedule_df: DataFrame containing the generated schedule
    :param leads_mapping: Dictionary mapping staff IDs to lists of activities they can lead
    :param staff_df: DataFrame containing staff information
    :param activity_df: DataFrame containing activity information
    :return: List of violations, each as a dictionary with details
    """
    violations = []

    # Create a mapping of activity names to their IDs for lookup
    activity_name_to_id = dict(zip(activity_df["activityName"], activity_df["activityID"]))
    
    # Convert the leads mapping to use sets for faster lookups
    staff_lead_lookup = {
        sid: set(activities) for sid, activities in leads_mapping.items()
    }

    # Group the schedule by time slot, group, and activity
    grouped = schedule_df.groupby(["time_slot", "group", "activity"], observed=False)

    for (ts, grp, act), sub_df in grouped:
        # Skip special activities like inspection (indicated by group="NA")
        if grp == "NA":
            continue

        # Get the activity ID from the activity name
        activity_id = activity_name_to_id[act]

        # Collect the staff IDs assigned to this activity
        staff_ids = []
        for staff_name in sub_df["staff"].unique():
            # Find the staff ID for this staff name
            sid_array = staff_df.loc[staff_df["staffName"] == staff_name, "staffID"]
            if not sid_array.empty:
                staff_ids.append(sid_array.values[0])

        # Check if any of the assigned staff can lead this activity
        can_lead = False
        for sid in staff_ids:
            if activity_id in staff_lead_lookup.get(sid, set()):
                can_lead = True
                break

        # If no qualified leader is assigned, record a violation
        if not can_lead:
            violations.append({
                "time_slot": ts,
                "group": grp,
                "activity": act,
                "message": "No qualified leader assigned to this activity"
            })

    return violations

def test_only_leads_and_assists(schedule_df, leads_mapping, assists_mapping, staff_df, activity_df):
    """
    Tests that staff are only assigned to activities they are qualified to lead or assist with.
    
    Staff members should only be assigned to activities for which they have the appropriate
    qualifications, either as a leader or assistant. This test verifies that no staff member
    is assigned to an activity for which they are neither qualified to lead nor assist.
    
    Validates Constraint 9: Skill qualification for activities.
    
    :param schedule_df: DataFrame containing the generated schedule
    :param leads_mapping: Dictionary mapping staff IDs to activities they can lead
    :param assists_mapping: Dictionary mapping staff IDs to activities they can assist with
    :param staff_df: DataFrame containing staff information
    :param activity_df: DataFrame containing activity information
    :return: List of violations, each as a dictionary with details
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

        # skip for non-standard activities (inspection, trips)
        if activity_name not in activity_name_to_id or row["group"] == "NA":
            continue

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

def test_inspection_daily(schedule_df, inspection_slots):
    """
    Tests that cabin inspection is correctly scheduled each day.
    
    Cabin inspection has specific scheduling requirements:
    1. Exactly one staff member must be assigned to inspection during period 1 of each day
    2. No inspection should be scheduled during other periods
    
    This test verifies that these inspection scheduling rules are followed correctly.
    
    Validates Constraint 15: Daily cabin inspection requirement.
    Validates Constraint 16: Inspection and activity exclusivity.
    
    :param schedule_df: DataFrame containing the generated schedule
    :param inspection_slots: List of time slots when inspection can be scheduled
    :return: List of violations, each as a dictionary with details
    """
    violations = []
    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]

    for day in days:
        # Define the designated inspection time slot for the day
        designated_slot = (day, 1)  # Period 1

        # Filter schedule_df for inspections in the designated slot
        inspections_in_designated = schedule_df[
            (schedule_df['time_slot'] == designated_slot) &
            (schedule_df['activity'] == 'inspection')
        ]

        # One staff assigned to inspection
        if len(inspections_in_designated['staff'].unique()) < 1:
            violations.append({
                "day": day,
                "time_slot": designated_slot,
                "message": f"No staff assigned to inspection on {day} Period 1."
            })

        # Check that exactly one inspection is assigned in the designated slot
        inspection_count = len(inspections_in_designated)
        if inspection_count != 1:
            violations.append({
                "day": day,
                "time_slot": designated_slot,
                "message": f"Expected exactly 1 inspection on {day} Period 1, found {inspection_count}."
            })

        # Check that no inspections are assigned outside the designated slot
        # Define the non-designated slots for the day (Periods 2 and 3)
        non_designated_slots = [(day, period) for period in [2, 3]]

        # Filter schedule_df for inspections in non-designated slots
        inspections_outside_designated = schedule_df[
            (schedule_df['time_slot'].isin(non_designated_slots)) &
            (schedule_df['activity'] == 'inspection')
        ]

        # Check that no inspections are assigned outside the designated slot
        if not inspections_outside_designated.empty:
            for _, row in inspections_outside_designated.iterrows():
                violations.append({
                    "day": day,
                    "time_slot": row['time_slot'],
                    "message": "Inspection assigned outside designated inspection slot (Period 1)."
                })

    return violations


def test_driving_range_constraints(schedule_df, group_ids, allowed_dr_days):
    """
    Tests that driving range activities follow the required scheduling constraints.
    
    Driving range has specific scheduling requirements:
    1. Each group must have driving range exactly once per week
    2. Driving range must occupy both periods 1 and 2 of the same day
    3. Driving range can only be scheduled on allowed days (Monday-Thursday)
    4. The same staff must be assigned to both driving range periods
    5. At least one qualified staff must be assigned to driving range
    
    Validates Constraint 17: Driving range frequency requirement.
    Validates Constraint 18: Driving range scheduling restrictions.
    Validates Constraint 19: Driving range period continuity.
    Validates Constraint 20: Driving range staffing requirements.
    Validates Constraint 21: Driving range staff continuity.
    Validates Constraint 22: Staff availability for driving range.
    
    :param schedule_df: DataFrame containing the generated schedule
    :param group_ids: List of group IDs
    :param allowed_dr_days: List of days when driving range is allowed to be scheduled
    :return: List of violations, each as a dictionary with details
    """
    violations = []
    driving_range_activity = "driving range"

    for g in group_ids:
        # Filter Driving Range activities for this group
        dr_schedule = schedule_df[
            (schedule_df['group'] == g) &
            (schedule_df['activity'].str.lower() == driving_range_activity)
            ]

        # 1. Check frequency: exactly two entries (Periods 1 and 2)
        if len(dr_schedule) != 2:
            violations.append({
                "group": g,
                "msg": f"Expected Driving Range to be scheduled once per week (2 periods), found {len(dr_schedule)}."
            })
            continue  # Skip further checks for this group

        # 2. Check that both periods are on the same day and in Periods 1 and 2
        days_scheduled = dr_schedule['time_slot'].apply(lambda x: x[0]).unique()
        periods_scheduled = dr_schedule['time_slot'].apply(lambda x: x[1]).tolist()

        if len(days_scheduled) != 1:
            violations.append({
                "group": g,
                "msg": f"Driving Range periods are on different days: {days_scheduled.tolist()}."
            })

        day_scheduled = days_scheduled[0]
        if day_scheduled not in allowed_dr_days:
            violations.append({
                "group": g,
                "msg": f"Driving Range is scheduled on an invalid day: {day_scheduled}."
            })

        if sorted(periods_scheduled) != [1, 2]:
            violations.append({
                "group": g,
                "msg": f"Driving Range is not scheduled in Periods 1 and 2, found periods {periods_scheduled}."
            })

        # 3. Check same staff assigned to both periods
        staff_assigned_periods = dr_schedule['staff'].tolist()

        # Convert list of lists to set of tuples for comparison
        staff_sets = [set(staff) for staff in staff_assigned_periods]

        if not all(s == staff_sets[0] for s in staff_sets):
            violations.append({
                "group": g,
                "msg": f"Different staff members assigned to Driving Range periods: {staff_assigned_periods}."
            })
        else:
            # 4. Check staff count limits
            assigned_staff = staff_sets[0]
            num_staff = len(assigned_staff)
            if num_staff < 1:
                violations.append({
                    "group": g,
                    "msg": f"Driving Range has no staff assigned)."
                })

    return violations


def test_trip_staff_assignment(schedule_df, staff_trips, staff_df):
    """
    Tests that all staff members assigned to trips are correctly included in the schedule.
    
    When staff are assigned to trips, they should appear in the schedule with the correct
    trip assignment. This test verifies that all staff who are scheduled for trips are 
    properly included in the schedule output.
    
    Validates Constraint 23: Trip assignment enforcement.
    
    :param schedule_df: DataFrame containing the generated schedule
    :param staff_trips: Dictionary mapping staff IDs to their trip assignments
    :param staff_df: DataFrame containing staff information
    :return: List of violations, each as a dictionary with details
    """
    violations = []
    
    # Create a copy of the schedule to avoid modifying the original
    schedule_copy = schedule_df.copy()
    
    # Normalize staff column to list format
    schedule_copy['staff'] = schedule_copy['staff'].apply(
        lambda x: [x] if not isinstance(x, list) else x
    )
    
    # First, build a set of expected trip assignments
    expected_trip_assignments = set()
    for staff_id, trips in staff_trips.items():
        staff_name = staff_df.loc[staff_df["staffID"] == staff_id, "staffName"].values[0]
        for time_slot, trip_name in trips:
            expected_trip_assignments.add((staff_name, time_slot, trip_name))
    
    # Now extract actual trip assignments from the schedule
    actual_trip_assignments = set()
    trip_schedule = schedule_copy[schedule_copy["group"] == "NA"]  # Trips use "NA" for group
    trip_schedule = trip_schedule[trip_schedule["location"] == "NA"]  # Trips use "NA" for location
    trip_schedule = trip_schedule[trip_schedule["activity"] != "inspection"]  # Exclude inspection duty
    
    for _, row in trip_schedule.iterrows():
        # Staff may be a single name or a list
        staff_list = row["staff"]
        time_slot = row["time_slot"]
        trip_name = row["activity"]  # Trip name is stored in the activity field
        
        # Add each staff member to the set of actual assignments
        for staff_name in staff_list:
            actual_trip_assignments.add((staff_name, time_slot, trip_name))
    
    # Check for missing trip assignments
    missing_assignments = expected_trip_assignments - actual_trip_assignments
    for staff_name, time_slot, trip_name in missing_assignments:
        violations.append({
            "staff": staff_name,
            "time_slot": time_slot,
            "trip_name": trip_name,
            "message": "Staff member assigned to trip is missing from schedule"
        })
    
    return violations

def test_trip_time_slots(schedule_df, trips_df):
    """
    Tests that all trips are scheduled in the correct time slots.
    
    Trips must be scheduled on the exact days and periods specified in the trips data.
    This test verifies that all trips in the schedule appear in their correct designated
    time slots.
    
    Validates Constraint 23: Trip assignment enforcement.
    
    :param schedule_df: DataFrame containing the generated schedule
    :param trips_df: DataFrame containing trip information
    :return: List of violations, each as a dictionary with details
    """
    violations = []
    
    if trips_df.empty:
        return violations  # No trips to check
    
    # Extract trip schedule entries
    trip_schedule = schedule_df[schedule_df["group"] == "NA"]  # Trips use "NA" for group
    trip_schedule = trip_schedule[trip_schedule["location"] == "NA"]  # Trips use "NA" for location
    trip_schedule = trip_schedule[trip_schedule["activity"] != "inspection"]  # Exclude inspection duty
    
    if trip_schedule.empty:
        return violations  # No trips in schedule
    
    # First, check if all trips in the trip data appear in the schedule
    scheduled_trip_names = set(trip_schedule["activity"].unique())
    expected_trip_names = set(trips_df["trip_name"].unique())
    
    # Find trips that are in the data but not in the schedule
    missing_trips = expected_trip_names - scheduled_trip_names
    for trip_name in missing_trips:
        violations.append({
            "trip_name": trip_name,
            "message": "Trip exists in trip data but is completely missing from schedule"
        })
    
    # Check that trips are scheduled in all required time slots
    for trip_name in scheduled_trip_names & expected_trip_names:  # Intersection - only check trips that appear in both
        # Get the trip schedule for this trip
        trip_group = trip_schedule[trip_schedule["activity"] == trip_name]
        
        # Find this trip in the trips_df to get expected time slots
        trip_entries = trips_df[trips_df["trip_name"] == trip_name]
        
        # Group trip entries by date to handle multi-day trips
        for date_str, date_entries in trip_entries.groupby("date"):
            # Convert date string to day of week
            import datetime
            try:
                date_dt = datetime.datetime.strptime(date_str, "%m/%d/%Y")
                day_of_week = date_dt.strftime("%A")
            except ValueError:
                violations.append({
                    "trip_name": trip_name,
                    "date": date_str,
                    "message": "Invalid date format in trip data"
                })
                continue
            
            # Get start and end periods for this trip on this day
            min_period = date_entries["start_period"].min()
            max_period = date_entries["end_period"].max()
            
            # Get all time slots where this trip appears in the schedule
            scheduled_slots = set(trip_group["time_slot"].tolist())
            
            # Check if all expected periods for this day are covered
            for period in range(min_period, max_period + 1):
                expected_slot = (day_of_week, period)
                if expected_slot not in scheduled_slots:
                    violations.append({
                        "trip_name": trip_name,
                        "date": date_str,
                        "expected_slot": expected_slot,
                        "message": f"Trip missing from required time slot ({day_of_week}, period {period})"
                    })
        
    return violations

def test_trip_staff_consistency(schedule_df):
    """
    Tests that the same staff are assigned for the full duration of each trip.
    
    Staff assignments for a given trip should be consistent across all time slots.
    This test verifies that the same staff members are assigned to a trip throughout
    its entire duration, with no different staff for different periods.
    
    Validates Constraint 23: Trip assignment enforcement.
    
    :param schedule_df: DataFrame containing the generated schedule
    :return: List of violations, each as a dictionary with details
    """
    violations = []
    
    # Create a copy of the schedule to avoid modifying the original
    trip_schedule = schedule_df.copy()
    
    # Make sure staff column is normalized to lists for consistent comparison
    # The staff column might be a list in some places and a single value in others
    trip_schedule['staff'] = trip_schedule['staff'].apply(
        lambda x: [x] if not isinstance(x, list) else x
    )
    
    # Extract trip schedule entries
    trip_schedule = trip_schedule[trip_schedule["group"] == "NA"]  # Trips use "NA" for group
    trip_schedule = trip_schedule[trip_schedule["location"] == "NA"]  # Trips use "NA" for location
    trip_schedule = trip_schedule[trip_schedule["activity"] != "inspection"]  # Exclude inspection duty
    
    if trip_schedule.empty:
        return violations  # No trips to check
    
    # Group trips by name to check staff consistency
    for trip_name, trip_group in trip_schedule.groupby("activity"):
        # Collect all staff sets per time slot
        staff_by_slot = {}
        
        for _, row in trip_group.iterrows():
            slot = row["time_slot"]
            staff_list = sorted(row["staff"])  # Sort for consistent comparison
            
            if slot not in staff_by_slot:
                staff_by_slot[slot] = set(tuple(staff_list))
            else:
                staff_by_slot[slot].add(tuple(staff_list))
        
        # Skip trips with only one time slot
        if len(staff_by_slot) <= 1:
            continue
            
        # Get the first staff set as reference
        slots = sorted(list(staff_by_slot.keys()))  # Sort slots for consistent reference
        reference_slot = slots[0]
        reference_staff = staff_by_slot[reference_slot]
        
        # Check all other time slots against the reference
        for slot in slots[1:]:
            current_staff = staff_by_slot[slot]
            if current_staff != reference_staff:
                violations.append({
                    "trip_name": trip_name,
                    "reference_slot": reference_slot,
                    "reference_staff": [list(s) for s in reference_staff],
                    "different_slot": slot,
                    "different_staff": [list(s) for s in current_staff],
                    "message": "Staff assignments not consistent across trip time slots"
                })
                
    return violations

def test_daily_activity_repetition_for_groups(schedule_df, activity_df):
    """
    Tests that no group has the same activity scheduled more than once on the same day,
    excluding activities with duration > 1 (e.g., driving range).

    Validates Constraint 25: No group can have the same activity twice in the same day.

    :param schedule_df: DataFrame containing the generated schedule
    :param activity_df: DataFrame containing activity information (including duration)
    :return: List of violations, each as a dictionary with details
    """
    violations = []

    # Filter out non-group activities (e.g., inspection, trips)
    group_schedule_df = schedule_df[schedule_df['group'] != "NA"].copy()

    if group_schedule_df.empty:
        return violations

    # Identify activities with duration > 1, these should be excluded from the check
    multi_period_activities = set(
        activity_df[activity_df['duration'] > 1]['activityName']
    )

    # Extract day from time_slot
    group_schedule_df['day'] = group_schedule_df['time_slot'].apply(lambda ts: ts[0])
    group_schedule_df['period'] = group_schedule_df['time_slot'].apply(lambda ts: ts[1]) # Add period column

    # Group by group and day, then check activity counts
    for (group_id, day), daily_schedule_for_group in group_schedule_df.groupby(['group', 'day'], observed=False):
        # Filter out multi-period activities before counting repetitions
        activities_to_check_today = daily_schedule_for_group[
            ~daily_schedule_for_group['activity'].isin(multi_period_activities)
        ]
        
        if activities_to_check_today.empty:
            continue

        # For each activity name, count how many distinct periods it appears in for this group on this day
        activity_period_counts = activities_to_check_today.groupby('activity')['period'].nunique()
        
        repeated_activities = activity_period_counts[activity_period_counts > 1]

        for activity_name, period_count in repeated_activities.items(): # period_count is the number of distinct periods
            violations.append({
                "group": group_id,
                "day": day,
                "activity": activity_name,
                "count": period_count, # This is now the count of distinct periods
                "message": f"Activity '{activity_name}' scheduled in {period_count} different periods for group {group_id} on {day}."
            })
    return violations

def analyze_staff_workload_distribution(schedule_df, staff_df):
    """
    Analyzes the distribution of activity assignments across staff members.
    
    This function calculates the minimum, average, and maximum number of activities 
    assigned to each staff member, and identifies which staff members have the minimum
    and maximum assignments.
    
    :param schedule_df: DataFrame containing the generated schedule
    :param staff_df: DataFrame containing staff information
    :return: Dictionary with summary statistics
    """
    # Create a normalized copy for analysis
    analysis_df = schedule_df.copy()
    
    # Normalize staff column to individual staff members (in case staff is stored as lists)
    if analysis_df['staff'].apply(lambda x: isinstance(x, list)).any():
        analysis_df = analysis_df.explode('staff')
    
    # Count assignments per staff member
    staff_assignments = analysis_df['staff'].value_counts().reset_index()
    staff_assignments.columns = ['staff_name', 'assignment_count']
    
    # Calculate statistics
    min_assignments = staff_assignments['assignment_count'].min()
    max_assignments = staff_assignments['assignment_count'].max()
    avg_assignments = staff_assignments['assignment_count'].mean()
    
    # Get staff with min and max assignments
    min_staff = staff_assignments[staff_assignments['assignment_count'] == min_assignments]['staff_name'].tolist()
    max_staff = staff_assignments[staff_assignments['assignment_count'] == max_assignments]['staff_name'].tolist()
    
    # Print the results
    print("\n===== STAFF WORKLOAD DISTRIBUTION =====")
    print(f"Minimum assignments: {min_assignments}")
    print(f"Staff with minimum assignments ({min_assignments}): {', '.join(min_staff)}")
    print(f"Average assignments: {avg_assignments:.2f}")
    print(f"Maximum assignments: {max_assignments}")
    print(f"Staff with maximum assignments ({max_assignments}): {', '.join(max_staff)}")
    
    # Calculate standard deviation to see how evenly distributed the workload is
    std_dev = staff_assignments['assignment_count'].std()
    print(f"Standard deviation: {std_dev:.2f} (lower is better - indicates more balanced workload)")
    
    return {
        'min_assignments': min_assignments,
        'min_staff': min_staff,
        'avg_assignments': avg_assignments,
        'max_assignments': max_assignments,
        'max_staff': max_staff,
        'std_dev': std_dev
    }

def analyze_staff_activity_diversity(schedule_df, staff_df):
    """
    Analyzes the diversity of activities assigned to each staff member.
    
    This function calculates the minimum, average, and maximum number of unique activities
    that each staff member is assigned to, and identifies which staff members have the
    minimum and maximum activity diversity.
    
    :param schedule_df: DataFrame containing the generated schedule
    :param staff_df: DataFrame containing staff information
    :return: Dictionary with summary statistics
    """
    # Create a normalized copy for analysis
    analysis_df = schedule_df.copy()
    
    # Normalize staff column to individual staff members (in case staff is stored as lists)
    if analysis_df['staff'].apply(lambda x: isinstance(x, list)).any():
        analysis_df = analysis_df.explode('staff')
    
    # Group by staff and count unique activities
    staff_activity_diversity = analysis_df.groupby('staff')['activity'].nunique().reset_index()
    staff_activity_diversity.columns = ['staff_name', 'unique_activities']
    
    # Calculate statistics
    min_activities = staff_activity_diversity['unique_activities'].min()
    max_activities = staff_activity_diversity['unique_activities'].max()
    avg_activities = staff_activity_diversity['unique_activities'].mean()
    
    # Get staff with min and max unique activities
    min_staff = staff_activity_diversity[staff_activity_diversity['unique_activities'] == min_activities]['staff_name'].tolist()
    max_staff = staff_activity_diversity[staff_activity_diversity['unique_activities'] == max_activities]['staff_name'].tolist()
    
    # Print the results
    print("\n===== STAFF ACTIVITY DIVERSITY =====")
    print(f"Minimum unique activities: {min_activities}")
    print(f"Staff with minimum diversity ({min_activities}): {', '.join(min_staff)}")
    print(f"Average unique activities: {avg_activities:.2f}")
    print(f"Maximum unique activities: {max_activities}")
    print(f"Staff with maximum diversity ({max_activities}): {', '.join(max_staff)}")
    
    # Calculate standard deviation
    std_dev = staff_activity_diversity['unique_activities'].std()
    print(f"Standard deviation: {std_dev:.2f}")
    
    # Also report staff with high repetition of the same activity
    print("\nStaff with high activity repetition:")
    staff_activity_counts = analysis_df.groupby(['staff', 'activity']).size().reset_index(name='count')
    staff_with_repetition = staff_activity_counts[staff_activity_counts['count'] > 4]
    
    if len(staff_with_repetition) > 0:
        for _, row in staff_with_repetition.sort_values('count', ascending=False).iterrows():
            print(f"  {row['staff']} teaches {row['activity']} {row['count']} times")
    else:
        print("  No staff teaches the same activity more than 4 times")
    
    return {
        'min_activities': min_activities,
        'min_staff': min_staff,
        'avg_activities': avg_activities,
        'max_activities': max_activities,
        'max_staff': max_staff,
        'high_repetition': staff_with_repetition.to_dict('records') if len(staff_with_repetition) > 0 else []
    }

def analyze_group_category_diversity(schedule_df, activity_df):
    """
    Analyzes the diversity of activity categories assigned to each group in each period.
    
    This function calculates the average number of unique activity categories that each
    group experiences in each time slot, providing insight into how varied the activities
    are for campers throughout the schedule.
    
    :param schedule_df: DataFrame containing the generated schedule
    :param activity_df: DataFrame containing activity information including categories
    :return: Dictionary with summary statistics
    """
    # Create a normalized copy for analysis
    analysis_df = schedule_df.copy()
    
    # Skip non-group activities
    analysis_df = analysis_df[analysis_df['group'] != "NA"]
    
    # Create a mapping of activity names to categories
    activity_categories = dict(zip(activity_df['activityName'], activity_df['category']))
    
    # Add category column to the analysis DataFrame
    analysis_df['category'] = analysis_df['activity'].map(activity_categories)
    
    # Group by time_slot and group, then count unique categories
    # First create a grouped object with each (time_slot, group) combination
    category_counts = []
    for (time_slot, group), group_df in analysis_df.groupby(['time_slot', 'group'], observed=False):
        # Skip if group is NA
        if group == "NA":
            continue
            
        # Count unique categories, excluding "fixed" category (waterfront)
        unique_categories = group_df[group_df['category'] != 'fixed']['category'].nunique()
        
        # Store in our results list
        category_counts.append({
            'time_slot': time_slot,
            'group': group,
            'unique_categories': unique_categories
        })
    
    # Convert to DataFrame for analysis
    category_df = pd.DataFrame(category_counts)
    
    # Calculate statistics
    if len(category_df) > 0:  # Ensure there are records to analyze
        avg_categories = category_df['unique_categories'].mean()
        min_categories = category_df['unique_categories'].min()
        max_categories = category_df['unique_categories'].max()
        
        # Find time slots with min and max diversity
        min_slots = category_df[category_df['unique_categories'] == min_categories]
        max_slots = category_df[category_df['unique_categories'] == max_categories]
        
        # Print the results
        print("\n===== GROUP ACTIVITY CATEGORY DIVERSITY =====")
        print(f"Average unique categories per group per period: {avg_categories:.2f}")
        print(f"Minimum categories in a period: {min_categories}")
        print(f"Maximum categories in a period: {max_categories}")
        
        print("\nCategory diversity by group:")
        for group, group_df in category_df.groupby('group', observed=False):
            avg_for_group = group_df['unique_categories'].mean()
            print(f"  Group {group}: {avg_for_group:.2f} avg categories per period")
        
        return {
            'avg_categories': avg_categories,
            'min_categories': min_categories,
            'max_categories': max_categories,
            'min_slots': min_slots.to_dict('records'),
            'max_slots': max_slots.to_dict('records')
        }
    else:
        print("\n===== GROUP ACTIVITY CATEGORY DIVERSITY =====")
        print("No valid data for category diversity analysis")
        return {
            'error': 'No valid data for analysis'
        }

def analyze_group_weekly_activity_diversity(schedule_df, activity_df):
    """
    Analyzes the diversity of unique activities each group experiences weekly.

    Calculates the percentage of total possible activities that each group is
    scheduled for at least once during the week.

    :param schedule_df: DataFrame containing the generated schedule
    :param activity_df: DataFrame containing activity information (e.g., from activity.csv)
    :return: Dictionary with summary statistics
    """
    print("\n===== GROUP WEEKLY ACTIVITY DIVERSITY ANALYSIS =====")

    # Validate input data - check if activity DataFrame is empty
    if activity_df.empty:
        print("Activity data is empty. Cannot perform weekly diversity analysis.")
        return {'error': 'Activity data empty'}

    # Calculate the total number of unique activities available in the system
    total_possible_activities = activity_df['activityName'].nunique()
    if total_possible_activities == 0:
        print("No unique activities found in activity data. Cannot perform weekly diversity analysis.")
        return {'error': 'No unique activities in activity data'}
    
    print(f"Total possible unique activities: {total_possible_activities}")

    # Filter the schedule to only include group activities (exclude inspection, trips, etc.)
    # Activities with group "NA" are typically special activities like inspection or trips
    group_schedule_df = schedule_df[schedule_df['group'] != "NA"].copy()

    # Check if we have any group activities to analyze
    if group_schedule_df.empty:
        print("No group-specific activities found in the schedule to analyze.")
        return {
            'min_percentage': 0,
            'min_group': [],
            'avg_percentage': 0,
            'max_percentage': 0,
            'max_group': [],
            'group_details': []
        }

    # Calculate diversity statistics for each group
    group_diversity_stats = []
    
    # Iterate through each group to analyze their activity diversity
    for group_id, activities_for_group_df in group_schedule_df.groupby('group', observed=False):
        # Count how many unique activities this group is assigned to during the week
        unique_activities_count = activities_for_group_df['activity'].nunique()
        
        # Calculate what percentage of all possible activities this group experiences
        percentage_diversity = (unique_activities_count / total_possible_activities) * 100
        
        # Store the results for this group
        group_diversity_stats.append({
            'group': group_id,
            'unique_activities_count': unique_activities_count,
            'percentage_diversity': percentage_diversity
        })
        
        # Print individual group results
        print(f"Group {group_id}: {percentage_diversity:.2f}% ({unique_activities_count} unique activities)")

    # Validate that we have data to analyze
    if not group_diversity_stats:
        print("No data to calculate diversity statistics.")
        return {
            'min_percentage': 0,
            'min_group': [],
            'avg_percentage': 0,
            'max_percentage': 0,
            'max_group': [],
            'group_details': []
        }

    # Convert results to DataFrame for easier statistical analysis
    diversity_df = pd.DataFrame(group_diversity_stats)

    # Calculate summary statistics across all groups
    min_percentage = diversity_df['percentage_diversity'].min()
    max_percentage = diversity_df['percentage_diversity'].max()
    avg_percentage = diversity_df['percentage_diversity'].mean()

    # Identify which groups have the minimum and maximum diversity
    min_groups = diversity_df[diversity_df['percentage_diversity'] == min_percentage]['group'].tolist()
    max_groups = diversity_df[diversity_df['percentage_diversity'] == max_percentage]['group'].tolist()

    # Print summary statistics
    print(f"Minimum weekly activity diversity: {min_percentage:.2f}% (Group(s): {', '.join(map(str, min_groups))})")
    print(f"Average weekly activity diversity: {avg_percentage:.2f}%")
    print(f"Maximum weekly activity diversity: {max_percentage:.2f}% (Group(s): {', '.join(map(str, max_groups))})")
    
    # Return comprehensive results dictionary
    return {
        'min_percentage': min_percentage,
        'min_groups': min_groups,
        'avg_percentage': avg_percentage,
        'max_percentage': max_percentage,
        'max_groups': max_groups,
        'group_details': group_diversity_stats
    }

def run_tests(schedule_df, group_ids, location_options_df, staff_off_time_slots, staff_df, activity_df, leads_mapping, assists_mapping, waterfront_schedule, inspection_slots, allowed_dr_days, staff_trips=None, trips_df=None):
    """
    Runs all validation tests on the generated schedule and reports the results.
    
    This function orchestrates the running of all the individual test functions to verify
    that the generated schedule meets all the required constraints. It collects and reports
    any violations found by each test, providing a comprehensive validation of the schedule.
    
    :param schedule_df: DataFrame containing the generated schedule
    :param group_ids: List of group IDs
    :param location_options_df: DataFrame containing valid activity-location pairs
    :param staff_off_time_slots: Dictionary mapping staff IDs to unavailable time slots
    :param staff_df: DataFrame containing staff information
    :param activity_df: DataFrame containing activity information
    :param leads_mapping: Dictionary mapping staff IDs to activities they can lead
    :param assists_mapping: Dictionary mapping staff IDs to activities they can assist with
    :param waterfront_schedule: Dictionary mapping group IDs to waterfront time slots
    :param inspection_slots: List of time slots when inspection can be scheduled
    :param allowed_dr_days: List of days when driving range is allowed
    :param staff_trips: Dictionary mapping staff IDs to their trip assignments
    :param trips_df: DataFrame containing trip information
    """

    print("\n========================================")
    print("SCHEDULE VALIDITY TESTS")
    print("========================================")
    staff_overlap_violations = test_staff_non_overlap(schedule_df)
    staff_availability_violations = test_staff_availability(schedule_df, staff_off_time_slots, staff_df)
    location_violations = test_location_non_overlap(schedule_df)
    location_activity_violations = test_location_activity_match(schedule_df, location_options_df)
    activity_violations = test_activity_exclusivity(schedule_df)
    group_wf_violations = test_group_activity_count_with_waterfront_and_golf_tennis(schedule_df, group_ids, waterfront_schedule)
    leads_violations = test_mandatory_leads(schedule_df, leads_mapping, staff_df, activity_df)
    no_leads_or_assists_violations = test_only_leads_and_assists(schedule_df, leads_mapping, assists_mapping, staff_df, activity_df)
    inspection_violations = test_inspection_daily(schedule_df, inspection_slots)
    driving_range_violations = test_driving_range_constraints(schedule_df, group_ids, allowed_dr_days)
    
    # Test for daily activity repetition for groups
    daily_activity_repetition_violations = test_daily_activity_repetition_for_groups(schedule_df, activity_df)

    # Run trip-related tests if the data is provided
    trip_assignment_violations = []
    trip_time_slot_violations = []
    trip_staff_consistency_violations = []
    
    if staff_trips is not None and staff_df is not None:
        trip_assignment_violations = test_trip_staff_assignment(schedule_df, staff_trips, staff_df)
    
    if trips_df is not None:
        trip_time_slot_violations = test_trip_time_slots(schedule_df, trips_df)
    
    trip_staff_consistency_violations = test_trip_staff_consistency(schedule_df)

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
        print("Group Activity Count per Period Violations:", group_wf_violations)
    else:
        print("Group Activity Count per Period: PASSED")
        
    if inspection_violations:
        print("Inspection Violations:", inspection_violations)
    else:
        print("Inspection Check: PASSED")
        
    if driving_range_violations:
        print("Driving Range Violations:", driving_range_violations)
    else:
        print("Driving Range Check: PASSED")
        
    if daily_activity_repetition_violations:
        print("Daily Activity Repetition for Groups Violations:", daily_activity_repetition_violations)
    else:
        print("Daily Activity Repetition for Groups: PASSED")
        
    # Report trip test results if they were run
    if staff_trips is not None:
        if trip_assignment_violations:
            print("Trip Staff Assignment Violations:", trip_assignment_violations)
        else:
            print("Trip Staff Assignment: PASSED")
    
    if trips_df is not None:
        if trip_time_slot_violations:
            print("Trip Time Slot Violations:", trip_time_slot_violations)
        else:
            print("Trip Time Slots: PASSED")
    
    if trip_staff_consistency_violations:
        print("Trip Staff Consistency Violations:", trip_staff_consistency_violations)
    else:
        print("Trip Staff Consistency: PASSED")
        
    # Run optimization metric analyses
    print("\n========================================")
    print("SCHEDULE OPTIMIZATION METRICS ANALYSIS")
    print("========================================")
    analyze_staff_workload_distribution(schedule_df, staff_df)
    analyze_staff_activity_diversity(schedule_df, staff_df)
    analyze_group_category_diversity(schedule_df, activity_df)
    analyze_group_weekly_activity_diversity(schedule_df, activity_df)