// const fs = require('fs');

/**
 * Parses a decorated key-value pair with its metadata comment into a structured object.
 * @param {string} metadataComment - The metadata comment starting with #$ (e.g., "#$ tag:input type:number")
 * @param {string} keyValuePair - The YAML key-value pair following the metadata (e.g., "frequency: 50")
 * @returns {Object} Parsed object containing id, value, and all metadata attributes
 */
function parseDecoratedPair(currentGroup, metadataComment, keyValuePair) {
    const parsedPair = {};
    const attributes = metadataComment.split(/\s+/).slice(1);

    parsedPair.group = currentGroup;
    parsedPair.id = keyValuePair.split(': ')[0];
    parsedPair.value = keyValuePair.split(': ')[1];
    parsedPair.comment = metadataComment;  // Store original comment for rebuilding

    // Parse each attribute (tag:input, type:number, etc.) into key-value pairs
    attributes.forEach(e => { parsedPair[e.split(':')[0]] = e.split(':')[1]; });

    return parsedPair;
}

/**
 * Parses a configuration file containing decorated YAML formatted data.
 * Supports grouped elements with metadata comments describing how an element should be displayed, and plain 
 * YAML content.
 * @param {string} file - Path to the configuration file
 * @returns {Object} Object containing decorated (grouped) and plain YAML data
 */
export function parseYaml(fileContents) {
    const lines = fileContents.split('\n');
    const decoratedData = {};  // Stores grouped decorated elements
    const plainData = [];      // Stores regular YAML lines

    // Track the current group nest level we are in
    let currentGroup = null;

    for (let i = 0; i < lines.length; i++) {
        const line = lines[i];

        // Reset current group on empty lines (group separator)
        if (!line) { currentGroup = null; continue; }

        // Handle decorated lines (starting with #$)
        if (line.trim().startsWith('#$')) {
            // Handle group declarations
            if (line === '#$ group') {
                const nextLine = lines[i + 1];
                currentGroup = nextLine.trim().slice(0, -1);  // Remove trailing colon
                decoratedData[currentGroup] = [];
                i++;  // Group name already used, so skip in next iteration
                continue;
            } else {
                // Handle decorated key-value pairs
                const metadataComment = line.trim();
                const keyValuePair = lines[i + 1]?.trim();
                if (currentGroup) {
                    decoratedData[currentGroup].push(parseDecoratedPair(currentGroup, metadataComment, keyValuePair));
                } else {
                    console.error('Error: No group defined for decorated key-value pair: "' + keyValuePair + '"');
                }
                i++;  // Next key-value already used, so skip in next iteration
                continue;
            }
        }

        // TODO: Handle regular comments. Skip for now.
        if (line.trim().startsWith('#')) continue;

        // Add non-comment lines to plainData
        plainData.push(line);
    }
    
    return { decorated: decoratedData, plain: plainData };
}

/**
 * Rebuilds a configuration file from parsed data.
 * @param {Object} parsedConfig - The parsed configuration object containing decorated and plain data
 * @returns {string} Rebuilt configuration file content
 */
export function rebuildYaml(parsedConfig, file) {
    let rebuiltConfig = '';

    // Rebuild decorated groups
    for (const group in parsedConfig.decorated) {
        rebuiltConfig += '#$ group\n' + group + ':\n';
        parsedConfig.decorated[group].forEach(pair => {
            rebuiltConfig += '  ' + pair.comment + '\n' + '  ' + pair.id + ': ' + pair.value + '\n';
        });
        rebuiltConfig += '\n';
    }

    // Append plain YAML content
    rebuiltConfig += parsedConfig.plain.join('\n');

    return rebuiltConfig;
}

// Example usage
// const file = 'config.yaml';
// const fileContents = fs.readFileSync(file, 'utf8');
// parsedConfig = parseConfig(fileContents);
// console.log(parsedConfig);

// rebuiltConfig = rebuildConfig(parsedConfig, file);
// fs.writeFileSync(file, rebuiltConfig);
// console.log(rebuiltConfig);

/**
Parsed Config Example:
    {
    decorated: {
        transmitter: [
            {
            id: 'frequency',
            value: '50',
            comment: '#$ tag:input type:range min:1 max:100 step:1',
            tag: 'input',
            type: 'range',
            min: '1',
            max: '100',
            step: '1'
            },
        ],
        receiver: [
            {
            id: 'power',
            value: '5',
            comment: '#$ tag:input type:number min:0 max:10 step:1',
            tag: 'input',
            type: 'number',
            min: '0',
            max: '10',
            step: '1'
            }
        ]
    },
    plain: [ 'pinset:', '  pin1: 1', '  pin2: 2' ]
    }
 **/