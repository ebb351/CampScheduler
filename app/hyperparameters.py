"""
Hyperparameters for the camp schedule optimization problem.
These values can be adjusted to tune the optimization process.
"""

# Optimization weights for different objectives
OPTIMIZATION_WEIGHTS = {
    'staff_diversity': 0.25,   # Weight for staff activity diversity 
    'group_diversity': 0.75,   # Weight for group activity category diversity per period
    'group_weekly_diversity': 0.75, # Weight for group unique activity diversity per week
    'unassigned_periods_balance': 0.75 # Balances unassigned periods for staff
}

# Time limit for the solver in minutes
SOLVER_TIME_LIMIT = 1