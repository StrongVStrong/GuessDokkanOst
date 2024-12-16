import os

# Directory path where the files are located
directory = r'C:\Users\Megas\Documents\GitHub\GuessDokkanOst\songs'

# Loop through each file in the directory
for filename in os.listdir(directory):
    # Check if it's a file (to avoid directories)
    if os.path.isfile(os.path.join(directory, filename)):
        # Find the position of the first "-" in the filename
        dash_index = filename.find('-')
        
        # If there's a "-" in the filename, slice the filename to remove everything after it
        if dash_index != -1:
            new_filename = filename[:dash_index].strip() + os.path.splitext(filename)[1]  # Retain the file extension
            # Rename the file
            os.rename(os.path.join(directory, filename), os.path.join(directory, new_filename))

print("Renaming complete.")
