# Clarification Questions for Semgrep Azure DevOps Extension

## Critical Questions (Need answers to proceed)

### 1. Semgrep API Details
**Question:** What Semgrep API endpoints are available for:
- Getting detailed finding information (code samples, fix suggestions, full descriptions)?
- Autofix functionality - is there an API endpoint or should we use CLI with autofix flags?
- Deployment ID - I see "15145" hardcoded in your license script. Should this be:
  - Fetched dynamically from the deployment API?
  - Made configurable in the extension?
  - Always the same for your organization?

**Current Usage:**
- `GET /api/v1/deployments` - Gets deployment slug
- `GET /api/v1/deployments/{slug}/findings` - Gets SAST findings
- `GET /api/sca/deployments/{id}/dependencies` - Gets SCA findings
- SBOM export endpoints

**What I need:**
- API endpoint for getting individual finding details (code samples, fix suggestions)
- Confirmation on autofix approach

---

### 2. UI/UX Preferences
**Question:** 
- Do you have screenshots or examples of the Snyk extension UI you want to replicate?
- Should the summary be displayed:
  - Only in pipeline logs?
  - As a separate tab in the pipeline run (like test results)?
  - Both?

**Current Plan:**
- Task input UI similar to Snyk (collapsible sections, modern styling)
- Summary in pipeline logs + optional markdown file artifact

---

### 3. PR Auto-Fix Behavior
**Question:**
- Should auto-fix PRs be:
  - Created immediately when fixes are available?
  - Queued for manual approval first?
- Branch naming: What pattern do you prefer? (e.g., `semgrep-fixes/rule-name-123`)
- Should we:
  - Create one PR per finding?
  - Group multiple fixes into one PR?
  - Group by rule type?

**Current Plan:**
- One PR per rule type (SAST fixes, SCA fixes, etc.)
- Branch prefix: `semgrep-fixes/`

---

### 4. License Whitelist Configuration
**Question:**
- Should the license whitelist be:
  - Configurable per pipeline (user enters in UI)?
  - Global default with override option?
  - Both (default list + user can add more)?

**Current Plan:**
- Pre-populate with your current APPROVED_LICENSES list
- Allow users to add additional licenses in UI
- Store as multi-line input field

---

### 5. Deployment & Distribution
**Question:**
- Will this extension be:
  - Private (only for your organization)?
  - Published to Azure DevOps Marketplace?
- If private, what's your organization name for testing?

**Current Plan:**
- Support both private and marketplace distribution
- Include packaging scripts

---

### 6. Existing Script Edge Cases
**Question:**
- Are there any special cases or business logic in your current scripts that must be preserved?
- The `iterationlist.csv` and `azuredevpath.csv` files - should these:
  - Remain as external dependencies?
  - Be configurable in the extension?
  - Have fallback defaults?

**Current Usage:**
- `iterationlist.csv` - Maps dates to iteration paths
- `azuredevpath.csv` - Maps contributor emails to area paths

---

### 7. Error Handling & Logging
**Question:**
- What level of logging do you need?
- Should the extension:
  - Fail the pipeline on critical errors?
  - Continue with warnings for non-critical issues?
  - Always complete scan even if ticket creation fails?

**Current Plan:**
- Continue on non-critical errors
- Log everything with configurable log level
- Fail only on scan execution errors

---

## Nice-to-Have Questions (Can be added later)

### 8. Notifications
- Should the extension send notifications when tickets are created?
- Email notifications? Slack? Teams?

### 9. Metrics & Reporting
- Should we track metrics (findings count, tickets created, etc.)?
- Export to external systems?

### 10. Advanced Filtering
- Should we support custom filters beyond severity/confidence/reachability?
- Rule-based filtering (include/exclude specific rules)?

---

## Priority Order

**Must Answer Before Starting:**
1. Semgrep API details (especially finding details and autofix)
2. Deployment ID handling
3. UI/UX preferences

**Can Answer During Development:**
4. PR auto-fix behavior
5. License whitelist configuration
6. Error handling preferences

**Can Add Later:**
7. Notifications
8. Metrics
9. Advanced filtering

---

## Assumptions (Please Confirm)

1. ✅ Extension will run on Linux agents (based on `/home/vsts/work/` paths)
2. ✅ Python 3.x will be available on agents
3. ✅ Git will be available for PR creation
4. ✅ SYSTEM_ACCESSTOKEN will be available for Azure DevOps API calls
5. ✅ SEMGREP_APP_TOKEN will be provided as secure input
6. ✅ Extension supports both YAML and Classic pipelines
