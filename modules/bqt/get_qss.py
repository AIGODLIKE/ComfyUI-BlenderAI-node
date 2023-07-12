import os

def merge_qss_files(folder_path, output_file):
    with open(output_file, 'w') as outfile:
        for root, dirs, files in os.walk(folder_path):
            for file in files:
                if file.endswith('.qss'):
                    with open(os.path.join(root, file), 'r') as infile:
                        outfile.write(infile.read())
                        outfile.write('\n')



merge_qss_files(r'C:\Users\atticus\Desktop\blender_addon\addons\ad_jewel_tools\modules\bqt\dark',r'C:\Users\atticus\Desktop\blender_addon\addons\ad_jewel_tools\modules\bqt\dark.qss')