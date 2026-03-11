# UI Implementation Plan - Semgrep Azure DevOps Extension

## 🎯 Objective

Create a beautiful, fully functional form-based UI for configuring the Semgrep scan task, replacing the need for YAML configuration. Users should be able to configure all scan options through an intuitive, modern interface similar to Snyk extension.

---

## 📋 Current State

### What Exists
- ✅ Complete `task.json` with all input parameters
- ✅ Input grouping (scan, tickets, sast, sca, license, summary, advanced)
- ✅ Visibility rules for conditional fields
- ✅ Help text and descriptions
- ❌ No custom UI - relies on default Azure DevOps form rendering

### What's Needed
- 🎨 Custom HTML/CSS/JavaScript UI
- 🎨 Modern, responsive design
- 🎨 Collapsible sections
- 🎨 Real-time validation
- 🎨 Visual feedback and previews
- 🎨 Help tooltips and inline guidance

---

## 🏗️ Architecture

### Azure DevOps UI Support

Azure DevOps extensions support custom task input UI through:
1. **Task Input UI**: HTML/JavaScript files referenced in `task.json`
2. **Contribution Points**: Custom UI contributions
3. **Modern Web Stack**: HTML5, CSS3, JavaScript/TypeScript

### Recommended Approach

**Option 1: Task Input UI (Recommended)**
- Create `task-inputs.html` and `task-inputs.js`
- Reference in `task.json` via `inputs` contribution
- Full control over UI/UX
- Works in both Classic and YAML pipelines

**Option 2: Custom Contribution**
- Create a custom contribution point
- More complex but more flexible
- Better for complex workflows

**Decision: Use Option 1 (Task Input UI)** - Simpler, well-supported, meets requirements

---

## 🎨 UI Design Plan

### Design Principles
1. **Modern & Clean**: Similar to Snyk extension aesthetic
2. **Intuitive**: Clear grouping and logical flow
3. **Responsive**: Works on different screen sizes
4. **Accessible**: WCAG 2.1 AA compliance
5. **Fast**: Lightweight, minimal dependencies

### Visual Structure

```
┌─────────────────────────────────────────────────┐
│  Semgrep Security Scan Configuration           │
├─────────────────────────────────────────────────┤
│                                                 │
│  📋 Scan Configuration                    [▼]   │
│  ┌─────────────────────────────────────────┐ │
│  │ Semgrep App Token: [••••••••]  [🔒]     │ │
│  │ Scan Type: [PR Scan ▼]                   │ │
│  │ Baseline Ref: [origin/master]            │ │
│  └─────────────────────────────────────────┘ │
│                                                 │
│  🎫 Ticket Creation                      [▼]   │
│  ┌─────────────────────────────────────────┐ │
│  │ ☑ Enable Ticket Creation                 │ │
│  │ Ticket Types: [☑ SAST] [☑ SCA] [☐ License]│ │
│  │                                           │ │
│  │ 📊 SAST Filters                    [▼]   │ │
│  │ Severities: [☑ Critical] [☑ High] ...    │ │
│  │ Confidences: [☑ High] [☑ Medium] ...     │ │
│  │                                           │ │
│  │ 🔗 SCA Filters                      [▼]   │ │
│  │ Severities: [☑ Critical] [☑ High] ...    │ │
│  │ Reachabilities: [☑ Always Reachable] ... │ │
│  │                                           │ │
│  │ 📜 License Configuration            [▼]   │ │
│  │ ☑ Use Default Whitelist                   │ │
│  │ Additional Licenses: [textarea]            │ │
│  └─────────────────────────────────────────┘ │
│                                                 │
│  📊 Summary & PR                          [▼]  │
│  ┌─────────────────────────────────────────┐ │
│  │ ☑ Generate Summary                       │ │
│  │ Display Mode: [Both ▼]                    │ │
│  │ ☐ Create Fix PR                           │ │
│  │ Branch Prefix: [semgrep-fixes/]           │ │
│  └─────────────────────────────────────────┘ │
│                                                 │
│  ⚙️ Advanced Configuration              [▼]    │
│  ┌─────────────────────────────────────────┐ │
│  │ Deployment ID: [15145]                   │ │
│  │ CSV URLs, Log Level, etc.                │ │
│  └─────────────────────────────────────────┘ │
│                                                 │
│  [Preview Configuration] [Save] [Cancel]        │
└─────────────────────────────────────────────────┘
```

---

## 📁 File Structure

```
extension/
├── tasks/
│   └── semgrepScan/
│       ├── task.json              # Updated with UI references
│       ├── task.ts
│       ├── task.js
│       └── ui/                    # NEW - UI components
│           ├── task-inputs.html   # Main UI form
│           ├── task-inputs.js      # UI logic and validation
│           ├── task-inputs.css    # Styling
│           └── assets/            # Images, icons
│               └── icons/
```

---

## 🛠️ Implementation Plan

### Phase 1: Foundation (Week 1)

#### 1.1 Setup UI Infrastructure
- [ ] Create `extension/tasks/semgrepScan/ui/` directory
- [ ] Create base HTML structure (`task-inputs.html`)
- [ ] Create CSS framework (`task-inputs.css`)
- [ ] Create JavaScript framework (`task-inputs.js`)
- [ ] Set up build process to copy UI files

#### 1.2 Basic Form Structure
- [ ] Create form container with sections
- [ ] Implement collapsible sections (accordion)
- [ ] Add section headers with icons
- [ ] Implement basic styling (colors, fonts, spacing)

#### 1.3 Integration with task.json
- [ ] Update `task.json` to reference UI files
- [ ] Map input fields to task.json inputs
- [ ] Test basic form rendering

### Phase 2: Core Form Fields (Week 1-2)

#### 2.1 Scan Configuration Section
- [ ] Semgrep App Token input (secure, masked)
- [ ] Scan Type dropdown (PR Scan / Full Scan)
- [ ] Baseline Reference input (conditional on PR Scan)
- [ ] Semgrep Organization input (optional)
- [ ] Real-time validation

#### 2.2 Ticket Creation Section
- [ ] Enable Ticket Creation toggle
- [ ] Ticket Types multi-select (SAST, SCA, License, All)
- [ ] Conditional display based on selections
- [ ] Visual indicators for selected types

#### 2.3 SAST Filters Section
- [ ] Severity multi-select checkboxes (Critical, High, Medium, Low)
- [ ] Confidence multi-select checkboxes (High, Medium, Low)
- [ ] Visual severity indicators (color-coded)
- [ ] Preview of selected filters

#### 2.4 SCA Filters Section
- [ ] Severity multi-select checkboxes
- [ ] Reachability multi-select checkboxes
- [ ] Transitivity options
- [ ] Visual reachability indicators

#### 2.5 License Configuration Section
- [ ] Use Default Whitelist toggle
- [ ] License whitelist override textarea
- [ ] Preview of default licenses
- [ ] Add/remove license functionality

### Phase 3: Advanced Features (Week 2)

#### 3.1 Summary & PR Section
- [ ] Generate Summary toggle
- [ ] Summary Display Mode dropdown
- [ ] Create Fix PR toggle
- [ ] Branch Prefix input (conditional)
- [ ] Group Fix PRs toggle (conditional)

#### 3.2 Advanced Configuration Section
- [ ] Deployment ID input
- [ ] CSV URL inputs (iteration list, area path)
- [ ] Default Iteration Path input
- [ ] Log Level dropdown
- [ ] Enable Metrics toggle
- [ ] Custom Rule Filters textarea

#### 3.3 Validation & Feedback
- [ ] Real-time field validation
- [ ] Error messages and warnings
- [ ] Success indicators
- [ ] Required field indicators
- [ ] Help tooltips on hover

### Phase 4: Polish & UX (Week 2-3)

#### 4.1 Visual Enhancements
- [ ] Modern color scheme (Semgrep brand colors)
- [ ] Smooth animations and transitions
- [ ] Loading states
- [ ] Icons and visual indicators
- [ ] Responsive design (mobile-friendly)

#### 4.2 User Experience
- [ ] Form state persistence (localStorage)
- [ ] Configuration preview
- [ ] Export/Import configuration
- [ ] Reset to defaults
- [ ] Keyboard navigation support

#### 4.3 Help & Guidance
- [ ] Inline help text
- [ ] Tooltips with detailed explanations
- [ ] Example configurations
- [ ] Link to documentation
- [ ] Contextual help based on selections

### Phase 5: Testing & Refinement (Week 3)

#### 5.1 Testing
- [ ] Cross-browser testing (Chrome, Edge, Firefox)
- [ ] Responsive design testing
- [ ] Accessibility testing (screen readers, keyboard)
- [ ] Integration testing with Azure DevOps
- [ ] User acceptance testing

#### 5.2 Refinement
- [ ] Performance optimization
- [ ] Code cleanup and documentation
- [ ] Bug fixes
- [ ] UI/UX improvements based on feedback

---

## 🎨 Design Specifications

### Color Scheme
- **Primary**: Semgrep brand colors (or Azure DevOps theme)
- **Success**: Green (#107C10)
- **Warning**: Orange (#FF8C00)
- **Error**: Red (#E81123)
- **Info**: Blue (#0078D4)
- **Background**: Light gray (#F8F8F8)
- **Text**: Dark gray (#323130)

### Typography
- **Font Family**: Segoe UI (Azure DevOps standard)
- **Headings**: Bold, 16-20px
- **Body**: Regular, 14px
- **Labels**: Semi-bold, 14px
- **Help Text**: Regular, 12px, gray

### Components

#### Input Fields
- **Text Input**: Standard Azure DevOps style
- **Dropdown**: Native select with custom styling
- **Checkbox**: Custom styled checkboxes
- **Toggle**: Modern toggle switch
- **Textarea**: Resizable, with character count

#### Sections
- **Collapsible**: Smooth expand/collapse animation
- **Icons**: Font Awesome or custom SVG icons
- **Borders**: Subtle borders, rounded corners
- **Spacing**: Consistent padding and margins

---

## 💻 Technology Stack

### Core Technologies
- **HTML5**: Semantic markup
- **CSS3**: Modern styling (Flexbox, Grid, Custom Properties)
- **JavaScript (ES6+)**: Form logic and validation
- **No Frameworks**: Keep it lightweight (or minimal dependency)

### Optional Enhancements
- **TypeScript**: For type-safe JavaScript (if needed)
- **CSS Preprocessor**: Sass/SCSS (if needed)
- **Build Tools**: Webpack/Rollup (if needed for bundling)

### Azure DevOps Integration
- **VSS SDK**: Azure DevOps UI SDK (if needed)
- **Task Lib**: For accessing task context (if needed)

---

## 📐 UI Component Specifications

### 1. Scan Configuration Section

```html
<section class="config-section" data-section="scan">
  <header class="section-header">
    <span class="icon">🔍</span>
    <h3>Scan Configuration</h3>
    <button class="toggle-section">▼</button>
  </header>
  <div class="section-content">
    <div class="form-group">
      <label>Semgrep App Token *</label>
      <input type="password" name="semgrepAppToken" required>
      <span class="help-text">Store as secure variable</span>
    </div>
    <div class="form-group">
      <label>Scan Type *</label>
      <select name="scanType">
        <option value="PR Scan">PR Scan</option>
        <option value="Full Scan">Full Scan</option>
      </select>
    </div>
    <div class="form-group conditional" data-show="scanType == 'PR Scan'">
      <label>Baseline Reference</label>
      <input type="text" name="baselineRef" value="origin/master">
    </div>
  </div>
</section>
```

### 2. Ticket Creation Section

```html
<section class="config-section" data-section="tickets">
  <header class="section-header">
    <span class="icon">🎫</span>
    <h3>Ticket Creation</h3>
    <button class="toggle-section">▼</button>
  </header>
  <div class="section-content">
    <div class="form-group">
      <label class="toggle-label">
        <input type="checkbox" name="enableTicketCreation" checked>
        <span class="toggle-switch"></span>
        Enable Ticket Creation
      </label>
    </div>
    <div class="form-group conditional" data-show="enableTicketCreation">
      <label>Ticket Types</label>
      <div class="checkbox-group">
        <label><input type="checkbox" name="ticketTypes" value="SAST"> SAST</label>
        <label><input type="checkbox" name="ticketTypes" value="SCA"> SCA</label>
        <label><input type="checkbox" name="ticketTypes" value="License"> License</label>
        <label><input type="checkbox" name="ticketTypes" value="All"> All</label>
      </div>
    </div>
  </div>
</section>
```

### 3. Filter Sections (SAST/SCA)

```html
<section class="config-section nested" data-section="sast">
  <header class="section-header">
    <span class="icon">📊</span>
    <h4>SAST Ticket Filters</h4>
    <button class="toggle-section">▼</button>
  </header>
  <div class="section-content">
    <div class="form-group">
      <label>Severities</label>
      <div class="checkbox-group severity-group">
        <label class="severity-critical">
          <input type="checkbox" name="sastSeverities" value="Critical">
          <span class="severity-badge critical">Critical</span>
        </label>
        <label class="severity-high">
          <input type="checkbox" name="sastSeverities" value="High">
          <span class="severity-badge high">High</span>
        </label>
        <!-- More options -->
      </div>
    </div>
  </div>
</section>
```

---

## 🔧 Implementation Details

### JavaScript Architecture

```javascript
// task-inputs.js structure
class SemgrepTaskUI {
  constructor() {
    this.form = document.getElementById('semgrep-config-form');
    this.sections = {};
    this.validators = {};
    this.init();
  }
  
  init() {
    this.loadSavedState();
    this.setupEventListeners();
    this.setupValidation();
    this.setupConditionalFields();
    this.setupTooltips();
  }
  
  setupEventListeners() {
    // Toggle sections
    // Field changes
    // Validation triggers
  }
  
  setupValidation() {
    // Real-time validation
    // Error display
    // Success indicators
  }
  
  setupConditionalFields() {
    // Show/hide based on conditions
    // Visibility rules from task.json
  }
  
  saveState() {
    // Save to localStorage
  }
  
  loadSavedState() {
    // Load from localStorage
  }
  
  validateForm() {
    // Full form validation
  }
  
  getFormData() {
    // Return form data as object
  }
  
  previewConfiguration() {
    // Show preview of configuration
  }
}
```

### CSS Architecture

```css
/* task-inputs.css structure */

/* Variables */
:root {
  --primary-color: #0078D4;
  --success-color: #107C10;
  --error-color: #E81123;
  --bg-color: #F8F8F8;
  --text-color: #323130;
  --border-radius: 4px;
  --spacing: 16px;
}

/* Base Styles */
.semgrep-config-container {
  font-family: 'Segoe UI', sans-serif;
  background: white;
  padding: var(--spacing);
}

/* Section Styles */
.config-section {
  margin-bottom: var(--spacing);
  border: 1px solid #e0e0e0;
  border-radius: var(--border-radius);
  overflow: hidden;
}

.section-header {
  display: flex;
  align-items: center;
  padding: var(--spacing);
  background: var(--bg-color);
  cursor: pointer;
}

.section-content {
  padding: var(--spacing);
  display: none; /* Collapsed by default */
}

.section-content.expanded {
  display: block;
}

/* Form Elements */
.form-group {
  margin-bottom: var(--spacing);
}

/* Severity Badges */
.severity-badge {
  padding: 4px 8px;
  border-radius: 3px;
  font-size: 12px;
  font-weight: 600;
}

.severity-critical { background: #E81123; color: white; }
.severity-high { background: #FF8C00; color: white; }
.severity-medium { background: #FFB900; color: black; }
.severity-low { background: #107C10; color: white; }

/* Animations */
@keyframes slideDown {
  from { opacity: 0; transform: translateY(-10px); }
  to { opacity: 1; transform: translateY(0); }
}
```

---

## 🔗 Integration with task.json

### Update task.json

```json
{
  "execution": {
    "Node": {
      "target": "task.js"
    }
  },
  "inputs": [
    // ... existing inputs
  ],
  "contributions": [
    {
      "id": "semgrep-task-inputs",
      "type": "ms.vss-distributed-task.task-inputs",
      "targets": [
        "ms.vss-distributed-task.tasks"
      ],
      "properties": {
        "name": "semgrepScan",
        "uri": "ui/task-inputs.html"
      }
    }
  ]
}
```

### File References

Update `vss-extension.json` to include UI files:

```json
{
  "files": [
    {
      "path": "extension/tasks/semgrepScan",
      "addressable": true
    },
    {
      "path": "extension/tasks/semgrepScan/ui",
      "addressable": true
    }
  ]
}
```

---

## 📋 Implementation Checklist

### Phase 1: Foundation
- [ ] Create UI directory structure
- [ ] Create base HTML file
- [ ] Create CSS framework
- [ ] Create JavaScript framework
- [ ] Update task.json with UI references
- [ ] Update vss-extension.json
- [ ] Test basic rendering

### Phase 2: Form Fields
- [ ] Scan Configuration section
- [ ] Ticket Creation section
- [ ] SAST Filters section
- [ ] SCA Filters section
- [ ] License Configuration section
- [ ] Summary & PR section
- [ ] Advanced Configuration section

### Phase 3: Functionality
- [ ] Conditional field visibility
- [ ] Form validation
- [ ] State persistence
- [ ] Configuration preview
- [ ] Help tooltips
- [ ] Error handling

### Phase 4: Polish
- [ ] Styling and animations
- [ ] Responsive design
- [ ] Accessibility
- [ ] Performance optimization
- [ ] Cross-browser testing

### Phase 5: Integration
- [ ] Test in Azure DevOps
- [ ] Verify form data mapping
- [ ] Test in Classic pipelines
- [ ] Test in YAML pipelines
- [ ] User acceptance testing

---

## 🎯 Success Criteria

1. ✅ **Beautiful UI**: Modern, clean, professional appearance
2. ✅ **Fully Functional**: All configuration options accessible
3. ✅ **Intuitive**: Easy to understand and use
4. ✅ **Responsive**: Works on different screen sizes
5. ✅ **Accessible**: Keyboard navigation, screen reader support
6. ✅ **Fast**: Quick load times, smooth interactions
7. ✅ **Validated**: Real-time validation and error messages
8. ✅ **Helpful**: Tooltips, examples, guidance

---

## 📚 Resources & References

### Azure DevOps Documentation
- Task Input UI: https://docs.microsoft.com/en-us/azure/devops/extend/develop/add-build-task
- UI Contribution Points: https://docs.microsoft.com/en-us/azure/devops/extend/reference/targets/overview

### Design Inspiration
- Snyk Extension UI
- Azure DevOps native forms
- Modern web form best practices

### Tools & Libraries
- **Icons**: Font Awesome, Material Icons, or custom SVG
- **Validation**: Native HTML5 + custom JavaScript
- **Styling**: Pure CSS3 (or minimal framework)

---

## ⏱️ Estimated Timeline

- **Phase 1 (Foundation)**: 2-3 days
- **Phase 2 (Form Fields)**: 3-4 days
- **Phase 3 (Functionality)**: 2-3 days
- **Phase 4 (Polish)**: 2-3 days
- **Phase 5 (Integration & Testing)**: 2-3 days

**Total**: ~2-3 weeks for complete implementation

---

## 🚀 Next Steps

1. **Review and approve this plan**
2. **Gather design requirements** (colors, branding, specific UI elements)
3. **Start Phase 1**: Create base structure
4. **Iterate**: Build and test incrementally
5. **Refine**: Based on user feedback

---

## ❓ Questions to Clarify

1. **Design Preferences**:
   - Specific color scheme? (Semgrep brand colors?)
   - Icon style preference? (Material, Font Awesome, custom?)
   - Any specific UI patterns to follow?

2. **Functionality**:
   - Should UI support saving/loading configurations?
   - Export/import configuration files?
   - Configuration templates/presets?

3. **Integration**:
   - Should UI work in both Classic and YAML pipelines?
   - Any specific Azure DevOps version requirements?

---

**Ready to proceed with implementation once plan is approved!** 🚀
