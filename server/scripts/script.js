// import { parseYaml, rebuildYaml } from './yaml-parser.js';

// Constants
const FORM_CONFIG = {
  FORM_ID: 'config-form',
  ENDPOINTS: {
    DATA: '/data',
  },
  CLASSES: {
    CONTROL_CONTAINER: 'control-container',
    GROUP_CONTAINER: 'group-container',
  },
};

// Types of form controls
const ControlType = {
  INPUT: 'input',
  SELECT: 'select',
};

class FormBuilder {
  constructor(configData) {
    this.configData = configData;
  }

  /**
   * Creates and returns the main form element
   * @returns {HTMLFormElement}
   */
  createForm() {
    const form = document.createElement('form');
    form.id = FORM_CONFIG.FORM_ID;
    
    this.appendControlGroups(form);
    this.appendSubmitButton(form);
    this.attachSubmitHandler(form);
    
    return form;
  }

  /**
   * Creates form control groups based on configuration
   * @param {HTMLFormElement} form 
   */
  appendControlGroups(form) {
    Object.entries(this.configData).forEach(([groupName, controls]) => {
      const groupContainer = this.createGroupContainer(groupName);
      controls.forEach(controlData => {
        const control = this.createFormControl(controlData);
        if (control) {
          groupContainer.appendChild(control);
        }
      });
      form.appendChild(groupContainer);
    });
  }

  /**
   * Creates a container for a group of controls
   * @param {string} groupName 
   * @returns {HTMLDivElement}
   */
  createGroupContainer(groupName) {
    const container = document.createElement('div');
    container.classList.add(FORM_CONFIG.CLASSES.GROUP_CONTAINER);
    container.id = groupName;

    const header = document.createElement('h2');
    header.textContent = groupName;
    container.appendChild(header);

    return container;
  }

  /**
   * Creates a form control based on control data
   * @param {Object} controlData 
   * @returns {HTMLDivElement|null}
   */
  createFormControl(controlData) {
    const container = document.createElement('div');
    container.classList.add(FORM_CONFIG.CLASSES.CONTROL_CONTAINER);

    const label = this.createLabel(controlData.id, controlData.unit);
    container.appendChild(label);

    switch (controlData.tag) {
      case ControlType.INPUT:
        return this.handleInputControl(container, controlData);
      case ControlType.SELECT:
        return this.handleSelectControl(container, controlData);
      default:
        console.warn(`Unsupported control type: ${controlData.tag}`);
        return null;
    }
  }

  /**
   * Handles creation of input controls
   * @param {HTMLDivElement} container 
   * @param {Object} controlData 
   * @returns {HTMLDivElement}
   */
  handleInputControl(container, controlData) {
    const input = this.createInput(controlData);
    
    if (controlData.type === 'range') {
      const valueLabel = this.createValueLabel(controlData.value);
      container.appendChild(valueLabel);
      this.attachRangeListener(input, valueLabel);
    }

    if (controlData.type === 'checkbox') {
      container.appendChild(this.createHiddenCheckboxInput(controlData.id));
    }

    container.appendChild(input);
    return container;
  }

  /**
   * Creates an input element with the specified configuration
   * @param {Object} controlData 
   * @returns {HTMLInputElement}
   */
  createInput(controlData) {
    const input = document.createElement('input');
    input.type = controlData.type;
    input.id = controlData.id;
    input.name = controlData.id;

    if (controlData.type === 'number') {
      input.placeholder = controlData.value;
    }
    
    if (controlData.type === 'checkbox') {
      // Convert string 'true'/'false' to boolean
      input.checked = controlData.value === 'true' || controlData.value === true;
    }

    // Apply valid configuration properties
    Object.entries(controlData)
      .filter(([_, value]) => value !== undefined)
      .forEach(([key, value]) => {
        if (key !== 'value' || controlData.type !== 'checkbox') {
          input[key] = value;
        }
      });

    return input;
  }

  /**
   * Handles creation of select controls
   * @param {HTMLDivElement} container 
   * @param {Object} controlData 
   * @returns {HTMLDivElement}
   */
  handleSelectControl(container, controlData) {
    const select = this.createSelect(controlData);
    container.appendChild(select);
    return container;
  }

  /**
   * Creates a select element with options
   * @param {Object} controlData 
   * @returns {HTMLSelectElement}
   */
  createSelect(controlData) {
    const select = document.createElement('select');
    select.id = controlData.id;
    select.name = controlData.id;

    controlData.options.split(',').forEach(option => {
      const optionElement = document.createElement('option');
      optionElement.value = option;
      optionElement.textContent = option;
      select.appendChild(optionElement);
    });

    select.value = controlData.value;

    return select;
  }

  /**
   * Creates a label element
   * @param {string} id 
   * @param {string} unit 
   * @returns {HTMLLabelElement}
   */
  createLabel(id, unit) {
    const label = document.createElement('label');
    label.htmlFor = id;
    label.textContent = `${id}${unit ? ` (${unit})` : ''}: `;
    return label;
  }

  /**
   * Creates a value label element
   * @param {string|number} value 
   * @returns {HTMLParagraphElement}
   */
  createValueLabel(value) {
    const label = document.createElement('p');
    label.textContent = value;
    return label;
  }

  /**
   * Creates a hidden input for checkbox support
   * @param {string} id 
   * @returns {HTMLInputElement}
   */
  createHiddenCheckboxInput(id) {
    const input = document.createElement('input');
    input.type = 'hidden';
    input.id = `${id}-hidden`;
    input.name = id;
    input.value = 'false';
    return input;
  }

  /**
   * Attaches event listener for range input
   * @param {HTMLInputElement} input 
   * @param {HTMLParagraphElement} valueLabel 
   */
  attachRangeListener(input, valueLabel) {
    input.addEventListener('input', () => {
      valueLabel.textContent = input.value;
    });
  }

  /**
   * Appends submit button to form
   * @param {HTMLFormElement} form 
   */
  appendSubmitButton(form) {
    const submitButton = document.createElement('input');
    submitButton.type = 'submit';
    form.appendChild(submitButton);
  }

  /**
   * Attaches submit handler to form
   * @param {HTMLFormElement} form 
   */
  attachSubmitHandler(form) {
    form.addEventListener('submit', async (event) => {
      event.preventDefault();
      await this.handleFormSubmit(form);
    });
  }

  /**
   * Handles form submission
   * @param {HTMLFormElement} form 
   */
  async handleFormSubmit(form) {
    try {
      const formData = new FormData(form);
      const formBody = Object.fromEntries(formData);

      // Handle checkbox values
      const checkboxes = form.querySelectorAll('input[type="checkbox"]');
      checkboxes.forEach(checkbox => {
        formBody[checkbox.name] = checkbox.checked.toString();
      });

      this.updateConfigData(formBody);
      await this.sendFormData();
    } catch (error) {
      console.error('Error submitting form:', error);
      // Here you could add user-facing error handling
    }
  }

  /**
   * Updates config data with form values
   * @param {Object} formBody 
   */
  updateConfigData(formBody) {
    Object.entries(this.configData).forEach(([_, controls]) => {
      controls.forEach(control => {
        if (formBody[control.id] !== undefined) {
          control.value = formBody[control.id];
        }
      });
    });
  }

  /**
   * Sends form data to server
   */
  async sendFormData() {
    const response = await fetch(FORM_CONFIG.ENDPOINTS.DATA, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(this.configData)
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    const responseText = await response.text();
    alert(responseText);
  }
}

/**
 * Fetches configuration data from server
 * @returns {Promise<string>}
 */
async function fetchConfigData() {
  try {
    const response = await fetch(FORM_CONFIG.ENDPOINTS.DATA, {
      method: 'GET',
      headers: {
        'Accept': 'application/json',
      },
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    return await response.json();
  } catch (error) {
    console.error('Error fetching config data:', error);
    throw error;
  }
}

/**
 * Main application entry point
 */
async function main() {
  try {
    const configData = await fetchConfigData();
    // const parsedConfig = parseYaml(configData);
    // const formBuilder = new FormBuilder(parsedConfig);
    const formBuilder = new FormBuilder(configData);
    document.body.appendChild(formBuilder.createForm());
  } catch (error) {
    console.error('Error initializing application:', error);
    // Here you could add user-facing error handling
  }
}

main();