# Camp Schedule Builder

A tool to automatically generate camp activity schedules. This guide is for users who are not familiar with programming.

## General Overview

This project uses a powerful tool from Google called **OR-Tools** to solve a complex puzzle: creating a weekly camp schedule. It takes a list of requirements (like "a staff member can't be in two places at once") and finds a schedule that doesn't break any of these rules.

These rules are called **hard constraints**. The scheduler will never produce a schedule that violates them. Examples of hard constraints include:
- A staff member cannot be assigned to more than one activity at the same time.
- An activity can only happen in a location that is suitable for it.
- An activity must have the required number of qualified staff.
- Staff cannot be scheduled for activities during their approved time off.

In addition to these hard constraints, the scheduler also tries to create the best possible schedule by optimizing for several factors:
- **Staff Activity Diversity**: Tries to prevent staff from doing the same activity too many times per week
- **Group Activity Category Diversity**: Aims to give each group a diverse mix of activity categories (e.g., sports individual, sports team, arts) in each period
- **Group Weekly Activity Diversity**: Ensures each group gets to try a variety of different activities throughout the week
- **Staff Workload Balance**: Attempts to give each staff member approximately 2 unassigned periods per week

The scheduler will keep searching for a better schedule until it either finds an optimal solution or reaches the maximum time limit (which you can adjust in `hyperparameters.py`).

## Initial Setup (One-Time Only)

You only need to do this setup once. Follow these steps in order.

### 1. Install Python
- **Purpose**: Python is the programming language this tool is built with. You need it to run the scheduler.
- **How to install**:
    - Go to the official Python website: [python.org/downloads](https://www.python.org/downloads/)
    - Download the latest version of Python for your operating system (Windows or macOS).
    - Run the installer. On Windows, make sure to check the box that says "Add Python to PATH".

### 2. Install Git
- **Purpose**: Git is a tool for managing and downloading code. You'll use it once to copy the scheduler project to your computer.
- **How to install**:
    - Go to the official Git website: [git-scm.com/downloads](https://git-scm.com/downloads/)
    - Download and install Git for your operating system.

### 3. Clone the Repository
- **Purpose**: This step downloads a copy of the schedule builder project to your computer.
- **How to do it**:
    - Open the terminal in Cursor (from the top menu: `Terminal` > `New Terminal`)
    - Copy and paste this command into the terminal and press Enter:
      ```bash
      git clone https://github.com/ebb351/CampScheduler.git
      ```
    - This will create a new folder called `CampScheduler` in your current directory
    - Open this folder in Cursor by going to `File` > `Open Folder` and selecting the `CampScheduler` folder

### 4. Create a Virtual Environment
- **Purpose**: A virtual environment is like a private workspace for this project. It keeps the tools it needs separate from other things on your computer to prevent conflicts.
- **How to do it**:
    - In the Cursor terminal, make sure you're in the `CampScheduler` directory (you should see `CampScheduler` in the terminal prompt)
    - Copy and paste this command into the terminal and press Enter:
      ```bash
      python -m venv .venv
      ```
    - Then activate the virtual environment by running:
      ```bash
      source .venv/bin/activate
      ```
    - You'll know it worked when you see `(.venv)` at the beginning of your terminal prompt

### 5. Install "Edit CSV" Extension
- **Purpose**: This is an extension for Cursor that makes it easy to view and edit the output schedule CSV files like `group_1_schedule.csv` and `staff_assignments.csv`
- **How to install**:
    - In Cursor, click on the Extensions icon in the left-hand sidebar (it looks like four squares).
    - Search for "Edit CSV".
    - Find the one by janisdd and click "Install".

### 6. Install Requirements
- **Purpose**: This step installs the specific Python libraries the scheduler needs to run, like Google OR-Tools.
- **How to do it**:
    - Open the terminal in Cursor
    - Copy and paste the following command into the terminal and press Enter:
      ```bash
      pip install -r requirements.txt
      ```

## Project Structure

Here is an overview of the folders and files in the project.

### `app/` directory
This directory contains the core logic of the scheduler. You should not need to change any files in here except for `hyperparameters.py`.

- `scheduler.py`: The main script that runs the scheduling process.
- `data_manager.py`: Handles loading all the data from the CSV files.
- `schedule_tests.py`: Contains tests to verify that the generated schedule is valid.
- `hyperparameters.py`: A file for you to tweak scheduling settings. See the "Running the Program" section for more details.

### `data/` directory
This directory holds all the data the scheduler uses. You will edit these files to prepare for each week's schedule. You can do this in a spreadsheet outside of these files, download as `csv` and replace the existing files. **It is critical that you do not change the file names.**

- `activity.csv`: Lists all possible camp activities, how many staff are needed to lead and assist, and what category these activities fall into.
- `staff.csv`: A list of all staff members.
- `leads.csv`: Defines which staff members are qualified to *lead* which activities.
- `assists.csv`: Defines which staff members can *assist* with which activities. If a staff member can lead an activity, they should also be listed as able to assist.
- `location.csv`: A list of all available locations for activities.
- `locOptions.csv`: Maps activities to the locations where they can take place.
- `groups.csv`: The names of the camp groups.
- `offDays.csv`: Staff days off for the week.
- `trips.csv`: Information about any trips happening during the week, including which staff are involved. 
- `certs.csv`: A list of all certifications and the activities they are required for (e.g. archery, climbing).
- `certified.csv`: Maps staff to the certifications they hold (e.g., Lifeguard).

### Output Directories
These directories will be created automatically when you run the scheduler. They will contain the generated schedules.

- `group_schedules/`: Contains a separate CSV schedule for each camp group.
- `staff_schedules/`: Contains a single CSV with the schedule for each staff member.

### `requirements.txt`
This file lists the Python libraries that the project depends on. The `pip install -r requirements.txt` command uses this file to install them.

### `.gitignore`
This file tells Git which files and folders to ignore in a project. It prevents unnecessary files (like virtual environment folders, Python cache files, and output schedules) from being tracked by Git. You don't need to modify this file.

## Running the Program

Follow these steps each week to generate a new schedule.

### 1. Update the `data/` files
The CSV files in the `data/` directory are the inputs to the scheduler. Before running it, you need to update them with the correct information for the upcoming week.

- **These files define the world for the scheduler.** For example, if you add a new location to `location.csv` and then update `locOptions.csv` to say that "Archery" can happen there, the scheduler will know it can use that new location for Archery.
- **You must save the CSV files after editing them** for the changes to be picked up by the scheduler.
- The two files you must change each week are `trips.csv` (for the week's trips) and `offDays.csv` (for the week's time-off schedule).
- You may also need to update other files. For example, if a counselor has a new activity they can run, you would add a new row to `leads.csv` for them.
    - **Important**: If you add a row to `leads.csv` for a staff member and an activity, you must add the same row to `assists.csv`.

### 2. Activate the Virtual Environment
- Before running the scheduler, you need to activate the virtual environment. In the Cursor terminal, you should see something like `(.venv)` at the beginning of the command prompt.
- If you don't see it, run this command in the terminal:
  ```bash
  source .venv/bin/activate
  ```
  (On Windows, it might be `.venv\Scripts\activate`)

### 3. Change Hyperparameters (Optional)
- You can adjust some settings in the `app/hyperparameters.py` file.
- `SOLVER_TIME_LIMIT`: The maximum time in minutes the scheduler will search for a solution. Default is 15 minutes. A longer time may result in a better-balanced schedule, but it's not guaranteed.
- `OPTIMIZATION_WEIGHTS`: These weights control how much importance is given to each optimization goal. These are relative to each other. The absolute value doesn't matter but keeping in range 0-1 is standard practice):
  - `staff_diversity`: How much to penalize staff doing the same activity repeatedly
  - `group_diversity`: How much to prioritize diverse activity categories in each period
  - `group_weekly_diversity`: How much to prioritize groups trying different activities throughout the week
  - `unassigned_periods_balance`: How much to prioritize giving staff their target of 2 unassigned periods (in testing, keeping this high was better)

### 4. Run the Scheduler
- In the terminal (make sure the virtual environment is active), run the following command:
  ```bash
  python app/scheduler.py
  ```
  You will see that it is running via printed statements in the terminal
- ***This will overwrite current schedule output files***. Copy current files elsewhere if you want to save them. 
- A lot of information will be printed in the terminal, including the full schedule, test results for each of the hard constraints, and an overview of how successfully each optimization goal was met (the output is a bit buggy/sometimes incorrect, don't worry about that). 
- This will take time. The scheduler is solving a very complex problem. You do not need to keep the screen on, but ***do not close your laptop*** while it is running.

### 5. Review and Edit the Output
- Once the scheduler is finished, the output schedules will be in the `group_schedules/` and `staff_schedules/` folders.
- You can open these CSV files directly in Cursor. To edit them easily, click the "Edit CSV" button that appears in the top-right of the tab bar.
- You can also move these files to Google Drive and open them as Google Sheets, or open them with Microsoft Excel.

## Troubleshooting and Upkeep

### No solution found (`infeasible`) errors
The scheduler is very flexible, so these errors are typically caused by the few activity/schedule rules that are not flexible: *waterfront* and *waterskiing* (the only two with many required time slots). Here are likely causes and quick solutions if you encounter this:

- WF requires 4 "leads" (leads = lifeguard, must be in both leads table and certs table), but 4 are not available on some given day due to trips or off days. 
    -  Reschedule off days or lower the `numStaffRequired` value for waterfront found in `activity.csv`
- Watersiing requires 1 "leads" and 1 "assists", but 1 is not available (there are only 3 staff who can lead currently) on some given day due to trips or off days. 
    -  Reschedule off days or move someone from `assists.csv` to `leads.csv` for waterskiing
- If major changes have been made to any input csvs around these two activities, you may have accidentally removed a crucial dependency (e.g. the waterfront location from `location.csv` was deleted and the scheduler has no location to put waterfront in). 

### Reverting Accidental Changes
- **Quick Fix**: If you make a change without meaning to and haven't yet saved the file, you can just close the file in the editor and select "don't save changes".
- **Otherwise**, If you accidentally change or delete code and things stop working, you can revert all files back to the last clean version you downloaded.
    - **Warning**: This will delete any unsaved changes, including any generated schedules. If you want to keep your schedules, save them somewhere else first (e.g., your Desktop).
- To revert, run this command in the terminal:
  ```bash
  git reset --hard HEAD
  ```
- After running this, you may need to run `python app/scheduler.py` again.

### File Errors
- If you see an error like `FileNotFoundError: [Errno 2] No such file or directory: 'data/some_file.csv'`, it means the scheduler can't find a file it needs.
- **Check the file names in your `data/` directory.** They must exactly match the names listed in the "Project Structure" section above. For example, `trips.csv` is correct, but `Trips.csv` or `trips_new.csv` will cause an error.

### Getting Help with Errors
- **Use Cursor Chat**: The AI assistant in Cursor is great for debugging.
  - Make sure it's in "Ask" mode (not "Edit" mode) so it doesn't try to change code automatically.
  - You can highlight an error message in the terminal, and a button "Add to Chat" will appear. Click it, and then ask the AI something like "What does this error mean?" or "How can I fix this? Give me granular steps". This should provide insight and instructions for resolving the error
- If you're stuck and can't solve an issue, just shoot Eli a text.