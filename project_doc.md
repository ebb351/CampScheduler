## Project Overview
This project uses Google's OR-Tools constraint programming solver to create optimal activity schedules for camp groups. It handles complex scheduling requirements including:
- Staff qualifications for leading or assisting activities
- Staff availability and time-off constraints
- Activity-location compatibility
- Multi-period activities like driving range
- Special activities like waterfront with fixed scheduling
- Prevention of scheduling conflicts
- Trip handling
- Optimization of defined variables
## Tech stack
- Optimizer: OR-Tools
- Backend: FastAPI or Flask (TBD)
- Frontend: Vue.js or React with Tailwind CSS (TBD)
- Database: SQLite
- Deployment: Electron Application or Docker (TBD)
## Project Roadmap
### Develop Basic Schedule Constraint Solving
1. Constraint Optimization Engine with Google's OR tools
	1. DONE Automatically Generate valid schedules satisfying complex constraints
	2. DONE Handle staff qualifications, availability, and assignments
	3. DONE Manage location compatiability with activities
	4. DONE Handle specieal cases like waterfront activities, golf/tennis pairings
	5. DONE Manage multi-period activities like driving range
	6. DONE Incorporate trip scheduling and staff assignments
	7. Specify exact number of off periods a staff member gets some week (defaults to 2)
2. Optimization Objective Function with Google's OR-Tools
	1. DONE Key optimization variables
		1. DONE Minimize staff workload imbalance: distribute assignments evenly across staff
			1. DONE I.e. miniminze: $\sum_i (\text{total assignments for staff } i - \text{average assignments})^2$ 
		2. DONE Maximize staff activitity diversity: avoid assigning the same activity to the same staff too much
		3. DONE Maximize group activity diversity: ensure groups experience a mix of arts/sports each period
			1. DONE Maximize: $\sum_{g,p,d} v_{g,p,d}$ where $v_{g,p,d}$ measures the variety of activity categories for group $g$, period $p$, day $d$
	2. DONE Hyperparams
		1. DONE Ability to assign weights in optimization function
			1. DONE I.e. $\text{objective} = \lambda_1 \cdot \text{Workload Imbalance} - \lambda_2 \cdot \text{Schedule Diversity} + \lambda_3 \cdot \text{Constraint Violations}$
3. Initial data model
	1. DONE CSV based data management for all scheduling parameters
	2. DONE Support for multiple staff roles (leads vs assists)
	3. DONE Group management with individualized schedules
	4. DONE Staff-off time tracking
4. Validation test functions
	1. DONE Verify no scheduling conflicts exist
	2. DONE Confirm each constraint is properly satisfied
	3. DONE Check special scheduling rules are followed

### Data Management
Use a simple SQLite database for data persistence with CSV import/export capabilities.
Detailed Steps:
1. Design streamlined database schema
   1. Create tables for core entity types (staff, activities, locations)
   2. Keep relationships simple and intuitive
2. Implement basic ORM
   1. Define models that map to database tables
   2. Create simple data access methods
3. Prioritize CSV compatibility
   1. Create user-friendly import tools for CSV files
   2. Implement export services to generate CSV files from database data
   3. Add validation during import with clear error messages
4. Create backup functionality
   1. Add simple database backup feature
   2. Implement restore capability for recovery

### Backend API
Convert the basic python files into a lightweight REST API service.
Detailed Steps:
1. Create a simple API structure
   1. `/api/schedule` - Endpoints for schedule generation and management
   2. `/api/data` - Basic endpoints for managing core data entities
2. Encapsulate core scheduler functionality
   1. Convert scheduler.py into a service class with methods callable from API endpoints
   2. Add error handling with clear error messages for non-technical users
3. Define focused data schemas
   1. Create models for essential data types (staff, activities, schedules)
   2. Implement validation to prevent invalid data
4. Implement CRUD operations
   1. Add endpoints for creating, reading, updating, and deleting all data entities
   2. Focus on simple, intuitive operations for non-technical users
5. Add schedule generation endpoint
   1. POST `/api/schedule/generate` to create new schedules
   2. PUT `/api/schedule/{id}` to update existing schedules
   3. Include validation to verify constraints are satisfied

### Frontend Components
Develop a simple, intuitive interface focused on core functionality.
Detailed Steps:
1. Set up a lightweight project structure
   1. Create essential components only
   2. Implement simple state management
2. Develop streamlined data management screens
   1. Staff management with qualification assignments
   2. Activity configuration with location requirements
   3. Simple group management
   4. Basic time constraints management
   5. Weekly trip/special activity management
3. Implement user-friendly CSV handling
   1. CSV upload with clear instructions and validation
   2. CSV template download functionality
   3. Simple error reporting for invalid data
4. Create clear schedule visualization
   1. Daily view with periods as columns
   2. Weekly view with days as rows
   3. Staff and group views with filtering options
5. Add basic interactive editing
   1. Simple interface for schedule adjustments
   2. Clear warnings when changes violate constraints
   3. Option to override constraints with confirmation
6. Implement responsive design
   1. Desktop-optimized views for primary use case
   2. Basic mobile support for viewing schedules
7. Add straightforward export functionality
   1. CSV export with standard format
   2. Print-friendly schedule views

### Packaging
Focus on a single, lightweight deployment approach that's easy for non-technical users to install and use.
Detailed Steps:
1. Electron Application
   1. Benefits:
      - Self-contained desktop application requiring no technical setup
      - Offline capability for use anywhere
      - Simple installation process for non-technical users
      - Cross-platform support (Windows, Mac)
   2. Implementation steps:
      - Package the entire application as a single Electron app
      - Include SQLite database embedded in the application
      - Create simple installers for Windows and Mac
      - Provide clear documentation for installation and use
2. Docker Deployment
   1. Benefits:
      - Consistent environment across different machines
      - Easier network access for multi-user scenarios
      - Better isolation of application components
      - Simplified updates via container replacement
   2. Implementation steps:
      - Create separate containers for frontend, backend, and database
      - Set up Docker Compose for easy deployment
      - Add volume mapping for persistent data
      - Document deployment process for non-technical users
3. Hybrid approach (optional)
   1. Create Electron app that can either:
      - Run packaged services locally, or
      - Connect to Docker-deployed backend on the network
   2. Provides maximum flexibility for different deployment scenarios