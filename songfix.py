import os

# Directory path where the files are located
directory = r'C:\Users\Megas\Documents\GitHub\GuessDokkanOst\songs'

# Loop through each file in the directory
for filename in os.listdir(directory):
    # Check if it's a file
    if os.path.isfile(os.path.join(directory, filename)):
        # Start with the original filename
        new_filename = filename
        
        # Find the position of the first "-" in the filename
        dash_index = new_filename.find('-')
        
        # If there's a "-" in the filename, slice the filename to remove everything after it
        if dash_index != -1:
            new_filename = new_filename[:dash_index].strip() + os.path.splitext(new_filename)[1]  # Retain the file extension
        
        # If there's a "Dragon Ball Z Dokkan Battle: " in the filename, remove it
        prefix = "Dragon Ball Z Dokkan Battle： "
        if prefix in new_filename:
            new_filename = new_filename.replace(prefix, "")
        
        # Rename the file only if the filename has changed
        if new_filename != filename:
            os.rename(os.path.join(directory, filename), os.path.join(directory, new_filename))

print("Renaming complete.")
