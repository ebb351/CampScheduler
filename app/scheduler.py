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
    def __init__(self, staff_df, activity_df, location_df, location_options_df, group_df, time_slots, staff_unavailable_time_slots):
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

    def solve(self):
        # Extract IDs
        staff_ids = self.staff_df["staffID"].tolist()
        activity_ids = self.activity_df["ActivityID"].tolist()
        location_ids = self.location_df["locID"].tolist()
        group_ids = self.group_df["groupID"].tolist()

        # Create the model
        model = cp_model.CpModel()

        # Decision variables
        x = {} # Group specific staff assignment: x[i: staff, j: activity, k: time slot]
        y = {} # Group specific location assignment y[l: location, j: activity, k: time slot ]


        for g in group_ids:
            for i in staff_ids:
                for j in activity_ids:
                    for k in self.time_slots:
                        x[i,j,k, g] = model.NewBoolVar(f'x[{i},{j},{k[0]}, {k[1]},{g}]')

            for l in location_ids:
                for j in activity_ids:
                    for k in self.time_slots:
                        y[l,j,k, g] = model.NewBoolVar(f'y[{l},{j},{k[0]}, {k[1]},{g}]')

        # CONSTRAINTS:
        # Activity exclusivity across groups in the same time slot
        for j in activity_ids:
            for k in self.time_slots:
                model.Add(
                    sum(x[i,j,k,g] for i in staff_ids for g in group_ids) <= 1
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
                    sum(y[l,j,k,g] for j in activity_ids for g in group_ids) <= 1
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
                    model.Add(
                        sum(valid_loc_vars) == sum(x[i,j,k,g] for i in staff_ids)
                    )

        # Group-specific activity assignment (3-4 activities per time slot)
        for g in group_ids:
            for k in self.time_slots:
                model.Add(
                    sum(x[i,j,k,g] for i in staff_ids for j in activity_ids) == 4
                )

        # Link staff, location, and activity assignments
        for g in group_ids:
            for j in activity_ids:
                for k in self.time_slots:
                    model.Add(
                        sum(x[i,j,k,g] for i in staff_ids) == sum(y[l,j,k,g] for l in location_ids)
                    )

        # Staff availability
        for i in staff_ids:
            unavailable_time_slots = self.staff_unavailable_time_slots.get(i, [])
            for k in unavailable_time_slots:
                for j in activity_ids:
                    for g in group_ids:
                        model.Add(x[i, j, k, g] == 0)

        # Empty objective function (currently no optimization)
        model.Minimize(0)

        # Solve the model
        solver = cp_model.CpSolver()
        status = solver.Solve(model)

        # Extract Results
        if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
            schedule = []
            for g in group_ids:
                for i in staff_ids:
                    for j in activity_ids:
                        for k in self.time_slots:
                            if solver.Value(x[i,j,k,g]) == 1:
                                # Find assigned location
                                assigned_location = None
                                for l in location_ids:
                                    if solver.Value(y[l,j,k,g ]) == 1:
                                        assigned_location = l
                                        break

                                # Map IDs to names
                                activity_name = self.activity_df.loc[self.activity_df["ActivityID"] == j, "ActivityName"].values[0]
                                staff_name = self.staff_df.loc[self.staff_df["staffID"] == i, "staffName"].values[0]
                                location_name = self.location_df.loc[self.location_df["locID"] == assigned_location, "locName"].values[0]

                                schedule.append({
                                    "activity": activity_name,
                                    "staff": staff_name,
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

    scheduler = Scheduler(staff_df, activity_df, location_df, location_options_df, group_df, time_slots, staff_unavailable_time_slots)
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
        run_tests(schedule, group_ids, location_options_df, staff_unavailable_time_slots, staff_df)

    except ValueError as e:
        print(f"Error: {e}")
