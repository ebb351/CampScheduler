# Camp Schedule Builder v2.0

A Python-based constraint optimization tool that automatically generates camp activity schedules while respecting complex constraints including staff availability, activity requirements, and location limitations.

## Overview

This project uses Google's OR-Tools constraint programming solver to create optimal activity schedules for camp groups. It handles complex scheduling requirements including:

- Staff qualifications for leading or assisting activities
- Staff availability and time-off constraints
- Activity-location compatibility
- Multi-period activities like driving range
- Special activities like waterfront with fixed scheduling
- Prevention of scheduling conflicts
- Trip handling

## Features

- **Constraint-Based Optimization**: Automatically finds valid schedules that satisfy all requirements
- **CSV-Based Data Management**: Load all scheduling data from simple CSV files
- **Comprehensive Testing**: Validates generated schedules against all constraints
- **Flexible Group Management**: Handles multiple groups with individualized schedules

## Requirements

- Python 3.8+
- Dependencies listed in `requirements.txt`

## Installation

1. Clone the repository
2. Create and activate a virtual environment (recommended)
3. Install dependencies:

```bash
pip install -r requirements.txt
```

## Data Structure

All scheduling data is managed through CSV files in the `data/` directory:

- `activity.csv`: Activities with staff requirements
- `staff.csv`: Staff member information
- `leads.csv`: Maps staff to activities they can lead
- `assists.csv`: Maps staff to activities they can assist with
- `location.csv`: Available locations
- `locOptions.csv`: Maps activities to valid locations
- `groups.csv`: Camp groups
- `offDays.csv`: Staff time-off requests
- `trips.csv`: Trip schedules and staff assignments

## Usage

Run the scheduler from the command line:

```bash
python app/scheduler.py
```

The program will:

1. Load data from the CSV files
2. Generate a valid schedule
3. Validate the schedule against all constraints
4. Print the optimized schedule

## How It Works

The scheduler works by:

1. Defining decision variables for staff assignment, location selection, and activity choices
2. Creating constraints that enforce all scheduling rules
3. Using CP-SAT solver to find a feasible solution
4. Processing the solution into a readable schedule format
5. Running validation tests to verify all constraints are satisfied

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.