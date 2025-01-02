from ortools.sat.python import cp_model
from data_manager import DataManager

class Scheduler:
    def __init__(self, staff_df, activity_df, location_df, time_slots):
        """
        Initialize the Scheduler.
        :param staff_df: List of staff names and IDs
        :param activity_df: List of activity IDs and their metadata
        :param location_df: List of location names and IDs
        :param time_slots: List of available time slots
        """
        self.staff_df = staff_df
        self.activity_df = activity_df
        self.location_df = location_df
        self.time_slots = time_slots

    def solve(self):
        # Extract IDs
        staff_ids = self.staff_df["staffID"].tolist()
        activity_ids = self.activity_df["ActivityID"].tolist()
        location_ids = self.location_df["locID"].tolist()

        # Create the model
        model = cp_model.CpModel()

        # Decision variables
        # Staff assignment: x[i: staff, j: activity, k: time slot]
        x = {}
        for i in staff_ids:
            for j in activity_ids:
                for k in self.time_slots:
                    x[i,j,k] = model.NewBoolVar(f'x[{i},{j},{k}]')

        # Location assignment y[l: location, j: activity, k: time slot ]
        y = {}
        for l in location_ids:
            for j in activity_ids:
                for k in self.time_slots:
                    y[l,j,k] = model.NewBoolVar(f'y[{l},{j},{k}]')

        # Constraints
        # Each activity is assigned to one staff member and one time slot
        for j in activity_ids:
            model.Add(
                sum(x[i,j,k] for i in staff_ids for k in self.time_slots) == 1
            )

        # Each activity is assigned to one location and one time slot
        for j in activity_ids:
            model.Add(
                sum(y[l,j,k] for l in location_ids for k in self.time_slots) == 1
            )

        # Link staff and location assignments
        for j in activity_ids:
            for k in self.time_slots:
                model.Add(
                    sum(x[i,j,k] for i in staff_ids) == sum(y[l,j,k] for l in location_ids)
                )

        # Empty objective function (currently no optimization)
        model.Minimize(0)

        # Solve the model
        solver = cp_model.CpSolver()
        status = solver.Solve(model)

        # Extract Results
        if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
            schedule = []
            for i in staff_ids:
                for j in activity_ids:
                    for k in self.time_slots:
                        if solver.Value(x[i,j,k]) == 1:
                            # Find assigned location
                            assigned_location = None
                            for l in location_ids:
                                if solver.Value(y[l,j,k]) == 1:
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

    time_slots = [
        "Monday, 1", "Monday, 2", "Monday, 3",
        "Tuesday, 1", "Tuesday, 2", "Tuesday, 3",
        "Wednesday, 1", "Wednesday, 2", "Wednesday, 3",
        "Thursday, 1", "Thursday, 2", "Thursday, 3",
        "Friday, 1", "Friday, 2", "Friday, 3",
        "Saturday, 1", "Saturday, 2", "Saturday, 3"
    ]

    scheduler = Scheduler(staff_df, activity_df, location_df, time_slots)
    try:
        schedule = scheduler.solve()
        print("Optimized Schedule:")
        for assignment in schedule:
            print(
                f"Activity: {assignment['activity']}, "
                f"Staff: {assignment['staff']}, "
                f"Location: {assignment['location']}, "
                f"Time Slot: {assignment['time_slot']}"
            )
    except ValueError as e:
        print(f"Error: {e}")
