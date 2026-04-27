#To run multiple Python files in a specific range

import subprocess

# Function to run python files starting from a specified file number to an end number
def run_python_files(start_number, end_number):
    # List to keep track of subprocesses
    processes = []

    # Iterate over the file names
    for i in range(start_number, end_number + 1):
        # Construct the file name
        file_name = f"python_scripts/{i}.py"
        
        # Start the python file as a subprocess and append it to the processes list
        process = subprocess.Popen(["python", file_name])
        processes.append(process)

    # Wait for all processes to complete
    for process in processes:
        process.wait()

# Run files from {i}.py to {i+1}.py

run_python_files(1, 83)
#run_python_files(1, 86)


