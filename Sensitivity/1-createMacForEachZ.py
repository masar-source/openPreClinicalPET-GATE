
import os
import pandas as pd


file_path = 'totalPETModel.mac'


sensitivities_df = pd.read_excel("sensitivity_measurments/SensPostionsQuad86.xlsx")
#sensitivities_df = pd.read_excel("sensitivity_measurments/SensPostionsQuad72.xlsx")
sensitivities = sensitivities_df.iloc[:, 0].tolist()


def read_original_file(file_path):
    with open(file_path, 'r') as file:
        file_content = file.readlines()
    return file_content


def create_modified_file(Z_value, file_number, file_content, new_dir_path):
    new_file_content = []
    for line in file_content:
        if line.startswith('/gate/sourceBox/placement/setTranslation'):
            new_line = f'/gate/sourceBox/placement/setTranslation 0. 0. {Z_value} mm\n'
            new_file_content.append(new_line)
            
        elif line.startswith('/gate/tableTip/placement/setTranslation'):
            new_line = f'/gate/tableTip/placement/setTranslation 0. -20. {Z_value} mm\n'
            new_file_content.append(new_line)
                        
        elif line.startswith('/gate/output/root/setFileName'):
            new_line = f'/gate/output/root/setFileName output/{file_number}\n'
            new_file_content.append(new_line)
        else:
            new_file_content.append(line)


    new_file_name = f"{file_number}.mac"
    new_file_path = os.path.join(new_dir_path, new_file_name)
    

    with open(new_file_path, 'w') as new_file:
        new_file.writelines(new_file_content)


original_file_content = read_original_file(file_path)


new_dir_path = 'mac_Z'  
for file_number, Z_value in enumerate(sensitivities, start=1):

    create_modified_file(Z_value, file_number, original_file_content, new_dir_path)
