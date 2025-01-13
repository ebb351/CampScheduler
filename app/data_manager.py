import os
import pandas as pd

class DataManager:
    def __init__(self, data_dir="data"):
        """
        Initialize the DataManager.
        :param data_dir: Directory where CSV files are stored
        """
        base_dir= os.path.dirname(os.path.abspath(__file__))
        self.data_dir = os.path.join(base_dir, "..", data_dir)
        self.dataframes = {}

    def load_csv(self, file_name):
        """
        Load a CSV file into a Pandas DataFrame.
        :param file_name: Name of the CSV file to load
        :return: Pandas DataFrame
        """
        file_path = os.path.join(self.data_dir, file_name)
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        try:
            df = pd.read_csv(file_path)
            # print(f"Loaded {file_name} successfully.")
            return df
        except Exception as e:
            raise ValueError(f"Error loading {file_name}: {e}")

    def load_all_csvs(self):
        """
        Load all required CSV files into DataFrames and store them in a dictionary
        """
        csv_files = {
            "staff": "staff.csv",
            "activity": "activity.csv",
            "certs": "certs.csv",
            "leads": "leads.csv",
            "assists": "assists.csv",
            "certified": "certified.csv",
            "location": "location.csv",
            "locOptions": "locOptions.csv",
            "groups": "groups.csv",
            "offDays": "offDays.csv",
            "trips": "trips.csv",
        }

        for key, file_name in csv_files.items():
            try:
                self.dataframes[key] = self.load_csv(file_name)
            except Exception as e:
                print(f"Error loading {key}: {e}")

    def validate_columns(self, df, required_columns):
        """
        Validate all loaded DataFrames for required columns
        """
        missing_cols = [col for col in required_columns if col not in df.columns]
        if missing_cols:
            raise ValueError(f"Missing columns: {missing_cols}")
        # print("Validation passed.")

    def validate_all(self):
        """
        Validate all loaded DataFrames for required columns
        """
        column_requirements = {
            "staff": ["staffID", "staffName"],
            "activity": ["activityID", "activityName", "numStaffReq", "duration"],
            "certs": ["certID", "certName", "activityID", "numStaffReq"],
            "leads": ["staffID", "activityID"],
            "assists": ["staffID", "activityID"],
            "certified": ["certID", "staffID"],
            "location": ["locID", "locName"],
            "locOptions": ["activityID", "locID"],
            "groups": ["groupID"],
            "offDays": ["staffID", "staffName", "date"],
            "trips": ["trip_name","staffID", "staffName", "date", "start_period", "end_period"]
        }

        for key, required_columns in column_requirements.items():
            try:
                if key in self.dataframes:
                    self.validate_columns(self.dataframes[key], required_columns)
                else:
                    print(f"DataFrame for {key} not loaded. Skipping validation")
            except ValueError as e:
                print(f"Error validating {key}: {e}")

    def get_dataframe(self, key):
        """
        Retrieve a DataFrame by its key
        :param key: The key for the DataFrame (e.g. "staff")
        :return: Pandas DataFrame
        """
        if key in self.dataframes:
            return self.dataframes[key]
        else:
            raise KeyError(f"DataFrame for {key} not found")

if __name__ == "__main__":
    # Initialize the DataManager with default data directory
    manager = DataManager(data_dir="data")

    # Load all CSVs
    manager.load_all_csvs()

    # Validate loaded DataFrames
    manager.validate_all()

    # Test: Retrieve a DataFrame by key
    staff_df = manager.get_dataframe("staff")
    print(staff_df.head())

