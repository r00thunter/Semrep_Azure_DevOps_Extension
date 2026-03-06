# Getting Started - Semgrep Azure DevOps Extension

## Prerequisites

1. **Node.js** 16+ and npm
2. **Python** 3.8+ (will be used by the extension at runtime)
3. **Azure DevOps** organization (Fareportal)
4. **Semgrep** account with API token

## Installation & Setup

### 1. Install Dependencies

```bash
npm install
```

This will install:
- TypeScript compiler
- Azure Pipelines Task Lib
- tfx-cli (for packaging)

### 2. Build the Extension

```bash
npm run build
```

This will:
- Compile TypeScript to JavaScript
- Copy Python scripts to the task directory

### 3. Package the Extension

```bash
npm run package
```

This creates a `.vsix` file that can be uploaded to Azure DevOps.

## Development Workflow

### Making Changes

1. **TypeScript Changes** (`extension/tasks/semgrepScan/task.ts`):
   - Edit the TypeScript file
   - Run `npm run build` to compile
   - Test locally (if possible)

2. **Python Script Changes** (`extension/scripts/*.py`):
   - Edit Python scripts
   - Run `npm run build` to copy to task directory
   - Test the scripts independently

3. **Task Definition Changes** (`extension/tasks/semgrepScan/task.json`):
   - Edit task.json
   - No build needed, but repackage extension

### Testing

1. **Package Extension**:
   ```bash
   npm run package
   ```

2. **Upload to Azure DevOps**:
   - Go to your Azure DevOps organization
   - Navigate to Extensions → Manage Extensions
   - Upload the `.vsix` file

3. **Test in Pipeline**:
   - Add the task to a pipeline
   - Configure inputs
   - Run the pipeline

## Project Structure

```
semgrep_ado_ext/
├── extension/
│   ├── tasks/
│   │   └── semgrepScan/
│   │       ├── task.json          # Task definition
│   │       ├── task.ts            # TypeScript implementation
│   │       ├── task.js            # Compiled JavaScript (generated)
│   │       └── scripts/           # Python scripts (copied during build)
│   │           ├── scan_executor.py
│   │           └── requirements.txt
│   ├── scripts/                   # Source Python scripts
│   ├── ui/                        # UI components (to be implemented)
│   └── icons/                     # Extension icons
├── scripts/
│   └── copy-scripts.js            # Build script to copy Python files
├── package.json                   # Node.js dependencies
├── tsconfig.json                  # TypeScript configuration
├── vss-extension.json             # Extension manifest
└── README.md                      # Documentation
```

## Configuration

### Required Inputs

- `semgrepAppToken`: Your Semgrep API token (store as secure variable)
- `deploymentId`: Static value "15145" for Fareportal

### Optional Inputs

All other inputs have defaults and can be configured per pipeline.

## Next Steps

1. **Complete Python Scripts**:
   - Implement `ticket_creator.py`
   - Implement `summary_generator.py`
   - Implement `pr_creator.py`

2. **Test Extension**:
   - Package and upload to Azure DevOps
   - Test in a sample pipeline
   - Verify scan execution works

3. **Iterate**:
   - Add ticket creation
   - Add summary generation
   - Add PR creation

## Troubleshooting

### TypeScript Compilation Errors

If you see TypeScript errors:
1. Ensure `npm install` has been run
2. Check that `@types/node` is installed
3. Verify `tsconfig.json` is correct

### Python Script Errors

If Python scripts fail:
1. Ensure Python 3.8+ is available on the agent
2. Check that `semgrep` CLI can be installed
3. Verify environment variables are set correctly

### Extension Packaging Errors

If packaging fails:
1. Ensure `tfx-cli` is installed: `npm install -g tfx-cli`
2. Check that all required files exist
3. Verify `vss-extension.json` is valid JSON

## Support

For issues or questions, refer to:
- `IMPLEMENTATION_PLAN.md` - Detailed implementation plan
- `ANSWERS_SUMMARY.md` - Answers to clarification questions
- `BUILD_STATUS.md` - Current build status
