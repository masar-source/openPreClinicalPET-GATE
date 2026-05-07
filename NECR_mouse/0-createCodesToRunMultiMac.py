import os

# Directory to save the generated Python files
output_dir = 'python_scripts'
os.makedirs(output_dir, exist_ok=True)

# Template for the Python script
python_script_template = """
import os
import subprocess

def run_gate_macro():
    macro_file = "{}"
    docker_command = [
        "docker", "run", "-i", "--rm",
        "-v", f"{{os.getcwd()}}:/APP",
        "opengatecollaboration/gate:8.2-docker",
        macro_file
    ]
    subprocess.run(docker_command)

if __name__ == "__main__":
    run_gate_macro()
"""

# Generate and save the Python files
file_paths = []
for i in range(1, 147):
    macro_file_name = f"mac_A/{i}.mac"
    script_content = python_script_template.format(macro_file_name)
    file_name = f"{i}.py"
    file_path = os.path.join(output_dir, file_name)
    with open(file_path, 'w') as file:
        file.write(script_content)
    file_paths.append(file_path)

