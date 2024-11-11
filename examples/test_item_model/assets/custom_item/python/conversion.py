import json
import math

model_name = "egg"

# Map textures to colors, check your model file for the texture names
texture_colors = {
    "#0": "#FF0000",  # Yellow
}






# Load the JSON model
with open(f'assets/custom_item/python/{model_name}.json', 'r') as f:
    model = json.load(f)

# Initialize the 16x16x16 grid
grid_size = 16
pixels = [[[{"active": False, "color": "#000000"} for _ in range(grid_size)] for _ in range(grid_size)] for _ in range(grid_size)]



# For each element in the model
for element in model['elements']:
    # Get the 'from' and 'to' coordinates
    from_coords = element['from']  # [x1, y1, z1]
    to_coords = element['to']      # [x2, y2, z2]
    
    # Get the rotation if any
    rotation = element.get('rotation', None)
    
    # Get the texture/color from the faces
    faces = element.get('faces', {})
    textures = [face.get('texture', None) for face in faces.values()]
    # Remove None and duplicates
    textures = [tex for tex in textures if tex is not None]
    textures = list(set(textures))
    if textures:
        texture = textures[0]
    else:
        texture = '#noir'  # default texture
    
    color = texture_colors.get(texture, "#FFFFFF")
    
    # Ensure that 'from' is the minimum and 'to' is the maximum
    x_min, y_min, z_min = min(from_coords[0], to_coords[0]), min(from_coords[1], to_coords[1]), min(from_coords[2], to_coords[2])
    x_max, y_max, z_max = max(from_coords[0], to_coords[0]), max(from_coords[1], to_coords[1]), max(from_coords[2], to_coords[2])
    
    # Now, for each voxel in the grid, check if it is inside the element
    for x in range(grid_size):
        for y in range(grid_size):
            for z in range(grid_size):
                # Get the center point of the voxel
                vx = x + 0.5
                vy = y + 0.5
                vz = z + 0.5
                
                # Apply inverse rotation if necessary
                point = [vx, vy, vz]
                
                if rotation:
                    # Apply inverse rotation to the point
                    origin = rotation['origin']
                    axis = rotation['axis']
                    angle = rotation['angle']
                    
                    # Translate the point to the rotation origin
                    px = point[0] - origin[0]
                    py = point[1] - origin[1]
                    pz = point[2] - origin[2]
                    
                    # Convert angle to radians and invert for inverse rotation
                    theta = -math.radians(angle)
                    
                    if axis == 'x':
                        # Rotate around x-axis
                        y_rot = py * math.cos(theta) + pz * math.sin(theta)
                        z_rot = -py * math.sin(theta) + pz * math.cos(theta)
                        x_rot = px
                    elif axis == 'y':
                        # Rotate around y-axis
                        x_rot = px * math.cos(theta) - pz * math.sin(theta)
                        z_rot = px * math.sin(theta) + pz * math.cos(theta)
                        y_rot = py
                    elif axis == 'z':
                        # Rotate around z-axis
                        x_rot = px * math.cos(theta) + py * math.sin(theta)
                        y_rot = -px * math.sin(theta) + py * math.cos(theta)
                        z_rot = pz
                    else:
                        # Unknown axis
                        x_rot, y_rot, z_rot = px, py, pz
                        
                    # Translate the point back from the rotation origin
                    point = [x_rot + origin[0], y_rot + origin[1], z_rot + origin[2]]
                
                # Check if the point is inside the axis-aligned box
                if (x_min <= point[0] <= x_max and
                    y_min <= point[1] <= y_max and
                    z_min <= point[2] <= z_max):
                    # Mark the voxel as active and assign the color
                    pixels[x][y][z]['active'] = True
                    pixels[x][y][z]['color'] = color

# Save the pixels data as a JSON file
with open(f'assets/custom_item/python/{model_name}_pixel.json', 'w') as f:
    json.dump(pixels, f)
