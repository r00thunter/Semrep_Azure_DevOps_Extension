# Semgrep Azure DevOps Extension - Implementation Plan

## Overview
This document outlines the plan for building a comprehensive Azure DevOps extension that consolidates the existing 3 scripts into a single, user-friendly extension with advanced UI and functionality.

## Project Structure

```
semgrep_ado_ext/
├── .vscode/                    # VS Code settings
├── extension/                  # Extension source code
│   ├── tasks/                  # Azure DevOps tasks
│   │   └── semgrepScan/        # Main Semgrep scan task
│   │       ├── task.json       # Task definition
│   │       ├── task.ts         # Task implementation (TypeScript)
│   │       ├── inputs/         # Input parameter definitions
│   │       └── lib/            # Helper libraries
│   ├── scripts/                # Python/Node scripts
│   │   ├── scan_executor.py    # Scan execution logic
│   │   ├── ticket_creator.py   # Work item creation
│   │   ├── summary_generator.py # Summary report generation
│   │   └── pr_creator.py       # PR creation with fixes
│   ├── ui/                     # UI components
│   │   ├── task-inputs.html    # Task input UI
│   │   ├── task-inputs.js      # UI logic
│   │   └── styles.css          # Styling
│   └── icons/                  # Extension icons
├── package.json                # Node.js dependencies
├── vss-extension.json          # Extension manifest
├── tsconfig.json               # TypeScript config
├── README.md                   # Documentation
└── IMPLEMENTATION_PLAN.md      # This file
```

## Architecture Components

### 1. Extension Manifest (vss-extension.json)
- Extension metadata
- Contribution points for pipeline task
- Icons and branding

### 2. Task Definition (task.json)
- Input parameters:
  - **Scan Configuration:**
    - `scanType` (dropdown: "PR Scan" | "Full Scan")
    - `semgrepAppToken` (secure string)
    - `semgrepOrg` (string, optional)
    - `baselineRef` (string, default: "origin/master")
  
  - **Ticket Creation:**
    - `enableTicketCreation` (boolean)
    - `ticketTypes` (multi-select: "SAST", "SCA", "License", "All")
    
  - **SAST Ticket Filters:**
    - `sastSeverities` (multi-select: Critical, High, Medium, Low)
    - `sastConfidences` (multi-select: High, Medium, Low)
    
  - **SCA Ticket Filters:**
    - `scaSeverities` (multi-select: Critical, High, Medium, Low)
    - `scaReachabilities` (multi-select: Always Reachable, Reachable, Direct, Transitive)
    
  - **License Configuration:**
    - `licenseWhitelist` (multi-line string - comma/newline separated)
    - `useDefaultLicenseWhitelist` (boolean, default: true) - Use global default with override option
    - `defaultApprovedLicenses` (pre-populated with your current list)
  
  - **CSV Configuration:**
    - `iterationListCsvUrl` (string) - URL to iteration list CSV (configurable)
    - `azureDevPathCsvUrl` (string) - URL to Azure DevOps path mapping CSV (configurable)
    - `defaultIterationPath` (string, default: "Engineering\\2025-Sprints") - Fallback if CSV unavailable
  
  - **Summary & PR:**
    - `generateSummary` (boolean, default: true)
    - `summaryDisplayMode` (dropdown: "Logs Only" | "Tab Only" | "Both", default: "Both")
    - `createFixPR` (boolean, default: false)
    - `fixPRBranchPrefix` (string, default: "semgrep-fixes/")
    - `groupFixPRsByType` (boolean, default: true) - Group fixes by rule type (SAST, SCA, etc.)
  
  - **Deployment Configuration:**
    - `deploymentId` (string, default: "15145") - Static deployment ID for Fareportal
    - `semgrepDeploymentSlug` (string, optional) - Deployment slug (fetched dynamically if not provided)

### 3. Task Implementation (TypeScript/Node.js)
- Main entry point that:
  - Validates inputs
  - Executes scan via Python script
  - Processes findings
  - Creates tickets based on filters
  - Generates summary
  - Optionally creates fix PR

### 4. Python Scripts

#### 4.1 scan_executor.py
- Handles full and differential scans
- Manages Semgrep CLI execution
- Outputs findings.json
- Handles PR vs master branch logic

#### 4.2 ticket_creator.py
- Consolidated work item creation logic
- Supports SAST, SCA, and License ticket types
- Applies user-defined filters
- Checks for existing work items
- Integrates with Azure DevOps APIs

#### 4.3 summary_generator.py
- Generates comprehensive summary report
- Uses Semgrep API: `GET /api/v1/deployments/{deploymentSlug}/findings`
- Extracts detailed information from API response:
  - **Vulnerability descriptions**: `assistant.rule_explanation.explanation` and `assistant.rule_explanation.summary`
  - **Code samples**: `location` object (filePath, line, column, endLine, endColumn)
  - **Fix recommendations**: 
    - `assistant.autofix.fix_code` - Auto-fix code
    - `assistant.guidance.instructions` and `assistant.guidance.summary` - Fix guidance
  - **Rule details**: `rule.message`, `rule.cweNames`, `rule.owaspNames`, `rule.vulnerabilityClasses`
  - **Click-to-fix PRs**: `click_to_fix_prs` array (if available)
- Outputs as:
  - Markdown/HTML for pipeline logs
  - Test results format for Azure DevOps tab view (when `summaryDisplayMode` includes "Tab")

#### 4.4 pr_creator.py
- Analyzes findings for auto-fixable issues
- Uses `assistant.autofix.fix_code` from Semgrep API response
- Checks `click_to_fix_prs` array to see if PRs already exist
- Creates new branch with pattern: `{fixPRBranchPrefix}{rule-type}-{timestamp}`
- Groups fixes by rule type (SAST, SCA, License) when `groupFixPRsByType` is true
- Applies fixes using autofix code from API
- Creates PR with:
  - Fix description
  - Links to original findings
  - Code samples showing before/after
- Uses Azure DevOps Git API for PR creation

### 5. UI Components
- Modern, Snyk-like interface
- Collapsible sections for different configuration areas
- Real-time validation
- Help text and tooltips
- Preview of selected filters

## Implementation Phases

### Phase 1: Foundation (Week 1)
1. ✅ Set up project structure
2. ✅ Create extension manifest
3. ✅ Create basic task.json with all input parameters
4. ✅ Set up TypeScript/Node.js build pipeline
5. ✅ Create basic task implementation skeleton

### Phase 2: Scan Execution (Week 1-2)
1. ✅ Implement scan_executor.py
2. ✅ Integrate with task.ts
3. ✅ Handle PR vs Full scan logic
4. ✅ Test scan execution in pipeline

### Phase 3: Ticket Creation (Week 2-3)
1. ✅ Refactor ticket_creator.py from existing scripts
2. ✅ Implement filter logic for SAST (severity + confidence)
3. ✅ Implement filter logic for SCA (severity + reachability)
4. ✅ Implement License whitelist filtering
5. ✅ Integrate with task.ts
6. ✅ Test ticket creation with various filters

### Phase 4: Summary & UI (Week 3-4)
1. ✅ Implement summary_generator.py
2. ✅ Fetch detailed finding info from Semgrep APIs
3. ✅ Format summary with code samples and fixes
4. ✅ Create task-inputs.html UI
5. ✅ Style UI to match Snyk extension
6. ✅ Add validation and help text

### Phase 5: PR Creation (Week 4)
1. ✅ Research Semgrep autofix capabilities
2. ✅ Implement pr_creator.py
3. ✅ Integrate with Azure DevOps Git API
4. ✅ Test PR creation workflow

### Phase 6: Testing & Documentation (Week 5)
1. ✅ End-to-end testing
2. ✅ Error handling improvements
3. ✅ Documentation
4. ✅ Package extension for distribution

## Key Technical Decisions

### 1. Language Choice
- **Task Implementation**: TypeScript/Node.js (standard for Azure DevOps extensions)
- **Business Logic**: Python (existing scripts are Python, easier migration)
- **Communication**: JSON files for data exchange between Node.js and Python

### 2. API Integration
- **Semgrep REST APIs:**
  - `GET /api/v1/deployments` - Get deployment slug
  - `GET /api/v1/deployments/{deploymentSlug}/findings` - Get findings with full details including:
    - `assistant.autofix.fix_code` - Auto-fix code
    - `assistant.guidance` - Fix guidance
    - `assistant.rule_explanation` - Vulnerability explanations
    - `click_to_fix_prs` - Existing autofix PRs
    - `location` - Code location details
    - `rule` - Rule metadata (CWE, OWASP, etc.)
  - `GET /api/v1/deployments/{deploymentId}/sbom/export` - SBOM export for license checking
  - `POST /api/sca/deployments/{id}/dependencies` - SCA dependency details
  - **Deployment ID**: Static value "15145" for Fareportal organization
- **Azure DevOps REST APIs:**
  - Work Item Tracking API - Create work items
  - Git API - Create PRs and branches
  - Repository API - Access CSV files (iterationlist.csv, azuredevpath.csv)

### 3. Configuration Management
- Store configuration in task.json inputs
- Use secure variables for tokens
- Support both UI and YAML pipeline configurations

### 4. Error Handling
- **Logging**: Configurable log level (default: INFO, can be set to DEBUG)
- **Error Strategy**:
  - Continue on non-critical errors (ticket creation failures, summary generation issues)
  - Fail pipeline only on scan execution errors
  - Log all errors with clear messages
  - Graceful degradation: if ticket creation fails, still generate summary
- **CSV Handling**:
  - If iterationlist.csv or azuredevpath.csv unavailable, use fallback defaults
  - Default iteration path: "Engineering\\2025-Sprints"
  - Default area path: "Engineering\\InfoSec\\DevSecOps\\SAST"

## Answers to Clarification Questions ✅

### 1. Semgrep APIs - ANSWERED ✅
- **API Endpoint**: `GET /api/v1/deployments/{deploymentSlug}/findings`
  - Provides full finding details including:
    - `assistant.autofix.fix_code` - Auto-fix code
    - `assistant.guidance` - Fix instructions and summary
    - `assistant.rule_explanation` - Vulnerability explanations
    - `click_to_fix_prs` - Existing autofix PRs
    - `location` - Code location (filePath, line, column, etc.)
    - `rule` - Rule metadata (CWE, OWASP, vulnerability classes)
- **Autofix**: Available via API response (`assistant.autofix.fix_code`), no CLI needed
- **Deployment ID**: Static value "15145" for Fareportal organization (not dynamic)

### 2. UI/UX - ANSWERED ✅
- **UI Design**: Use imagination to create modern, intuitive UI (no specific Snyk examples provided)
- **Summary Display**: **BOTH** - Display in pipeline logs AND as a separate tab in pipeline run

### 3. PR Auto-Fix - ANSWERED ✅
- **Approach**: Current plan approved
  - One PR per rule type (SAST fixes, SCA fixes, etc.)
  - Branch prefix: `semgrep-fixes/`
  - Created immediately when fixes are available

### 4. License Whitelist - ANSWERED ✅
- **Configuration**: Global default with override option
  - Pre-populate with default approved licenses list
  - Allow users to override/add additional licenses in UI

### 5. Deployment & Distribution - ANSWERED ✅
- **Type**: Private extension for Fareportal organization
- **Organization**: "Fareportal"
- **Deployment ID**: Static "15145"

### 6. Existing Script Edge Cases - ANSWERED ✅
- **CSV Files**: Both `iterationlist.csv` and `azuredevpath.csv` should be **configurable** in extension
  - `iterationlist.csv`: Maps dates to iteration paths (sprints)
    - Format: `Iteration Name,Start Date,End Date`
    - Example: `Engineering\\2025-Sprints\\Q1\\Sprint-01 (Jan 06 - Jan 17),1/6/2025,1/17/2025`
    - Currently sorted till 2027, needs to be extensible for future sprints
  - `azuredevpath.csv`: Maps contributor emails to area paths
    - Format: `area_path,email_contributor`
    - Example: `Engineering\\OpsFinTech\\OpsTech\\PostSales,aadeshkumar@fareportal.com`
  - Both should have fallback defaults if CSV unavailable

### 7. Error Handling - ANSWERED ✅
- **Current Plan Approved**: Continue on non-critical errors, log everything, fail only on scan execution errors

## Updated Implementation Details

### CSV Configuration Strategy
- **iterationlist.csv**:
  - Configurable URL input in task.json
  - Download from Azure DevOps repository at runtime
  - Parse to find current sprint based on today's date
  - Fallback: Use default iteration path "Engineering\\2025-Sprints"
  - Future extensibility: CSV can be updated without changing extension code

- **azuredevpath.csv**:
  - Configurable URL input in task.json
  - Download from Azure DevOps repository at runtime
  - Map contributor email to area path
  - Fallback: Use default area path "Engineering\\InfoSec\\DevSecOps\\SAST"

### Summary Display Implementation
- **Pipeline Logs**: Output markdown-formatted summary to console
- **Pipeline Tab**: Use Azure DevOps Test Results API to create a custom tab
  - Format findings as test results
  - Include expandable sections for each finding
  - Show code samples, fix recommendations, and links

### License Whitelist Implementation
- **Default List**: Hardcoded in extension with current APPROVED_LICENSES
- **Override Mechanism**: 
  - UI input field for additional licenses
  - Merge default + user-provided licenses
  - Store as comma/newline-separated list

## Next Steps

1. ✅ **Answers received - proceed with implementation**
2. **Set up development environment**
3. **Create initial project structure**
4. **Implement Phase 1 components**
5. **Iterate based on feedback**

## Dependencies

### Node.js Packages
- `azure-pipelines-task-lib` - Azure DevOps task SDK
- `@types/node` - TypeScript types
- `typescript` - TypeScript compiler

### Python Packages
- `requests` - HTTP client
- `semgrep` - Semgrep CLI (installed via pip)
- `csv` - CSV parsing (built-in)
- `datetime` - Date handling (built-in)

### Azure DevOps APIs
- Work Item Tracking API
- Git API
- Build API

## Success Criteria

1. ✅ Extension installs and runs in Azure DevOps pipeline (Fareportal organization)
2. ✅ Users can configure scan type (PR/Full) via UI
3. ✅ Users can configure ticket creation filters via UI
4. ✅ Tickets are created based on selected filters (SAST, SCA, License)
5. ✅ Summary report shows detailed vulnerability information:
   - In pipeline logs (markdown format)
   - In pipeline run tab (test results format)
6. ✅ Fix PRs can be created (where applicable) using autofix code from API
7. ✅ UI is intuitive and modern (designed based on best practices)
8. ✅ All existing functionality is preserved
9. ✅ CSV files (iterationlist.csv, azuredevpath.csv) are configurable
10. ✅ License whitelist uses global default with override option
11. ✅ Deployment ID "15145" is correctly used for Fareportal