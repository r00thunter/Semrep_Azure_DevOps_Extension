# Semgrep Task Input UI

This directory contains the custom UI components for the Semgrep Azure DevOps extension task configuration.

## Files

- **task-inputs.html**: Main HTML structure for the configuration form
- **task-inputs.css**: Styling and visual design
- **task-inputs.js**: JavaScript logic for form interactions, validation, and state management

## Features

### UI Components
- ✅ Collapsible sections (accordion-style)
- ✅ Modern, responsive design
- ✅ Real-time form validation
- ✅ Conditional field visibility
- ✅ Help tooltips
- ✅ Severity badges with color coding
- ✅ Toggle switches for boolean options
- ✅ Custom checkboxes and form controls

### Functionality
- ✅ Section expand/collapse
- ✅ Form validation with error messages
- ✅ State persistence (localStorage)
- ✅ Configuration preview
- ✅ Reset to defaults
- ✅ Conditional field display based on selections
- ✅ Ticket type checkbox handling

## Usage

### In Azure DevOps

The UI files are automatically included when the extension is packaged. However, Azure DevOps task inputs are typically configured through `task.json` and rendered using the default Azure DevOps form renderer.

### Standalone Usage

You can open `task-inputs.html` directly in a browser to:
- Preview the UI design
- Test form interactions
- Validate the user experience

### Integration

To integrate this UI with Azure DevOps:

1. **Option 1: Custom Contribution** (Advanced)
   - Create a custom contribution point in `vss-extension.json`
   - Reference the HTML file in the contribution properties

2. **Option 2: Task Input UI** (If supported)
   - Reference the UI files in `task.json`
   - Azure DevOps will render the custom UI

3. **Option 3: Documentation/Preview**
   - Use as a reference for users
   - Generate screenshots for documentation
   - Test form logic before implementation

## Browser Support

- Chrome/Edge (latest)
- Firefox (latest)
- Safari (latest)

## Development

### Making Changes

1. Edit the HTML, CSS, or JavaScript files
2. Test in browser by opening `task-inputs.html`
3. Rebuild the extension: `npm run build`
4. Package the extension: `npm run package`

### Testing

Open `task-inputs.html` in a browser and test:
- Form validation
- Section toggling
- Conditional field visibility
- State persistence (check localStorage)
- All form interactions

## Notes

- The UI uses modern CSS (CSS Variables, Flexbox, Grid)
- JavaScript is vanilla ES6+ (no dependencies)
- Form data is saved to localStorage for testing
- In production, form data would be submitted to Azure DevOps task system

## Future Enhancements

- [ ] Modal dialogs for preview/confirmation
- [ ] Toast notifications component
- [ ] Export/import configuration
- [ ] Configuration templates/presets
- [ ] Accessibility improvements (ARIA labels, keyboard navigation)
- [ ] Dark mode support
