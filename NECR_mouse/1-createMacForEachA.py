
import os
import pandas as pd

# NECR simulation. The changing value for each mac file is the activity: {A_value} becquerel.

file_path = 'totalPETModel.mac'

# Load activity values from the Excel file
activities_df = pd.read_excel("NECR_measurments/ActivitiesQuad35.xlsx")
#activities_df = pd.read_excel("ActivitiesQuad35.xlsx")
activities = activities_df.iloc[:, 0].tolist()

# Function to read the original file content
def read_original_file(file_path):
    with open(file_path, 'r') as file:
        file_content = file.readlines()
    return file_content

# Function to modify and save a file
def create_modified_file(A_value, file_number, file_content, new_dir_path):
    new_file_content = []
    for line in file_content:
        if line.startswith('/gate/source/F18CylinderSource/setActivity'):
            new_line = f'/gate/source/F18CylinderSource/setActivity {A_value} becquerel\n'
            new_file_content.append(new_line)
        elif line.startswith('/gate/output/root/setFileName output'):
            # Change the file name for the output command
            new_line = f'/gate/output/root/setFileName output/{file_number}\n'
            new_file_content.append(new_line)
        else:
            new_file_content.append(line)
    
    # Construct the new file name and path
    new_file_name = f"{file_number}.mac"
    new_file_path = os.path.join(new_dir_path, new_file_name)
    
    # Write the new file content to the new file
    with open(new_file_path, 'w') as new_file:
        new_file.writelines(new_file_content)

# Read the original file content (outside the loop)
original_file_content = read_original_file(file_path)

# Assuming you have a loop or a sequence to create multiple files
new_dir_path = 'mac_A'  # replace with your actual directory path
for file_number, A_value in enumerate(activities, start=1):
    # Call the function with each file_number, the corresponding activity value, and the new directory path
    create_modified_file(A_value, file_number, original_file_content, new_dir_path)
