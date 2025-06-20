from ortools.sat.python import cp_model
from data_manager import DataManager
from schedule_tests import run_tests
from datetime import datetime
import calendar
import pandas as pd
import time
import os
from hyperparameters import OPTIMIZATION_WEIGHTS, SOLVER_TIME_LIMIT

def map_dates_to_time_slots(dates):
    """
    Converts calendar dates to day-of-week time slots used in the schedule model.
    Each date is transformed into multiple time slots (one for each period in the day).
    
    :param dates: List of dates in MM/DD/YYYY format
    :return: List of time slots in (day_name, period) format
    """
    time_slots_map = []

    for date_str in dates:
        date_dt = datetime.strptime(date_str, "%m/%d/%Y")
        # day_of_week_number is 0 for Monday, 6 for Sunday
        day_of_week_number = date_dt.weekday()
        day_name = calendar.day_name[day_of_week_number]

        # Skip sundays since never on schedule
        if day_name == "Sunday":
            continue

        # Otherwise, build the three time slots
        for period in range(1,4):
            time_slots_map.append((day_name, period))

    return time_slots_map

class Scheduler:
    def __init__(self, staff_df, activity_df, location_df, location_options_df, group_df, time_slots,
                 staff_off_time_slots, leads_mapping, assists_mapping, waterfront_schedule, allowed_dr_days, staff_trips,
                 optimization_weights=None):
        """
        Initialize the Scheduler with all necessary camp data.
        
        :param staff_df: DataFrame containing staff information (names and IDs)
        :param activity_df: DataFrame containing activities and their requirements
        :param location_df: DataFrame containing location information
        :param location_options_df: DataFrame mapping activities to their possible locations
        :param group_df: DataFrame containing camper group information
        :param time_slots: List of all available time slots in format (day, period)
        :param staff_off_time_slots: Dictionary mapping staff IDs to unavailable time slots
        :param leads_mapping: Dictionary mapping staff IDs to activities they can lead
        :param assists_mapping: Dictionary mapping staff IDs to activities they can assist with
        :param waterfront_schedule: Dictionary mapping group IDs to their waterfront time slots
        :param allowed_dr_days: List of days when driving range is permitted
        :param staff_trips: Dictionary mapping staff IDs to their trip assignments
        :param optimization_weights: Dictionary of weights for optimization objectives
            - staff_diversity: weight for staff activity diversity objective
            - group_diversity: weight for group activity category diversity objective
        """
        self.staff_df = staff_df
        self.activity_df = activity_df
        self.location_df = location_df
        self.location_options_df = location_options_df
        self.group_df = group_df
        self.time_slots = time_slots
        self.staff_off_time_slots = staff_off_time_slots
        self.leads_mapping = leads_mapping
        self.assists_mapping = assists_mapping
        self.waterfront_schedule = waterfront_schedule
        self.allowed_dr_days = allowed_dr_days
        self.staff_trips = staff_trips
        
        # Default optimization weights if none provided
        if optimization_weights is None:
            self.optimization_weights = {
                'staff_diversity': 0.5,   # Weight for staff activity diversity
                'group_diversity': 1.0,   # Weight for group activity category diversity
                'group_weekly_diversity': 0.5, # Weight for group unique activity diversity per week
                'unassigned_periods_balance': 0.25 # Balances unassigned periods for staff
            }
        else:
            self.optimization_weights = optimization_weights

    def solve(self):
        """
        Builds and solves the constraint satisfaction problem for camp scheduling.
        Returns a complete schedule if a feasible solution is found.
        
        :return: List of dictionaries containing schedule entries
        :raises: ValueError if no feasible solution is found
        """
        # Extract all entity IDs from DataFrames
        staff_ids = self.staff_df["staffID"].tolist()
        activity_ids = self.activity_df["activityID"].tolist()
        location_ids = self.location_df["locID"].tolist()
        group_ids = self.group_df["groupID"].tolist()
        
        # Get IDs for special activities that have specific constraints
        waterfront_id = self.activity_df.loc[
            self.activity_df["activityName"] == "waterfront",
            "activityID"
        ].values[0]
        golf_id = self.activity_df.loc[self.activity_df["activityName"] == "golf", "activityID"].values[0]
        tennis_id = self.activity_df.loc[self.activity_df["activityName"] == "tennis", "activityID"].values[0]
        # Waterskiing (runs in tandem with waterfront)
        waterskiing_id = self.activity_df.loc[
            self.activity_df["activityName"].str.lower() == "waterskiing".lower(),
            "activityID"
        ].values[0]

        # Create a dictionary to map activity IDs to their categories
        activity_categories = {}
        for _, row in self.activity_df.iterrows():
            activity_categories[row['activityID']] = row['category']
        
        # Get unique activity categories
        unique_categories = self.activity_df['category'].unique().tolist()

        # Initialize the constraint programming model
        model = cp_model.CpModel()

        # DECISION VARIABLES:
        # staff_assign[i, j, k, g]: Whether staff i is assigned to activity j, 
        # in time slot k, for group g
        staff_assign = {}

        # loc_assign[l, j, k, g]: Whether location l is assigned to activity j,
        # in time slot k, for group g
        loc_assign = {}

        # staff_count[j, k, g]: The integer (0..N) of how many staff 
        # are assigned to activity j, time slot k, group g
        staff_count = {}

        # activity_chosen[j, k, g]: Boolean => if the activity j is "chosen" 
        # for time slot k, group g (meaning staff_count >= min req).
        activity_chosen = {}

        # golf_tennis_slot[k, g]: Boolean => "both golf & tennis simultaneously 
        # in slot k for group g"
        golf_tennis_slot = {}

        # inspection_slot[i,k]: Boolean => "staff i is assigned to inspection in time_slot k"
        inspection_slot = {}

        # driving_range[g, day]: Boolean => "driving range is scheduled for group g on day"
        driving_range_day = {}

        # driving_range_staff[g, day, i]: Boolean => "staff i is assigned to driving range for group g on day"
        driving_range_staff = {}

        # trip_assign[i,k, trip_name] = 1 if staff i is assigned to trip_name at time k
        trip_assign = {}

        # Create decision variables for staff assignments to activities
        for g in group_ids:
            for i in staff_ids:
                for j in activity_ids:
                    for k in self.time_slots:
                        staff_assign[i,j,k, g] = model.NewBoolVar(f'x[{i},{j},{k[0]}, {k[1]},{g}]')

            # Create decision variables for location assignments to activities
            for l in location_ids:
                for j in activity_ids:
                    for k in self.time_slots:
                        loc_assign[l,j,k, g] = model.NewBoolVar(f'y[{l},{j},{k[0]}, {k[1]},{g}]')

        # Create staff count variables and activity selection variables
        for g in group_ids:
            for j in activity_ids:
                for k in self.time_slots:
                    # Create an IntVar for total staff assigned to activity j, k, g
                    staff_count[j,k,g] = model.NewIntVar(
                        0,
                        len(staff_ids),
                        f't[{j},{k[0]}, {k[1]},{g}]'
                    )

                    # Constraint: Staff count equals sum of all staff assignments
                    model.Add(
                        staff_count[j,k,g] == sum(staff_assign[i,j,k,g] for i in staff_ids)
                    )

                    # Boolean variable indicating if activity j is chosen for time slot k and group g
                    activity_chosen[j,k,g] = model.NewBoolVar(
                        f'z[{j},{k[0]}, {k[1]},{g}]'
                    )

        # Create variables for golf and tennis scheduling (special case where they must be scheduled together)
        for g in group_ids:
            for k in self.time_slots:
                golf_tennis_slot[k,g] = model.NewBoolVar(f"both_golf_tennis_{k}_{g}")

        # Create variables for cabin inspection assignments (only in period 1)
        for i in staff_ids:
            for k in time_slots:
                if k[1] == 1: # period 1
                    inspection_slot[i,k] = model.NewBoolVar(f"inspection_{i}_{k}")
                else:
                    pass # no inspection in period 2 or 3

        # Create variables for driving range scheduling (special activity spanning two periods)
        for g in group_ids:
            for day in self.allowed_dr_days:
                driving_range_day[g, day] = model.NewBoolVar(f"driving_range_g{g}_{day}")
                for i in staff_ids:
                    driving_range_staff[g, day, i] = model.NewBoolVar(f"driving_range_g{g}_{day}_{i}")

        # Create variables for trip assignments (staff going on trips outside of camp)
        trip_name_list = set() # gather unique names from staff trips
        for i in staff_ids:
            if i not in self.staff_trips:
                continue
            for (k, trip_name) in self.staff_trips[i]:
                trip_name_list.add(trip_name)

        for i in staff_ids:
            if i not in self.staff_trips:
                continue
            for (k, trip_name) in self.staff_trips[i]:
                trip_assign[i,k, trip_name] = model.NewBoolVar(f"trip_{i}_{k[0]}_{k[1]}_{trip_name}")

        #########################################
        # OPTIMIZATION VARIABLES - STARTS HERE
        #########################################
        
        # 1. Staff Total Assignments
        # Calculate total assignments for each staff member for use in other optimization variables
        staff_total_assignments = {}
        for i in staff_ids:
            # Count all regular activity assignments
            staff_total_assignments[i] = model.NewIntVar(
                0, 
                len(activity_ids) * len(self.time_slots) * len(group_ids), 
                f'staff_total_assignments_{i}'
            )
            
            # Sum all assignments for this staff member across all activities, time slots, and groups
            model.Add(
                staff_total_assignments[i] == sum(
                    staff_assign[i,j,k,g] 
                    for j in activity_ids 
                    for k in self.time_slots 
                    for g in group_ids
                )
            )
        
        # 2. Staff Activity Diversity Variables
        # For each staff member and activity, count how many times they're assigned to that activity
        staff_activity_count = {}
        max_activity_count = len(self.time_slots) * len(group_ids)  # Maximum possible repetitions
        
        for i in staff_ids:
            for j in activity_ids:
                staff_activity_count[i,j] = model.NewIntVar(0, max_activity_count, f'staff_activity_count_{i}_{j}')
                
                # Sum all assignments of staff i to activity j across all time slots and groups
                model.Add(
                    staff_activity_count[i,j] == sum(
                        staff_assign[i,j,k,g] 
                        for k in self.time_slots 
                        for g in group_ids
                    )
                )
        
        # Penalize activity repetitions: count cases where staff does same activity MORE THAN 4 TIMES
        # (changed from the original implementation that penalized beyond 1 repetition)
        staff_repeated_activities = model.NewIntVar(0, len(staff_ids) * len(activity_ids) * max_activity_count, 'staff_repeated_activities')
        
        # Sum up all the activity counts that are greater than 4
        repeated_activity_terms = []
        for i in staff_ids:
            for j in activity_ids:
                # Create a variable that's max(0, staff_activity_count[i,j] - 4)
                excess_count = model.NewIntVar(0, max_activity_count - 4, f'excess_count_{i}_{j}')
                
                # If staff_activity_count[i,j] > 4, we want to count the excess (repetitions)
                # staff_activity_count[i,j] - 4 if positive, otherwise 0
                excess_indicator = model.NewBoolVar(f'excess_indicator_{i}_{j}')
                model.Add(staff_activity_count[i,j] >= 5).OnlyEnforceIf(excess_indicator)
                model.Add(staff_activity_count[i,j] <= 4).OnlyEnforceIf(excess_indicator.Not())
                
                model.Add(excess_count == staff_activity_count[i,j] - 4).OnlyEnforceIf(excess_indicator)
                model.Add(excess_count == 0).OnlyEnforceIf(excess_indicator.Not())
                
                repeated_activity_terms.append(excess_count)
        
        model.Add(staff_repeated_activities == sum(repeated_activity_terms))
        
        # 3. Group Activity Diversity Variables
        # Track category diversity for each group in each time slot
        
        # For each group, day, period, and category, track if that category is represented
        group_has_category = {}
        days = list(set(k[0] for k in self.time_slots))
        periods = list(set(k[1] for k in self.time_slots))
        
        # Filter out "fixed" category (waterfront) from optimization
        optimizable_categories = [cat for cat in unique_categories if cat != "fixed"]
        
        for g in group_ids:
            for day in days:
                for period in periods:
                    for category in optimizable_categories:
                        time_slot = (day, period)
                        if time_slot in self.time_slots:  # Check if this time slot exists
                            group_has_category[g, day, period, category] = model.NewBoolVar(
                                f'group_has_category_{g}_{day}_{period}_{category}'
                            )
                            
                            # Calculate if group g has any activity in this category during this time slot
                            category_activities = [j for j in activity_ids if activity_categories.get(j) == category]
                            
                            # If any activity in this category is chosen, set group_has_category to 1
                            model.Add(
                                sum(activity_chosen[j, time_slot, g] for j in category_activities) >= 1
                            ).OnlyEnforceIf(group_has_category[g, day, period, category])
                            
                            model.Add(
                                sum(activity_chosen[j, time_slot, g] for j in category_activities) == 0
                            ).OnlyEnforceIf(group_has_category[g, day, period, category].Not())
        
        # Count total category variety across all groups, days, and periods
        # Only considering optimizable categories (excluding fixed/waterfront)
        group_category_variety = model.NewIntVar(0, len(group_ids) * len(days) * len(periods) * len(optimizable_categories), 
                                               'group_category_variety')
        
        model.Add(
            group_category_variety == sum(
                group_has_category[g, day, period, category]
                for g in group_ids
                for day in days
                for period in periods
                for category in optimizable_categories
                if (day, period) in self.time_slots  # Only count valid time slots
            )
        )
        
        # 4. Group Weekly Unique Activity Diversity Variables
        # For each group and activity, track if the group does that activity at least once a week
        group_has_activity_weekly = {}
        for g in group_ids:
            for j in activity_ids:
                group_has_activity_weekly[g, j] = model.NewBoolVar(
                    f'group_has_activity_weekly_{g}_{j}'
                )
                
                # Sum of occurrences of activity j for group g throughout the week
                sum_activity_occurrences_for_group_week = sum(
                    activity_chosen[j, k, g] for k in self.time_slots
                )
                
                # Link group_has_activity_weekly to sum_activity_occurrences_for_group_week
                # If sum >= 1, group_has_activity_weekly must be true
                model.Add(sum_activity_occurrences_for_group_week >= 1).OnlyEnforceIf(group_has_activity_weekly[g, j])
                # If sum == 0, group_has_activity_weekly must be false
                model.Add(sum_activity_occurrences_for_group_week == 0).OnlyEnforceIf(group_has_activity_weekly[g, j].Not())

        # Total count of unique group-activity pairs for the week
        total_group_weekly_activity_diversity = model.NewIntVar(
            0, 
            len(group_ids) * len(activity_ids), 
            'total_group_weekly_activity_diversity'
        )
        model.Add(
            total_group_weekly_activity_diversity == sum(
                group_has_activity_weekly[g, j]
                for g in group_ids
                for j in activity_ids
            )
        )

        # 5. Staff Unassigned Periods Balance
        # Objective to have each staff member have approximately 2 unassigned periods per week
        target_unassigned_periods = 2
        
        # Get all period 1 time slots for inspection calculation
        period_one_slots = [k for k in self.time_slots if k[1] == 1]

        unassigned_dev_terms = []
        for i in staff_ids:
            # Calculate available slots (not off, not on a trip)
            staff_off_slots = self.staff_off_time_slots.get(i, [])
            staff_trip_slots = [trip[0] for trip in self.staff_trips.get(i, [])]
            available_slots = [k for k in self.time_slots if k not in staff_off_slots and k not in staff_trip_slots]
            num_available_slots = len(available_slots)

            # Total periods worked by staff (activities + inspections)
            total_work_periods = model.NewIntVar(0, len(self.time_slots), f'total_work_periods_{i}')
            
            # Sum of activity assignments (already calculated in staff_total_assignments)
            # Sum of inspection assignments
            inspection_assignments = sum(inspection_slot[i, k] for k in period_one_slots)
            
            model.Add(total_work_periods == staff_total_assignments[i] + inspection_assignments)
            
            # Unassigned periods for this staff member
            unassigned_periods = model.NewIntVar(-len(self.time_slots), len(self.time_slots), f'unassigned_periods_{i}')
            model.Add(unassigned_periods == num_available_slots - total_work_periods)
            
            # Deviation from the target of 2 unassigned periods
            deviation = model.NewIntVar(0, len(self.time_slots), f'unassigned_dev_abs_{i}')
            model.AddAbsEquality(deviation, unassigned_periods - target_unassigned_periods)
            unassigned_dev_terms.append(deviation)

        # Sum of deviations for all staff
        total_unassigned_periods_deviation = model.NewIntVar(0, len(staff_ids) * len(self.time_slots), 'total_unassigned_periods_deviation')
        model.Add(total_unassigned_periods_deviation == sum(unassigned_dev_terms))

        #########################################
        # OPTIMIZATION VARIABLES - ENDS HERE
        #########################################

        ##############
        # CONSTRAINTS:
        ##############

        # Constraint 1: Activity exclusivity across groups in the same time slot
        # Each activity can be assigned to at most one group in a given time slot
        for j in activity_ids:
            for k in self.time_slots:
                model.Add(
                    sum(activity_chosen[j,k,g] for g in group_ids) <= 1
                )

        # Constraint 2: Staff non-overlap across activities and groups
        # Each staff member can be assigned to at most one activity across all groups in a time slot
        for i in staff_ids:
            for k in self.time_slots:
                model.Add(
                    sum(staff_assign[i,j,k,g] for j in activity_ids for g in group_ids) <= 1
                )

        # Constraint 3: Location non-overlap across activities and groups
        # Each location can be used for at most one activity across all groups in a time slot
        for l in location_ids:
            for k in self.time_slots:
                model.Add(
                    sum(loc_assign[l,j,k,g] for j in activity_ids for g in group_ids) <= 1
                )

        # Constraint 4: Activities only take place in valid locations
        # Create mapping of activityID to valid locationIDs from the location options DataFrame
        valid_locations = (
            self.location_options_df.groupby("activityID")["locID"]
            .apply(list)
            .to_dict()
        )
        
        # Ensure activities are only assigned to valid locations
        for g in group_ids:
            for j in activity_ids:
                for k in self.time_slots:
                    valid_loc_vars = [loc_assign[l,j,k,g] for l in valid_locations.get(j, [])]
                    # If activity is chosen, exactly one valid location must be assigned
                    # If activity is not chosen, no location should be assigned
                    model.Add(sum(valid_loc_vars) == activity_chosen[j,k,g])

        # Constraint 5: Group-specific activity assignment
        # Each group needs the right number of activities per time slot
        for g in group_ids:
            for k in self.time_slots:
                # Skip waterfront slots which have special handling
                if k in self.waterfront_schedule[g]:
                    continue # waterfront already handled

                # For regular time slots:
                # - If NOT a golf+tennis slot: each group gets exactly 4 activities
                # - If IS a golf+tennis slot: each group gets exactly 2 activities (golf and tennis)
                
                # Regular case: 4 activities when not golf+tennis slot
                model.Add(
                    sum(activity_chosen[j,k,g] for j in activity_ids) == 4
                ).OnlyEnforceIf(golf_tennis_slot[k, g].Not())

                # Special case: 2 activities when golf+tennis slot
                model.Add(
                    sum(activity_chosen[j,k,g] for j in activity_ids) == 2
                ).OnlyEnforceIf(golf_tennis_slot[k, g])

        # Constraint 6: Link staff, location, and activity assignments
        # Ensure proper relationships between activity selection, location assignment, and staffing
        for g in group_ids:
            for j in activity_ids:
                for k in self.time_slots:
                    # If activity j is chosen for (k,g), exactly one location must be assigned
                    model.Add(
                        sum(loc_assign[l,j,k,g] for l in location_ids) == 1
                    ).OnlyEnforceIf(activity_chosen[j,k,g])

                    # If activity j is not chosen for (k,g), no location should be assigned
                    model.Add(
                        sum(loc_assign[l,j,k,g] for l in location_ids) == 0
                    ).OnlyEnforceIf(activity_chosen[j,k,g].Not())

                    # Additional constraints for location assignment:
                    # - If a location is assigned to activity j, there must be staff assigned (count > 0)
                    # - If activity j is not chosen, no location can be assigned to it
                    for l in location_ids:
                        model.Add(staff_count[j,k,g] > 0).OnlyEnforceIf(loc_assign[l,j,k,g])
                        model.Add(loc_assign[l,j,k,g] == 0).OnlyEnforceIf(activity_chosen[j,k,g].Not())

        # Constraint 7: Staff availability
        # Staff cannot be assigned to activities during their time off
        for i in staff_ids:
            unavailable_time_slots = self.staff_off_time_slots.get(i, [])
            for k in unavailable_time_slots:
                # Staff cannot be assigned to any activity during their time off
                for j in activity_ids:
                    for g in group_ids:
                        model.Add(staff_assign[i, j, k, g] == 0)

        # Staff cannot be assigned to inspection during their time off
        for i in staff_ids:
            unavailable_time_slots = self.staff_off_time_slots.get(i, [])
            for k in unavailable_time_slots:
                if k in inspection_slots:
                    model.Add(inspection_slot[i,k] == 0)


        # Constraint 8: Minimum staffing requirements for activities
        # Each activity must have its required minimum number of staff when chosen
        for g in group_ids:
            for j in activity_ids:
                for k in self.time_slots:
                    # Get the minimum staff requirement for this activity from the activity DataFrame
                    required_staff = self.activity_df.loc[
                        self.activity_df["activityID"] == j,
                        "numStaffReq"
                    ].values[0]

                    # If activity is chosen, ensure minimum staff requirement is met
                    model.Add(staff_count[j, k, g] >= required_staff).OnlyEnforceIf(activity_chosen[j, k, g])
                    
                    # If activity is not chosen, ensure no staff are assigned
                    model.Add(staff_count[j, k, g] == 0).OnlyEnforceIf(activity_chosen[j, k, g].Not())

        # Constraint 9: Skill qualification for activities
        # Staff can only be assigned to activities they can lead or assist with
        for g in group_ids:
            for i in staff_ids:
                # Combine the sets of activities staff can lead or assist with
                can_participate_set = set(leads_mapping.get(i,[])) | set(assists_mapping.get(i,[]))
                for j in activity_ids:
                    for k in self.time_slots:
                        # If staff cannot lead or assist this activity, they cannot be assigned
                        if j not in can_participate_set:
                            model.Add(staff_assign[i, j, k, g] == 0)

        # Constraint 10: Leadership requirement for activities
        # Each activity must have at least one staff who can lead it
        for g in group_ids:
            for j in activity_ids:
                for k in self.time_slots:
                    # Sum up all staff who can lead this activity
                    leads_assigned = sum(
                        staff_assign[i, j, k, g] for i in staff_ids if j in leads_mapping.get(i, [])
                    )
                    # If activity is chosen, ensure at least one staff can lead it
                    model.Add(leads_assigned >= 1).OnlyEnforceIf(activity_chosen[j, k, g])

        # Constraint 11: Waterfront scheduling
        # Waterfront must be scheduled at fixed times for each group and as the only activity
        for g, timeslots in self.waterfront_schedule.items():
            for k in timeslots:
                # 1) Must schedule waterfront in these designated slots
                model.Add(activity_chosen[waterfront_id, k, g] == 1)
                # Waterskiing must ALSO be scheduled in every waterfront slot
                model.Add(activity_chosen[waterskiing_id, k, g] == 1)

                # 2) Exactly TWO activities (waterfront + waterskiing) should be present in the slot – no more, no less
                model.Add(sum(activity_chosen[j,k,g] for j in activity_ids) == 2)

        # Constraint 12: Golf and Tennis pairing requirement
        # Golf and Tennis must be scheduled together in the same time slot
        # When they are scheduled together, they are the only two activities in that slot

        for g in group_ids:
            for k in time_slots:
                # When golf_tennis_slot is true, exactly 2 activities are chosen (golf and tennis)
                model.Add(
                    sum(activity_chosen[j, k, g] for j in activity_ids) == 2
                ).OnlyEnforceIf(golf_tennis_slot[k, g])

                # Ensure that when golf_tennis_slot is true, those two activities must be golf and tennis
                model.Add(activity_chosen[golf_id, k, g] + activity_chosen[tennis_id, k, g] == 2).OnlyEnforceIf(golf_tennis_slot[k, g])
                
                # When golf_tennis_slot is false, golf and tennis cannot both be scheduled
                # (at most one can be scheduled, or neither)
                model.Add(activity_chosen[golf_id, k, g] + activity_chosen[tennis_id, k, g] <= 1).OnlyEnforceIf(golf_tennis_slot[k, g].Not())

        # Constraint 13: Golf and Tennis frequency requirement
        # Each group must have the golf and tennis pairing at least twice per week
        for g in group_ids:
            model.Add(
                sum(golf_tennis_slot[k, g] for k in time_slots) >= 2
            )

        # Constraint 14: Daily golf and tennis limit
        # Golf and Tennis pairing can appear at most once per day for each group
        day_map = {}  # Map time slots to their day of the week
        for k in time_slots:
            day_map[k] = k[0]  # k[0] contains the day name
            
        days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
        for g in group_ids:
            for d in days:
                # Get all time slots for the current day
                day_slots = [k for k in time_slots if day_map[k] == d]

                # Limit golf + tennis pairing to at most once per day per group
                model.Add(
                    sum(golf_tennis_slot[k, g] for k in day_slots) <= 1
                )

        # Constraint 15: Daily cabin inspection requirement
        # Exactly one staff member must be assigned to cabin inspection each day during period 1
        days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
        for day in days:
            # Create the period 1 time slot for this day
            day_slot = (day, 1)
            
            # Ensure exactly one staff is assigned to inspection
            model.Add(
                sum(inspection_slot[i,day_slot] for i in staff_ids) == 1
            )

        # Constraint 16: Inspection and activity exclusivity
        # Staff cannot be assigned to both inspection and regular activities in the same time slot
        for i in staff_ids:
            for k in time_slots:
                if k[1] == 1:  # Only period 1 has inspections
                    model.Add(
                        sum(staff_assign[i,j,k,g] for j in activity_ids for g in group_ids) + inspection_slot[i,k] <= 1
                    )
                else:
                    pass  # No inspection in periods 2 or 3, so no constraint needed

        # Constraint 17: Driving range frequency requirement
        # Each group must have driving range exactly once per week on an allowed day
        for g in group_ids:
            model.Add(
                sum(driving_range_day[g, day] for day in self.allowed_dr_days) == 1
            )

        # Constraint 18: Driving range scheduling restrictions
        # Get the driving range activity ID
        driving_range_id = self.activity_df.loc[
            self.activity_df["activityName"] == "driving range",
            "activityID"
        ].values[0]

        # Driving Range can only be scheduled during periods 1 and 2 on allowed days
        for g in group_ids:
            for j in activity_ids:
                if j == driving_range_id:
                    for k in self.time_slots:
                        day, period = k
                        # If not an allowed day or period, driving range cannot be scheduled
                        if day not in self.allowed_dr_days or period not in [1, 2]:
                            model.Add(activity_chosen[j, k, g] == 0)

        # Constraint 19: Driving range period continuity
        # Driving range must be scheduled for both periods 1 and 2 on the same day
        for g in group_ids:
            for day in self.allowed_dr_days:
                k1 = (day, 1)  # Period 1 slot
                k2 = (day, 2)  # Period 2 slot
                dr_day_var = driving_range_day[g, day]  # Boolean variable for driving range on this day

                # If driving range is scheduled on this day, it must be in both periods 1 and 2
                model.Add(activity_chosen[driving_range_id, k1, g] == 1).OnlyEnforceIf(dr_day_var)
                model.Add(activity_chosen[driving_range_id, k2, g] == 1).OnlyEnforceIf(dr_day_var)

                # If driving range is not scheduled on this day, it must not be in either period
                model.Add(activity_chosen[driving_range_id, k1, g] == 0).OnlyEnforceIf(dr_day_var.Not())
                model.Add(activity_chosen[driving_range_id, k2, g] == 0).OnlyEnforceIf(dr_day_var.Not())

                # Constraint 20: Driving range staffing requirements
                # At least one staff must be assigned to driving range when it's scheduled
                model.Add(
                    sum(driving_range_staff[g, day, i] for i in staff_ids) >= 1
                ).OnlyEnforceIf(dr_day_var)

                # If driving range is not scheduled, no staff should be assigned to it
                model.Add(
                    sum(driving_range_staff[g, day, i] for i in staff_ids) == 0
                ).OnlyEnforceIf(dr_day_var.Not())

                # Constraint 21: Driving range staff continuity
                # Staff assigned to driving range must work both periods 1 and 2
                for i in staff_ids:
                    # Link the driving range staff variables to the actual staff assignments
                    model.Add(
                        staff_assign[i, driving_range_id, k1, g] == driving_range_staff[g, day, i]
                    ).OnlyEnforceIf(dr_day_var)
                    model.Add(
                        staff_assign[i, driving_range_id, k2, g] == driving_range_staff[g, day, i]
                    ).OnlyEnforceIf(dr_day_var)

                    # If driving range is not scheduled, ensure no staff assignments
                    model.Add(
                        staff_assign[i, driving_range_id, k1, g] == 0
                    ).OnlyEnforceIf(dr_day_var.Not())
                    model.Add(
                        staff_assign[i, driving_range_id, k2, g] == 0
                    ).OnlyEnforceIf(dr_day_var.Not())

                    # Constraint 22: Staff availability for driving range
                    # Staff can only be assigned to driving range if available for both periods
                    unavailable_time_slots = self.staff_off_time_slots.get(i, [])
                    if k1 in unavailable_time_slots or k2 in unavailable_time_slots:
                        # If staff is unavailable in either period, they cannot be assigned to driving range
                        model.Add(driving_range_staff[g, day, i] == 0)

        # Constraint 23: Trip assignment enforcement
        # Staff members must be assigned to trips listed in the trips data
        for i in staff_ids:
            if i not in self.staff_trips:
                continue

            for (k, trip_name) in self.staff_trips[i]:
                # Force assignment of staff to their scheduled trips
                model.Add(
                    trip_assign[i,k, trip_name] == 1
                )

        # Constraint 24: Trip exclusivity
        # Staff on trips cannot be assigned to other activities or inspection
        for i in staff_ids:
            if i not in self.staff_trips:
                continue

            for (k, trip_name) in self.staff_trips[i]:
                # Staff on trips cannot be assigned to any regular activities
                model.Add(
                    sum(staff_assign[i,j,k,g] for j in activity_ids for g in group_ids) == 0
                ).OnlyEnforceIf(trip_assign[i,k, trip_name])

                # Staff on trips cannot be assigned to inspection duty
                if k in inspection_slots:
                    model.Add(
                        inspection_slot[i,k] == 0
                    ).OnlyEnforceIf(trip_assign[i,k, trip_name])

        # Constraint 25: No group can have the same activity twice in the same day
        days = list(set(k[0] for k in self.time_slots)) # Extract unique days
        periods = list(set(k[1] for k in self.time_slots)) # Extract unique periods

        for g in group_ids:
            for j in activity_ids: # j is activityID
                # Check the duration of the activity
                activity_duration = self.activity_df.loc[self.activity_df["activityID"] == j, "duration"].iloc[0]
                
                # If the activity's duration is greater than 1, skip this constraint for this activity
                if activity_duration > 1:
                    continue

                for day in days:
                    # Sum of activity_chosen for this group, activity, on this day (across all periods)
                    daily_activity_occurrences = []
                    for period in periods:
                        time_slot = (day, period)
                        # Ensure the time slot exists before trying to access activity_chosen
                        if time_slot in self.time_slots:
                             daily_activity_occurrences.append(activity_chosen[j, time_slot, g])
                    
                    # Only add constraint if there are any occurrences for this day (i.e., list is not empty)
                    if daily_activity_occurrences:
                        model.Add(sum(daily_activity_occurrences) <= 1)

        # Constraint 26: Maximum staffing for activities
        # Each activity cannot have more staff than its maxStaff allows
        for j in activity_ids:
            # Get the max staff for this activity from the activity DataFrame
            max_staff = self.activity_df.loc[
                self.activity_df["activityID"] == j,
                "maxStaff"
            ].values[0]

            for g in group_ids:
                for k in self.time_slots:
                    # The number of staff assigned to an activity cannot exceed max_staff
                    model.Add(staff_count[j, k, g] <= max_staff)

        ##############################################
        # Constraint 11A: Waterskiing limited to waterfront slots only
        ##############################################
        for g in group_ids:
            for k in self.time_slots:
                if k not in self.waterfront_schedule.get(g, []):
                    # Waterskiing cannot be scheduled outside waterfront periods
                    model.Add(activity_chosen[waterskiing_id, k, g] == 0)

        ##############################################
        # Constraint 11B: Waterskiing staff daily continuity
        # If a staff member works waterskiing at any waterfront period in a day,
        # they must work ALL waterskiing periods that day (across groups).
        ##############################################
        days_list_ws = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]

        # Pre-compute waterfront/waterskiing slots by day for easier reference
        waterski_slots_by_day = {d: [] for d in days_list_ws}
        for g_tmp, slots_tmp in self.waterfront_schedule.items():
            for slot in slots_tmp:
                waterski_slots_by_day[slot[0]].append((slot, g_tmp))

        # Create helper boolean vars indicating whether a staff member is on waterski duty for a given day
        waterski_staff_day = {}
        for i in staff_ids:
            for d in days_list_ws:
                waterski_staff_day[i, d] = model.NewBoolVar(f"waterski_staff_day_{i}_{d}")

                slots_pairs = waterski_slots_by_day[d]

                if slots_pairs:
                    # Link individual waterski period assignments to the day-level boolean
                    for slot_k, grp_tmp in slots_pairs:
                        model.Add(staff_assign[i, waterskiing_id, slot_k, grp_tmp] == waterski_staff_day[i, d])
                else:
                    # No waterfront on this day – force the boolean to 0
                    model.Add(waterski_staff_day[i, d] == 0)

        # OBJECTIVE FUNCTION:
        # Combine all optimization objectives with weights
        
        # Define objective weights from the instance variable
        w_staff_diversity = self.optimization_weights['staff_diversity']
        w_group_diversity = self.optimization_weights['group_diversity']
        w_group_weekly_diversity = self.optimization_weights['group_weekly_diversity']
        w_unassigned_balance = self.optimization_weights['unassigned_periods_balance']
        
        # Build the objective function: 
        # - Minimize workload imbalance 
        # - Minimize staff activity repetitions
        # - Maximize group activity category diversity
        # - Maximize group unique activity diversity per week
        
        # Note: CP-SAT can only minimize, so we negate the terms we want to maximize
        model.Minimize(
            w_staff_diversity * staff_repeated_activities - 
            w_group_diversity * group_category_variety -
            w_group_weekly_diversity * total_group_weekly_activity_diversity +
            w_unassigned_balance * total_unassigned_periods_deviation
        )

        # Solve the constraint programming model
        solver = cp_model.CpSolver()
        
        # Set a time limit (in seconds) to prevent the solver from running indefinitely
        solver.parameters.max_time_in_seconds = SOLVER_TIME_LIMIT * 60  # Convert to seconds
        
        # Disable detailed logging but show basic progress
        solver.parameters.log_search_progress = False
        
        print("Solving optimization problem...")
        print(f"Time limit set to {solver.parameters.max_time_in_seconds/60} minutes")
        
        # Create a simple progress callback
        class SolutionCallback(cp_model.CpSolverSolutionCallback):
            """Simple callback to display optimization progress."""
            
            def __init__(self):
                cp_model.CpSolverSolutionCallback.__init__(self)
                self._solution_count = 0
                self._start_time = time.time()
                
            def on_solution_callback(self):
                """Called on each new solution."""
                current_time = time.time()
                obj = self.ObjectiveValue()
                self._solution_count += 1
                if self._solution_count % 10 == 0:  # Only print every 50th solution
                    print(f"  Solution {self._solution_count} | Objective: {obj} | Time: {current_time - self._start_time:.1f}s")
        
        callback = SolutionCallback()
        status = solver.Solve(model, callback)
        
        # Report solver status
        print("\nSolver completed with status:", end=" ")
        if status == cp_model.OPTIMAL:
            print("OPTIMAL - Found guaranteed optimal solution")
        elif status == cp_model.FEASIBLE:
            print("FEASIBLE - Found a valid solution, but optimality not guaranteed")
        elif status == cp_model.INFEASIBLE:
            print("INFEASIBLE - Problem has no solution")
        elif status == cp_model.MODEL_INVALID:
            print("MODEL_INVALID - Model is invalid")
        else:
            print(f"OTHER - Status code: {status}")
            
        # Report optimization metrics if a solution was found
        if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
            print(f"Time used by solver: {solver.WallTime():.2f} seconds")
            
            # If we have optimization variables in the model, report their values
            if hasattr(self, 'optimization_weights') and self.optimization_weights:
                print("\nOptimization metrics:")
                # Print optimization values - these variables are in the current scope
                print(f"- Staff activity repetitions: {solver.Value(staff_repeated_activities)}")
                print(f"- Group activity category variety: {solver.Value(group_category_variety)}")
                print(f"- Group weekly unique activities: {solver.Value(total_group_weekly_activity_diversity)}")
                print(f"- Staff unassigned periods deviation: {solver.Value(total_unassigned_periods_deviation)}")
                print(f"- Weighted objective value: {solver.ObjectiveValue()}")

        # EXTRACT RESULTS
        # Build the schedule if a feasible solution was found
        if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
            schedule = []

            # Process the solution to build a readable schedule
            for g in group_ids:
                for j in activity_ids:
                    # Skip driving range (handled separately)
                    if j == driving_range_id:
                        continue
                    for k in self.time_slots:
                        # Collect all staff assigned to this activity, time slot, and group
                        assigned_staff_ids = [i for i in staff_ids if solver.Value(staff_assign[i, j, k, g]) == 1]

                        # Only process activities that have staff assigned to them
                        if assigned_staff_ids:
                            # Find the assigned location for this activity
                            assigned_location = None
                            for l in location_ids:
                                if solver.Value(loc_assign[l, j, k, g]) == 1:
                                    assigned_location = l
                                    break

                            # Convert staff IDs to staff names
                            assigned_staff_names = []
                            for i in assigned_staff_ids:
                                name = self.staff_df.loc[
                                    self.staff_df["staffID"] == i, "staffName"
                                ].values[0]
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

                            # Add this activity to the schedule
                            schedule.append({
                                "activity": activity_name,
                                "staff": assigned_staff_names,  # list of all staff
                                "location": location_name,
                                "time_slot": k,
                                "group": g
                            })

            # Extract driving range assignments
            for g in group_ids:
                for day in self.allowed_dr_days:
                    # Check if driving range is scheduled for this group and day
                    if solver.Value(driving_range_day[g, day]) == 1:
                        k1 = (day, 1)  # Period 1
                        k2 = (day, 2)  # Period 2

                        # Find staff assigned to driving range
                        assigned_staff_ids = [
                            i for i in staff_ids
                            if solver.Value(driving_range_staff[g, day, i]) == 1
                        ]

                        if assigned_staff_ids:
                            # Get staff names
                            for i in assigned_staff_ids:
                                names = self.staff_df.loc[
                                    self.staff_df["staffID"] == i,
                                    "staffName"
                                ].values[0]

                            # Add driving range to schedule for both periods
                            schedule.append({
                                "activity": "driving range",
                                "staff": [names],
                                "location": "driving range",
                                "time_slot": k1,
                                "group": g
                            })
                            schedule.append({
                                "activity": "driving range",
                                "staff": [names],
                                "location": "driving range",
                                "time_slot": k2,
                                "group": g
                            })

            # Extract inspection assignments
            for k in inspection_slots:
                assigned_inspection_id = [i for i in staff_ids if solver.Value(inspection_slot[i,k]) == 1]
                if assigned_inspection_id:
                    # Get the name of the staff assigned to inspection
                    name = self.staff_df.loc[
                        self.staff_df["staffID"] == assigned_inspection_id[0],
                        "staffName"
                    ].values[0]

                    # Add inspection to the schedule
                    schedule.append({
                        "activity": "inspection",
                        "staff": [name],
                        "location": "NA",
                        "time_slot": k,
                        "group": "NA"
                    })

            # Extract trip assignments
            trip_assignments = {}  # Maps (trip_name, slot) to list of staff IDs

            # Collect staff for each trip
            for i in staff_ids:
                if i not in self.staff_trips:
                    continue
                trips_for_staff = self.staff_trips.get(i, [])
                for (slot, trip_name) in trips_for_staff:
                    key = (trip_name, slot)
                    if key not in trip_assignments:
                        trip_assignments[key] = []
                    trip_assignments[key].append(i)

            # Organize trip staff into a dictionary by trip and time slot
            trip_rows = {}
            for (trip_name, k), staff_list in trip_assignments.items():
                for i in staff_list:
                    if solver.Value(trip_assign[i,k,trip_name]) == 1:
                        if (trip_name, k) not in trip_rows:
                            trip_rows[(trip_name, k)] = []
                        trip_rows[(trip_name, k)].append(i)

            # Create schedule entries for trips
            for (trip_name, k), staff_ids in trip_rows.items():
                # Convert staff IDs to names
                staff_names = []
                for i in staff_ids:
                    name = self.staff_df.loc[
                        self.staff_df["staffID"] == i,
                        "staffName"
                    ].values[0]
                    staff_names.append(name)
                
                # Add trip to the schedule
                schedule.append({
                    "activity": trip_name,
                    "staff": staff_names,
                    "location": "NA",
                    "time_slot": k,
                    "group": "NA"
                })

            return schedule
        else:
            raise ValueError("No feasible solution found.")

def generate_staff_schedule_csv(schedule_df, staff_df, time_slots, staff_off_time_slots):
    """
    Generates a CSV file with schedules broken down by staff member.

    :param schedule_df: DataFrame containing the generated schedule.
    :param staff_df: DataFrame containing staff information.
    :param time_slots: List of all time slots in the schedule.
    :param staff_off_time_slots: Dictionary mapping staff IDs to lists of unavailable time slots.
    """
    output_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'staff_schedules')
    os.makedirs(output_dir, exist_ok=True)

    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
    periods = [1, 2, 3]
    
    staff_list = staff_df[['staffID', 'staffName']].to_dict('records')

    # Explode schedule_df to handle multiple staff per activity
    if 'staff' in schedule_df.columns and schedule_df['staff'].apply(lambda x: isinstance(x, list)).any():
        schedule_df_exploded = schedule_df.explode('staff')
    else:
        schedule_df_exploded = schedule_df

    data = []
    for staff_info in staff_list:
        staff_id = staff_info['staffID']
        staff_name = staff_info['staffName']
        
        staff_schedule_rows = []
        
        # Get staff's off slots
        off_slots = set(staff_off_time_slots.get(staff_id, []))

        for period in periods:
            row_data = {'Staff': staff_name if period == 1 else ''}
            
            for day in days:
                time_slot = (day, period)
                
                activity = '' # Default to blank
                if time_slot not in off_slots:
                    # Find activity for this staff, day, period
                    activity_info = schedule_df_exploded[
                        (schedule_df_exploded['staff'] == staff_name) &
                        (schedule_df_exploded['time_slot'] == time_slot)
                    ]
                    
                    if not activity_info.empty:
                        activity_name = activity_info['activity'].iloc[0]
                        group = activity_info['group'].iloc[0]
                        
                        # Rename volleyball to newcomb for groups 1 and 2
                        if str(activity_name).lower() == 'volleyball' and group in [1, 2]:
                            activity = 'newcomb'
                        else:
                            activity = activity_name
                
                row_data[day] = activity
            staff_schedule_rows.append(row_data)
        
        data.extend(staff_schedule_rows)
        # Add a blank row for line break, matching the requested format
        data.append({day: '' for day in ['Staff'] + days})

    # Create DataFrame and save to CSV
    if data:
        # Remove the last empty row
        data.pop()
        staff_schedule_df = pd.DataFrame(data, columns=['Staff'] + days)
        staff_schedule_df.to_csv(os.path.join(output_dir, "staff_schedule.csv"), index=False)

def generate_unassigned_staff_csv(schedule_df, staff_df, time_slots, staff_off_time_slots, staff_trips):
    """
    Generates a CSV file showing unassigned staff for each time slot.
    
    :param schedule_df: DataFrame containing the generated schedule
    :param staff_df: DataFrame containing staff information
    :param time_slots: List of all time slots in the schedule
    :param staff_off_time_slots: Dictionary mapping staff IDs to lists of unavailable time slots
    :param staff_trips: Dictionary mapping staff IDs to their trip assignments
    """
    output_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'staff_schedules')
    os.makedirs(output_dir, exist_ok=True)

    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
    periods = [1, 2, 3]
    
    # Create a DataFrame with periods as rows and days as columns
    unassigned_df = pd.DataFrame(index=periods, columns=days)
    
    # Explode schedule_df to handle multiple staff per activity
    if 'staff' in schedule_df.columns and schedule_df['staff'].apply(lambda x: isinstance(x, list)).any():
        schedule_df_exploded = schedule_df.explode('staff')
    else:
        schedule_df_exploded = schedule_df

    # For each time slot, find unassigned staff
    for day in days:
        for period in periods:
            time_slot = (day, period)
            
            # Get all staff names
            all_staff = set(staff_df['staffName'].tolist())
            
            # Remove staff who are off
            off_staff = set()
            for staff_id, off_slots in staff_off_time_slots.items():
                if time_slot in off_slots:
                    staff_name = staff_df.loc[staff_df['staffID'] == staff_id, 'staffName'].iloc[0]
                    off_staff.add(staff_name)
            
            # Remove staff who are on trips
            trip_staff = set()
            for staff_id, trips in staff_trips.items():
                if any(slot == time_slot for slot, _ in trips):
                    staff_name = staff_df.loc[staff_df['staffID'] == staff_id, 'staffName'].iloc[0]
                    trip_staff.add(staff_name)
            
            # Remove staff who are assigned to activities
            assigned_staff = set(schedule_df_exploded[
                schedule_df_exploded['time_slot'] == time_slot
            ]['staff'].tolist())
            
            # Calculate unassigned staff
            unassigned_staff = all_staff - off_staff - trip_staff - assigned_staff
            
            # Sort staff names for consistent output
            unassigned_staff = sorted(list(unassigned_staff))
            
            # Join staff names with newlines
            unassigned_df.at[period, day] = '\n'.join(unassigned_staff) if unassigned_staff else ''
    
    # Save to CSV
    unassigned_df.to_csv(os.path.join(output_dir, "staff_unassigned.csv"))

def generate_group_schedules_csv(schedule_df, group_ids):
    """
    Generates CSV files for each group's schedule.
    
    :param schedule_df: DataFrame containing the generated schedule
    :param group_ids: List of group IDs
    """
    output_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'group_schedules')
    os.makedirs(output_dir, exist_ok=True)

    # Prepare day and period lists
    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
    periods = [1, 2, 3]
    all_groups = group_ids + ["NA"]

    for group in all_groups:
        # Filter schedule for this group
        group_sched = schedule_df[schedule_df['group'] == group]
        # Build a DataFrame with periods as rows, days as columns
        sched_matrix = pd.DataFrame(index=periods, columns=days)
        for day in days:
            for period in periods:
                # Find all activities for this group, day, period
                acts = group_sched[(group_sched['time_slot'] == (day, period))]['activity'].tolist()
                
                # Rename volleyball to newcomb for groups 1 and 2
                if group in [1, 2]:
                    acts = ['newcomb' if str(act).lower() == 'volleyball' else act for act in acts]

                # Filter out "waterskiing" so it does not appear on group schedules
                acts = [act for act in acts if str(act).lower() != 'waterskiing']
                # Join activity names with newlines if multiple
                sched_matrix.at[period, day] = '\n'.join(acts) if acts else ''
        # Save to CSV
        group_name = f"group_{group}" if group != "NA" else "special_NA"
        sched_matrix.to_csv(os.path.join(output_dir, f"{group_name}_schedule.csv"))

# Main application entry point
if __name__ == "__main__":
    # Initialize the data manager with the data directory
    manager = DataManager(data_dir="data")

    # Load all CSV files and validate the data
    manager.load_all_csvs()
    manager.validate_all()

    # Extract DataFrames
    staff_df = manager.get_dataframe("staff")
    activity_df = manager.get_dataframe("activity")
    location_df = manager.get_dataframe("location")
    location_options_df = manager.get_dataframe("locOptions")
    group_df = manager.get_dataframe("groups")
    off_days_df = manager.get_dataframe("offDays")
    trips_df = manager.get_dataframe("trips")
    leads_df = manager.get_dataframe("leads")
    assists_df = manager.get_dataframe("assists")

    # Create leads and assists mapping
    leads_mapping = leads_df.groupby('staffID')['activityID'].apply(list).to_dict()
    assists_mapping = assists_df.groupby('staffID')['activityID'].apply(list).to_dict()

    # Map dates to time slots for off_days and trips_ooc
    off_days = off_days_df.groupby("staffID")["date"].apply(list).to_dict()
    staff_off_time_slots = {
        staff_id: map_dates_to_time_slots(dates)
        for staff_id, dates in off_days.items()
    }

    # Extract trip assignments mapping staff to trips
    staff_trips = {}

    for idx, row in trips_df.iterrows():
        staff_id = row["staffID"]
        trip_name = row["trip_name"]
        date_str = row["date"] # in MM/DD/YYYY
        start_period = row["start_period"]
        end_period = row["end_period"]

        # Convert date_str --> day_of_week (e.g. "Monday")
        date_dt = datetime.strptime(date_str, "%m/%d/%Y")
        dow_number = date_dt.weekday()
        dow_name = calendar.day_name[dow_number]

        # Build partial-day time slots
        trip_slots = [(dow_name, p) for p in range(start_period, end_period+1)]

        if staff_id not in staff_trips:
            staff_trips[staff_id] = []

        # Store as ((day_of_week, period), trip_name)
        for slot in trip_slots:
            staff_trips[staff_id].append((slot, trip_name))

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

    inspection_slots = [
        ("Monday", 1),
        ("Tuesday", 1),
        ("Wednesday", 1),
        ("Thursday", 1),
        ("Friday", 1),
        ("Saturday", 1)
    ]

    allowed_dr_days = ["Monday", "Tuesday", "Wednesday", "Thursday"]

    # Define optimization weights
    optimization_weights = OPTIMIZATION_WEIGHTS  # Use imported weights

    scheduler = Scheduler(staff_df, activity_df, location_df, location_options_df, group_df, time_slots,
                          staff_off_time_slots, leads_mapping, assists_mapping, waterfront_schedule, 
                          allowed_dr_days, staff_trips, optimization_weights)
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

        # Generate all schedule CSV files
        generate_group_schedules_csv(schedule_df.copy(), group_ids)
        generate_staff_schedule_csv(schedule_df.copy(), staff_df, time_slots, staff_off_time_slots)
        generate_unassigned_staff_csv(schedule_df.copy(), staff_df, time_slots, staff_off_time_slots, staff_trips)

        # Run tests on schedule
        schedule_df = schedule_df.explode('staff')
        run_tests(schedule_df, group_ids, location_options_df, staff_off_time_slots, 
                  staff_df, activity_df, leads_mapping, assists_mapping, 
                  waterfront_schedule, inspection_slots, allowed_dr_days,
                  time_slots, staff_trips=staff_trips, trips_df=trips_df)

    except ValueError as e:
        print(f"Error: {e}")
