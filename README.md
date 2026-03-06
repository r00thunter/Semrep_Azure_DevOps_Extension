# Semgrep Azure DevOps Extension

A comprehensive Azure DevOps pipeline extension for Semgrep security scanning with advanced ticket creation, summary reporting, auto-fix PR capabilities, and enterprise-grade error handling.

## 🎯 Features

### Core Functionality
- 🔍 **Flexible Scanning**: Choose between PR Scan (differential) or Full Scan
- 🎫 **Configurable Ticket Creation**: Create Azure DevOps work items for SAST, SCA, and License findings
- 📊 **Comprehensive Summary**: Detailed vulnerability reports with code samples and fix suggestions
- 🔧 **Auto-Fix PRs**: Automatically create pull requests with fixes for identified vulnerabilities

### Advanced Filtering
- **SAST**: Filter by severity (Critical, High, Medium, Low) and confidence (High, Medium, Low)
- **SCA**: Filter by severity and reachability (Always Reachable, Reachable, Direct, Transitive)
- **License**: Global default whitelist with override option for approved licenses
- **Custom Rules**: Include/exclude specific rules via configuration

### Enterprise Features
- ✅ **Advanced Error Recovery**: Automatic retry with exponential backoff, rate limit handling
- ⚡ **Performance Optimizations**: Deployment slug caching, batch API calls
- 📈 **Metrics & Reporting**: Comprehensive metrics collection and reporting
- 🛡️ **Partial Failure Handling**: Continues processing even if some operations fail

## 📦 Installation

### Prerequisites
- Azure DevOps organization (Fareportal)
- Semgrep account with API token
- Python 3.8+ (available on pipeline agents)

### Upload Extension

1. Download the extension package: `semgrep-security-scan-1.0.0.vsix`
2. Go to your Azure DevOps organization: `https://dev.azure.com/`
3. Navigate to: **Organization Settings** → **Extensions** → **Manage Extensions**
4. Click **Upload new extension**
5. Select the `.vsix` file
6. Accept the terms and install

## 🚀 Usage

### Basic Configuration

```yaml
- task: SemgrepSecurityScan@1
  displayName: 'Semgrep Security Scan'
  inputs:
    semgrepAppToken: '$(SEMGREP_APP_TOKEN)'  # Store as secure variable
    scanType: 'PR Scan'                       # or 'Full Scan'
    deploymentId: '12345'                     # Static
```

### Full Configuration Example

```yaml
- task: SemgrepSecurityScan@1
  displayName: 'Semgrep Security Scan'
  inputs:
    # Scan Configuration
    semgrepAppToken: '$(SEMGREP_APP_TOKEN)'
    scanType: 'PR Scan'
    baselineRef: 'origin/master'
    
    # Ticket Creation
    enableTicketCreation: true
    ticketTypes: 'All'  # or 'SAST,SCA,License'
    
    # SAST Filters
    sastSeverities: 'Critical,High'
    sastConfidences: 'High,Medium'
    
    # SCA Filters
    scaSeverities: 'Critical,High'
    scaReachabilities: 'Always Reachable,Reachable,Direct'
    
    # License Configuration
    useDefaultLicenseWhitelist: true
    licenseWhitelistOverride: ''  # Additional licenses if needed
    
    # Summary & PR
    generateSummary: true
    summaryDisplayMode: 'Both'  # 'Logs Only', 'Tab Only', or 'Both'
    createFixPR: false
    fixPRBranchPrefix: 'semgrep-fixes/'
    groupFixPRsByType: true
    
```

## 📋 Input Parameters

### Scan Configuration
| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `semgrepAppToken` | string | ✅ Yes | - | Semgrep API token (store as secure variable) |
| `scanType` | pickList | ✅ Yes | "PR Scan" | "PR Scan" or "Full Scan" |
| `baselineRef` | string | No | "origin/master" | Baseline reference for PR scans |
| `semgrepOrg` | string | No | - | Semgrep organization (optional) |

### Ticket Creation
| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `enableTicketCreation` | boolean | No | true | Enable work item creation |
| `ticketTypes` | multiSelect | No | "All" | SAST, SCA, License, or All |

### SAST Filters
| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `sastSeverities` | multiSelect | No | "Critical,High" | Severity levels to include |
| `sastConfidences` | multiSelect | No | "High,Medium" | Confidence levels to include |

### SCA Filters
| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `scaSeverities` | multiSelect | No | "Critical,High" | Severity levels to include |
| `scaReachabilities` | multiSelect | No | "Always Reachable,Reachable,Direct" | Reachability types to include |

### License Configuration
| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `useDefaultLicenseWhitelist` | boolean | No | true | Use global default whitelist |
| `licenseWhitelistOverride` | multiLine | No | - | Additional licenses (comma/newline separated) |

### Summary & PR
| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `generateSummary` | boolean | No | true | Generate summary report |
| `summaryDisplayMode` | pickList | No | "Both" | "Logs Only", "Tab Only", or "Both" |
| `createFixPR` | boolean | No | false | Create PRs with auto-fixes |
| `fixPRBranchPrefix` | string | No | "semgrep-fixes/" | Branch prefix for fix PRs |
| `groupFixPRsByType` | boolean | No | true | Group fixes by rule type |

### Advanced Configuration
| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `deploymentId` | string | ✅ Yes | "12345" | Semgrep deployment ID (static) |
| `iterationListCsvUrl` | string | No | - | URL to iteration list CSV |
| `azureDevPathCsvUrl` | string | No | - | URL to area path mapping CSV |
| `defaultIterationPath` | string | No | "Engineering\\2025-Sprints" | Fallback iteration path |
| `logLevel` | pickList | No | "INFO" | DEBUG, INFO, WARNING, ERROR |
| `enableMetrics` | boolean | No | true | Enable metrics collection |
| `customRuleFilters` | multiLine | No | - | Custom rule filters (include/exclude) |

## 📊 Outputs

### Summary Report
- **Markdown Format**: Displayed in pipeline logs and saved as artifact
- **Test Results Format**: JSON format saved as artifact (for tab view)
- **Location**: `semgrep-summary/` artifact directory

### Metrics
- **Metrics File**: `semgrep_metrics.json` (saved to working directory)
- **Includes**: Scan stats, ticket creation stats, PR stats, performance metrics

### Work Items
- Created in Azure DevOps with:
  - Links to PR (if applicable)
  - Links to Semgrep findings
  - Code locations
  - Severity and confidence information
  - HTML descriptions with details

### Pull Requests
- Created when `createFixPR=true` and findings have autofix code
- Branch pattern: `{fixPRBranchPrefix}{rule-type}-{timestamp}`
- Includes fix descriptions and links to findings

## 🏗️ Project Structure

```
semgrep_ado_ext/
├── extension/
│   ├── tasks/
│   │   └── semgrepScan/          # Main task
│   │       ├── task.json         # Task definition
│   │       ├── task.ts           # TypeScript implementation
│   │       ├── task.js           # Compiled JavaScript
│   │       └── scripts/          # Python scripts (copied during build)
│   │           ├── scan_executor.py
│   │           ├── ticket_creator.py
│   │           ├── summary_generator.py
│   │           ├── pr_creator.py
│   │           ├── api_utils.py
│   │           ├── metrics.py
│   │           └── requirements.txt
│   ├── scripts/                  # Source Python scripts
│   ├── ui/                      # UI components (future)
│   └── icons/                   # Extension icons
├── scripts/
│   └── copy-scripts.js          # Build script
├── package.json                 # Node.js dependencies
├── tsconfig.json                # TypeScript configuration
├── vss-extension.json           # Extension manifest
└── README.md                    # This file
```

## 🛠️ Development

### Prerequisites
- Node.js 16+ and npm
- Python 3.8+
- TypeScript 5+
- tfx-cli (for packaging)

### Setup

1. **Install dependencies**:
   ```bash
   npm install
   ```

2. **Build the extension**:
   ```bash
   npm run build
   ```
   This compiles TypeScript and copies Python scripts to the task directory.

3. **Package the extension**:
   ```bash
   npm run package
   ```
   This creates the `.vsix` file in the root directory.

### Scripts

- `npm run build` - Compile TypeScript and copy scripts
- `npm run package` - Build and package extension
- `npm run copy-scripts` - Copy Python scripts to task directory

## 🔧 How It Works

### Execution Flow

1. **Scan Execution** (10-30%)
   - Runs Semgrep CLI (full or PR scan)
   - Outputs findings.json
   - Validates scan completion

2. **Ticket Creation** (30-60%) - Optional
   - Fetches findings from Semgrep API
   - Applies filters (severity, confidence, reachability)
   - Creates Azure DevOps work items
   - Links to PRs and Semgrep findings

3. **Summary Generation** (60-85%) - Optional
   - Fetches detailed finding information
   - Generates markdown summary
   - Generates test results format
   - Publishes as artifacts

4. **PR Creation** (85-95%) - Optional
   - Finds findings with autofix code
   - Creates branches and applies fixes
   - Creates pull requests via Azure DevOps API

5. **Completion** (95-100%)
   - Finalizes metrics
   - Reports success/failure

### Error Handling

- **Critical Errors**: Scan failures stop the pipeline
- **Non-Critical Errors**: Ticket/PR/Summary failures log warnings but continue
- **Retry Logic**: Automatic retries with exponential backoff for API calls
- **Rate Limits**: Automatic handling with Retry-After header support
- **Partial Failures**: Continues processing even if some items fail

## 📈 Metrics

The extension collects comprehensive metrics:

- **Scan Metrics**: Findings count, scan duration, scan type
- **Ticket Metrics**: Created/skipped/failed counts per type
- **PR Metrics**: PRs created, findings fixed, branches created
- **Summary Metrics**: Findings included, output formats
- **Performance**: Total duration, per-step durations

Metrics are saved to `semgrep_metrics.json` and can be published as artifacts.

## 🔐 Security

- **Token Storage**: Use Azure DevOps secure variables for `semgrepAppToken`
- **OAuth Token**: Enable "Allow scripts to access OAuth token" for Azure DevOps API access
- **No Hardcoded Secrets**: All sensitive data via environment variables

## 🐛 Troubleshooting

### Common Issues

1. **Python not found**
   - Ensure Python 3.8+ is available on the agent
   - Add Python installation step if needed

2. **API Authentication Failed**
   - Verify `SEMGREP_APP_TOKEN` is correct
   - Check token has necessary permissions

3. **Ticket Creation Fails**
   - Verify `SYSTEM_ACCESSTOKEN` is available
   - Enable "Allow scripts to access OAuth token" in pipeline options

4. **Rate Limit Errors**
   - Extension automatically retries with backoff
   - Check logs for retry attempts

5. **CSV Files Not Found**
   - Extension uses fallback defaults
   - Verify CSV URLs are accessible

## 📚 Documentation

Additional documentation available in the `docs/` directory:

- **Implementation Details**: See `docs/` folder for detailed documentation
- **Configuration Examples**: See usage examples above
- **API Reference**: Semgrep API documentation at https://semgrep.dev/api

## 🎯 Use Cases

### PR Security Review
```yaml
- task: SemgrepSecurityScan@1
  inputs:
    scanType: 'PR Scan'
    enableTicketCreation: true
    ticketTypes: 'SAST,SCA'
    sastSeverities: 'Critical,High'
    generateSummary: true
    createFixPR: true
```

### Full Repository Scan
```yaml
- task: SemgrepSecurityScan@1
  inputs:
    scanType: 'Full Scan'
    enableTicketCreation: true
    ticketTypes: 'All'
    generateSummary: true
```

### License Compliance Check
```yaml
- task: SemgrepSecurityScan@1
  inputs:
    scanType: 'Full Scan'
    enableTicketCreation: true
    ticketTypes: 'License'
    useDefaultLicenseWhitelist: true
```

## ✅ Status

**Production Ready** - All core features and enhancements implemented and tested.

- ✅ Scan execution (Full & PR)
- ✅ Ticket creation (SAST, SCA, License)
- ✅ Summary generation
- ✅ Auto-fix PR creation
- ✅ Advanced error recovery
- ✅ Performance optimizations
- ✅ Metrics and reporting

## 📄 License

MIT License - See [LICENSE](./LICENSE) file for details.

## 👥 Support

For issues, questions, or contributions:
- Check the documentation in the `docs/` directory
- Review pipeline logs for detailed error messages
- Contact the development team

## 🔄 Version History

- **1.0.0** (Current)
  - Initial release
  - All core features implemented
  - Advanced error recovery and performance optimizations
  - Metrics and reporting

---

## 👤 Author

**Yash Mishra** (AKA Lucifer)

---

**Built for Fareportal** | **Powered by Semgrep**
