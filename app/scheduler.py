from ortools.sat.python import cp_model
from data_manager import DataManager
from schedule_tests import run_tests
from datetime import datetime
import pandas as pd

def map_dates_to_time_slots(dates, base_date = "01/06/2025"):
    """
    Map dates to corresponding fay of the week in the time slot format
    :param dates: List of dates in MM/DD/YY format
    :param base_date: first day of the week in MM/DD/YY format (e.g. Monday)
    :return: Dictionary mapping dates to time slots
    """
    base_date = datetime.strptime(base_date, "%m/%d/%Y")
    time_slots_map = []

    for date_str in dates:
        date = datetime.strptime(date_str, "%m/%d/%Y")
        day_offset = (date - base_date).days
        day_of_week = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"][day_offset % 6]
        time_slots = [(day_of_week, period) for period in range(1,4)]
        time_slots_map.extend([(day_of_week, period) for period in range(1,4)])

    return time_slots_map

class Scheduler:
    def __init__(self, staff_df, activity_df, location_df, location_options_df, group_df, time_slots, staff_unavailable_time_slots, leads_mapping, assists_mapping, waterfront_schedule):
        """
        Initialize the Scheduler.
        :param staff_df: List of staff names and IDs
        :param activity_df: List of activity IDs and their metadata
        :param location_df: List of location names and IDs
        :param group_df: List of group IDs
        :param time_slots: List of available time slots
        :param staff_unavailable_time_slots: Dictionary mapping staff IDs to unavailable time slots
        """
        self.staff_df = staff_df
        self.activity_df = activity_df
        self.location_df = location_df
        self.location_options_df = location_options_df
        self.group_df = group_df
        self.time_slots = time_slots
        self.staff_unavailable_time_slots = staff_unavailable_time_slots
        self.leads_mapping = leads_mapping
        self.assists_mapping = assists_mapping
        self.waterfront_schedule = waterfront_schedule

    def solve(self):
        # Extract IDs
        staff_ids = self.staff_df["staffID"].tolist()
        activity_ids = self.activity_df["activityID"].tolist()
        location_ids = self.location_df["locID"].tolist()
        group_ids = self.group_df["groupID"].tolist()
        waterfront_id = self.activity_df.loc[
            self.activity_df["activityName"] == "waterfront",
            "activityID"
        ].values[0]

        # Create the model
        model = cp_model.CpModel()

        # Decision variables
        x = {} # Group specific staff assignment: x[i: staff, j: activity, k: time slot]
        y = {} # Group specific location assignment y[l: location, j: activity, k: time slot ]
        t = {} # Total staff assigned to activity j, k, g
        z = {} # if z == 1, then T_jkg >= numStaffReq[j], else T_jkg == 0

        for g in group_ids:
            for i in staff_ids:
                for j in activity_ids:
                    for k in self.time_slots:
                        x[i,j,k, g] = model.NewBoolVar(f'x[{i},{j},{k[0]}, {k[1]},{g}]')

            for l in location_ids:
                for j in activity_ids:
                    for k in self.time_slots:
                        y[l,j,k, g] = model.NewBoolVar(f'y[{l},{j},{k[0]}, {k[1]},{g}]')

        for g in group_ids:
            for j in activity_ids:
                for k in self.time_slots:
                    # Create an IntVar for total staff assigned to activity j, k, g
                    t[j,k,g] = model.NewIntVar(
                        0,
                        len(staff_ids),
                        f't[{j},{k[0]}, {k[1]},{g}]'
                    )

                    # Sum of x[i,j,k,g] must match t[j,k,g]
                    model.Add(
                        t[j,k,g] == sum(x[i,j,k,g] for i in staff_ids)
                    )

                    # Create a BoolVar for "activity j chosen in (k,g)"
                    z[j,k,g] = model.NewBoolVar(
                        f'z[{j},{k[0]}, {k[1]},{g}]'
                    )

        # CONSTRAINTS:
        # Activity exclusivity across groups in the same time slot
        for j in activity_ids:
            for k in self.time_slots:
                model.Add(
                    sum(z[j,k,g] for g in group_ids) <= 1
                )

        # Staff non-overlap across groups in the same time slot
        for i in staff_ids:
            for k in self.time_slots:
                model.Add(
                    sum(x[i,j,k,g] for j in activity_ids for g in group_ids) <= 1
                )

        # Location non-overlap across groups in the same time slot
        for l in location_ids:
            for k in self.time_slots:
                model.Add(
                    sum(y[l,j,k,g] for j in activity_ids for g in group_ids) <=1
                )

        # Activities only take place in a valid location
        # Create mapping of activityID to valid locationID
        valid_locations = (
            self.location_options_df.groupby("activityID")["locID"]
            .apply(list)
            .to_dict()
        )
        for g in group_ids:
            for j in activity_ids:
                for k in self.time_slots:
                    valid_loc_vars = [y[l,j,k,g] for l in valid_locations.get(j, [])]
                    model.Add(sum(valid_loc_vars) == z[j,k,g])

        # Group-specific activity assignment (4 activities per time slot)
        for g in group_ids:
            for k in self.time_slots:
                if k not in waterfront_schedule[g]:
                    model.Add(
                        sum(z[j,k,g] for j in activity_ids) == 4
                    )
                else:
                    pass

        # Link staff, location, and activity assignments
        for g in group_ids:
            for j in activity_ids:
                for k in self.time_slots:
                    # If activity j is chosen (z=1), pick exactly one location
                    model.Add(
                        sum(y[l,j,k,g] for l in location_ids) == 1
                    ).OnlyEnforceIf(z[j,k,g])

                    # If not chosen, no location is assigned
                    model.Add(
                        sum(y[l,j,k,g] for l in location_ids) == 0
                    ).OnlyEnforceIf(z[j,k,g].Not())

                    # For each location, if y=1 --> T>0, if z=0 --> y=0
                    for l in location_ids:
                        model.Add(t[j,k,g] > 0).OnlyEnforceIf(y[l,j,k,g])
                        model.Add(y[l,j,k,g] == 0).OnlyEnforceIf(z[j,k,g].Not())

        # Staff availability
        for i in staff_ids:
            unavailable_time_slots = self.staff_unavailable_time_slots.get(i, [])
            for k in unavailable_time_slots:
                for j in activity_ids:
                    for g in group_ids:
                        model.Add(x[i, j, k, g] == 0)

        # Ensure min required staff assigned to each activity
        for g in group_ids:
            for j in activity_ids:
                for k in self.time_slots:
                    # Min staff if z=1 (activity j is chosen)
                    required_staff = self.activity_df.loc[
                        self.activity_df["activityID"] == j,
                        "numStaffReq"
                    ].values[0]

                    model.Add(t[j, k, g] >= required_staff).OnlyEnforceIf(z[j, k, g])
                    model.Add(t[j, k, g] == 0).OnlyEnforceIf(z[j, k, g].Not())

        # Staff can only be assigned if they can lead or assist
        for g in group_ids:
            for i in staff_ids:
                # Combine the sets of leads + assists
                can_participate_set = set(leads_mapping.get(i,[])) | set(assists_mapping.get(i,[]))
                for j in activity_ids:
                    for k in self.time_slots:
                        if j not in can_participate_set:
                            model.Add(x[i, j, k, g] == 0)

        # At least one staff assigned who can lead each activity
        for g in group_ids:
            for j in activity_ids:
                for k in self.time_slots:
                    leads_assigned = sum(
                        x[i, j, k, g] for i in staff_ids if j in leads_mapping.get(i, [])
                    )
                    # if z=1 --> leads_assigned >=1
                    model.Add(leads_assigned >= 1).OnlyEnforceIf(z[j, k, g])

        # Waterfront scheduled at same times each week per group, only activity in that time slot
        for g, timeslots in waterfront_schedule.items():
            for k in timeslots:
                # 1) Must schedule waterfront
                model.Add(z[waterfront_id, k, g] == 1)
                # 2) No other activities in that time slot
                model.Add(sum(z[j,k,g] for j in activity_ids) == 1)

        # Empty objective function (currently no optimization)
        model.Minimize(0)

        # Solve the model
        solver = cp_model.CpSolver()
        status = solver.Solve(model)

        # Extract Results
        if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
            schedule = []

            if status in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
                for g in group_ids:
                    for j in activity_ids:
                        for k in self.time_slots:
                            # Collect all staff i assigned
                            assigned_staff_ids = [i for i in staff_ids if solver.Value(x[i, j, k, g]) == 1]

                            if assigned_staff_ids:
                                # That means (j,k,g) is actually chosen (z=1) and has staff

                                # Find assigned location exactly once
                                assigned_location = None
                                for l in location_ids:
                                    if solver.Value(y[l, j, k, g]) == 1:
                                        assigned_location = l
                                        break

                                # Convert staff IDs to staff names
                                assigned_staff_names = []
                                for i in assigned_staff_ids:
                                    name = self.staff_df.loc[self.staff_df["staffID"] == i, "staffName"].values[0]
                                    assigned_staff_names.append(name)

                                # Convert IDs to activity/location names
                                activity_name = self.activity_df.loc[
                                    self.activity_df["activityID"] == j,
                                    "activityName"
                                ].values[0]
                                location_name = self.location_df.loc[
                                    self.location_df["locID"] == assigned_location,
                                    "locName"
                                ].values[0]

                                schedule.append({
                                    "activity": activity_name,
                                    "staff": assigned_staff_names,  # list of all staff
                                    "location": location_name,
                                    "time_slot": k,
                                    "group": g
                                })

                return schedule
        else:
            raise ValueError("No feasible solution found.")

# Usage
if __name__ == "__main__":
    # Initialize DataManager
    manager = DataManager(data_dir="data")

    # Load and validate data
    manager.load_all_csvs()
    manager.validate_all()

    # Extract DataFrames
    staff_df = manager.get_dataframe("staff")
    activity_df = manager.get_dataframe("activity")
    location_df = manager.get_dataframe("location")
    location_options_df = manager.get_dataframe("locOptions")
    group_df = manager.get_dataframe("groups")
    off_days_df = manager.get_dataframe("offDays")
    trips_ooc_df = manager.get_dataframe("tripsOOC")
    leads_df = manager.get_dataframe("leads")
    assists_df = manager.get_dataframe("assists")

    # Create leads and assists mapping
    leads_mapping = leads_df.groupby('staffID')['activityID'].apply(list).to_dict()
    assists_mapping = assists_df.groupby('staffID')['activityID'].apply(list).to_dict()

    # Map dates to time slots for off_days and trips_ooc
    off_days = off_days_df.groupby("staffID")["date"].apply(list).to_dict()
    staff_off_time_slots = {staff_id: map_dates_to_time_slots(dates) for staff_id, dates in off_days.items()}

    trips = trips_ooc_df.groupby("staffID")["date"].apply(list).to_dict()
    staff_trip_time_slots = {staff_id: map_dates_to_time_slots(dates) for staff_id, dates in trips.items()}

    # Combine unavailable time slots for each staff member
    staff_unavailable_time_slots = {}

    for staff_id in set(staff_off_time_slots.keys()).union(staff_trip_time_slots.keys()):
        off_time_slots = staff_off_time_slots.get(staff_id, [])
        trip_time_slots = staff_trip_time_slots.get(staff_id, [])
        staff_unavailable_time_slots[staff_id] = set(off_time_slots).union(trip_time_slots)

    # Extract Group IDs
    group_ids = group_df["groupID"].tolist()

    time_slots = [
        ("Monday", 1), ("Monday", 2), ("Monday", 3),
        ("Tuesday", 1), ("Tuesday", 2), ("Tuesday", 3),
        ("Wednesday", 1), ("Wednesday", 2), ("Wednesday", 3),
        ("Thursday", 1), ("Thursday", 2), ("Thursday", 3),
        ("Friday", 1), ("Friday", 2), ("Friday", 3),
        ("Saturday", 1), ("Saturday", 2), ("Saturday", 3)
    ]

    waterfront_schedule = {
        1: [("Tuesday", 3), ("Wednesday", 3), ("Friday", 3), ("Saturday", 3)],
        2: [("Monday", 2), ("Tuesday", 2), ("Thursday", 2), ("Saturday", 2)],
        3: [("Monday", 3), ("Wednesday", 2), ("Friday", 2), ("Saturday", 1)],
        4: [("Monday", 1), ("Wednesday", 1), ("Thursday", 1), ("Friday", 1)]
    }

    scheduler = Scheduler(staff_df, activity_df, location_df, location_options_df, group_df, time_slots, staff_unavailable_time_slots, leads_mapping, assists_mapping, waterfront_schedule)
    try:
        schedule = scheduler.solve()

        # Parse schedule into DataFrame for easier sorting
        schedule_df = pd.DataFrame(schedule)

        # Sort the schedule based on the order of time_slots
        schedule_df['time_slot'] = pd.Categorical(schedule_df['time_slot'], categories = time_slots, ordered=True)
        sorted_schedule = schedule_df.sort_values(by=['time_slot', 'group'])


        # Print sorted schedule by time slot
        print("Optimized Schedule:")
        for time_slot in time_slots:
            time_slot_df = sorted_schedule[sorted_schedule['time_slot'] == time_slot]
            if not time_slot_df.empty:
                print(f"\nTime Slot: {time_slot[0]}, Period: {time_slot[1]}")
                for _, row in time_slot_df.iterrows():
                    print(
                        f" Group: {row['group']}, "
                        f"Activity: {row['activity']}, "
                        f"Staff: {row['staff']}, "
                        f"Location: {row['location']}"
                    )

        # Run tests on schedule
        schedule_df = schedule_df.explode('staff')
        run_tests(schedule_df, group_ids, location_options_df, staff_unavailable_time_slots, staff_df, activity_df, leads_mapping, assists_mapping, waterfront_schedule)

    except ValueError as e:
        print(f"Error: {e}")
