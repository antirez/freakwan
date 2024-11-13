def parse_value(value):
    """
    Parses a string value and converts it to the appropriate type.
    
    Args:
        value (str): The string value to parse
    
    Returns:
        The value converted to the appropriate type (int, float, bool, or str)
    """
    value = value.strip()

    if value.lower() == 'true':
        return True
    elif value.lower() == 'false':
        return False

    elif value.lower() == 'null':
        return None

    try:
        if '.' in value:
            return float(value)
        else:
            return int(value)
    except ValueError:
        pass
    
    # Return the value as a string if no other type matches
    return value

def parse_decorated_pair(current_group, metadata_comment, key_value_pair):
    """
    Parses a decorated key-value pair with its metadata comment into a structured dictionary.
    
    Args:
        current_group (str): The current group name
        metadata_comment (str): Metadata comment starting with #$ 
        key_value_pair (str): YAML key-value pair
    
    Returns:
        dict: Parsed dictionary with group, id, value, and metadata attributes
    """
    parsed_pair = {}
    
    # Split attributes, skipping the first element (the #$ marker)
    attributes = metadata_comment.split()[1:]
    
    # Parse key and value
    key, value = key_value_pair.split(': ', 1)
    
    # Basic parsing
    parsed_pair['group'] = current_group
    parsed_pair['id'] = key.strip()
    parsed_pair['value'] = parse_value(value)
    parsed_pair['comment'] = metadata_comment
    
    # Parse additional attributes
    for attr in attributes:
        if ':' in attr:
            attr_key, attr_value = attr.split(':', 1)
            parsed_pair[attr_key] = parse_value(attr_value)
    
    return parsed_pair

def parse_yaml(file_contents):
    """
    Parses a configuration file with decorated YAML formatted data.
    
    Args:
        file_contents (str): Contents of the YAML file
    
    Returns:
        dict: Dictionary with 'decorated' and 'plain' YAML data
    """
    # Split file contents into lines
    lines = file_contents.split('\n')
    
    # Data containers
    decorated_data = {}
    plain_data = {}
    
    # Track current group
    current_group = None
    
    # Iterate through lines
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        
        # Reset current group on empty lines
        if not line:
            current_group = None
            i += 1
            continue
        
        # Handle group declarations
        if line.startswith('#$ group'):
            if i + 1 < len(lines):
                current_group = lines[i + 1].strip()[:-1]  # Remove trailing colon
                decorated_data[current_group] = []
                i += 2
                continue
        
        # Handle decorated key-value pairs
        elif line.startswith('#$'):
            if i + 1 < len(lines):
                metadata_comment = line
                key_value_pair = lines[i + 1].strip()
                
                if current_group:
                    decorated_pair = parse_decorated_pair(current_group, metadata_comment, key_value_pair)
                    decorated_data[current_group].append(decorated_pair)
                i += 2
                continue
        
                # Skip comments
        elif line.startswith('#'):
            i += 1
            continue
        
        # Add non-comment lines to plain data
        current_group = line.strip()[:-1]  # Remove trailing colon
        plain_data[current_group] = {}
        
        i += 1
        while i < len(lines) and lines[i]:
            key_value_pair = lines[i].strip()
            key, value = key_value_pair.split(':', 1)
            plain_data[current_group][key.strip()] = parse_value(value.strip())
            i += 1
            
        i += 1
    
    return {
        'decorated': decorated_data,
        'plain': plain_data
    }

def rebuild_yaml(parsed_config):
    """
    Rebuilds a configuration file from parsed data.
    
    Args:
        parsed_config (dict): Parsed configuration dictionary
    
    Returns:
        str: Rebuilt configuration file content
    """
    rebuilt_config = ''
    
    # Rebuild decorated groups
    for group, pairs in parsed_config['decorated'].items():
        rebuilt_config += '#$ group\n'
        rebuilt_config += f'{group}:\n'
        
        for pair in pairs:
            rebuilt_config += f'  {pair["comment"]}\n'
            rebuilt_config += f'  {pair["id"]}: {pair["value"]}\n'
        
        rebuilt_config += '\n'  # Empty line between groups
        
    # Append plain YAML content
    for group, pairs in parsed_config['plain'].items():
        rebuilt_config += f'{group}:\n'
        for key, value in pairs.items():
            rebuilt_config += f'  {key}: {value}\n'
            
        rebuilt_config += '\n'  # Empty line between groups
    
    rebuilt_config = rebuilt_config[:-2] # hack to remove trailing blank lines

    # Return as string
    return rebuilt_config