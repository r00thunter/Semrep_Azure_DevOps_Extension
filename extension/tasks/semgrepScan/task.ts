import * as tl from 'azure-pipelines-task-lib/task';
import * as path from 'path';
import * as fs from 'fs';

async function run() {
    try {
        // Get input parameters
        // Auto-fetch from variable library 'Semgrep_Variables' if not provided
        const semgrepAppTokenInput = tl.getInput('semgrepAppToken', false);
        const semgrepAppToken: string = semgrepAppTokenInput || process.env.SEMGREP_APP_TOKEN || '';
        if (!semgrepAppToken) {
            throw new Error('Semgrep App Token is required. Please provide it as input or in variable library "Semgrep_Variables" as SEMGREP_APP_TOKEN.');
        }
        const scanType: string = tl.getInput('scanType', true)!;
        // Use SEMGREP_BRANCH from variable library if baselineRef not provided
        const baselineRefInput = tl.getInput('baselineRef', false);
        const baselineRef: string = baselineRefInput || process.env.SEMGREP_BRANCH || process.env.BUILD_SOURCEBRANCHNAME || 'origin/master';
        const semgrepOrg: string = tl.getInput('semgrepOrg', false) || process.env.SEMGREP_ORG || '';
        
        // Ticket creation parameters
        const enableTicketCreation: boolean = tl.getBoolInput('enableTicketCreation', false) || false;
        const ticketTypes: string = tl.getInput('ticketTypes', false) || 'All';
        
        // SAST filters
        const sastSeverities: string[] = tl.getDelimitedInput('sastSeverities', ',', false) || [];
        const sastConfidences: string[] = tl.getDelimitedInput('sastConfidences', ',', false) || [];
        
        // SCA filters
        const scaSeverities: string[] = tl.getDelimitedInput('scaSeverities', ',', false) || [];
        const scaReachabilities: string[] = tl.getDelimitedInput('scaReachabilities', ',', false) || [];
        
        // License configuration
        const useDefaultLicenseWhitelist: boolean = tl.getBoolInput('useDefaultLicenseWhitelist', false) !== false;
        const licenseWhitelistOverride: string = tl.getInput('licenseWhitelistOverride', false) || '';
        
        // Summary & PR
        const generateSummary: boolean = tl.getBoolInput('generateSummary', false) !== false;
        const summaryDisplayMode: string = tl.getInput('summaryDisplayMode', false) || 'Both';
        const createFixPR: boolean = tl.getBoolInput('createFixPR', false) || false;
        const fixPRBranchPrefix: string = tl.getInput('fixPRBranchPrefix', false) || 'semgrep-fixes/';
        const groupFixPRsByType: boolean = tl.getBoolInput('groupFixPRsByType', false) !== false;
        
        // Advanced configuration
        const deploymentId: string = tl.getInput('deploymentId', true)!;
        const iterationListCsvUrl: string = tl.getInput('iterationListCsvUrl', false) || '';
        const azureDevPathCsvUrl: string = tl.getInput('azureDevPathCsvUrl', false) || '';
        const defaultIterationPath: string = tl.getInput('defaultIterationPath', false) || 'Engineering\\2025-Sprints';
        const logLevel: string = tl.getInput('logLevel', false) || 'INFO';
        
        // Set log level
        process.env.LOG_LEVEL = logLevel;
        
        // Set Semgrep token
        process.env.SEMGREP_APP_TOKEN = semgrepAppToken;
        
        // Get Azure DevOps environment variables
        // Prefer variables from 'Semgrep_Variables' library if available
        const buildRepoName = process.env.SEMGREP_REPO_NAME || process.env.BUILD_REPOSITORY_NAME || '';
        const systemCollectionUri = process.env.SYSTEM_COLLECTIONURI || '';
        const systemTeamProjectId = process.env.SYSTEM_TEAMPROJECTID || '';
        const buildRepositoryId = process.env.BUILD_REPOSITORY_ID || '';
        const buildRepositoryUri = process.env.SEMGREP_REPO_URL || process.env.BUILD_REPOSITORY_URI || '';
        const buildRequestedForEmail = process.env.BUILD_REQUESTEDFOREMAIL || '';
        const pipelineStartTime = process.env.SYSTEM_PIPELINESTARTTIME || '';
        const pullRequestId = process.env.SYSTEM_PULLREQUEST_PULLREQUESTID || '0';
        const sourceBranchName = process.env.SEMGREP_BRANCH || process.env.BUILD_SOURCEBRANCHNAME || '';
        // SYSTEM_ACCESSTOKEN from variable library takes precedence
        const systemAccessToken = process.env.SYSTEM_ACCESSTOKEN || '';
        // SEMGREP_WEBAPP_TOKEN from variable library (if needed)
        const semgrepWebappToken = process.env.SEMGREP_WEBAPP_TOKEN || '';
        
        // Set environment variables for Python scripts
        process.env.BUILD_REPOSITORY_NAME = buildRepoName;
        process.env.SYSTEM_COLLECTIONURI = systemCollectionUri;
        process.env.SYSTEM_TEAMPROJECTID = systemTeamProjectId;
        process.env.BUILD_REPOSITORY_ID = buildRepositoryId;
        process.env.BUILD_REPOSITORY_URI = buildRepositoryUri;
        process.env.BUILD_REQUESTEDFOREMAIL = buildRequestedForEmail;
        process.env.SYSTEM_PIPELINESTARTTIME = pipelineStartTime;
        process.env.SYSTEM_PULLREQUEST_PULLREQUESTID = pullRequestId;
        process.env.BUILD_SOURCEBRANCHNAME = sourceBranchName;
        process.env.SYSTEM_ACCESSTOKEN = systemAccessToken;
        if (semgrepWebappToken) {
            process.env.SEMGREP_WEBAPP_TOKEN = semgrepWebappToken;
        }
        process.env.DEPLOYMENT_ID = deploymentId;
        process.env.SCAN_TYPE = scanType;
        process.env.BASELINE_REF = baselineRef;
        if (semgrepOrg) {
            process.env.SEMGREP_ORG = semgrepOrg;
        }
        
        // Set ticket creation parameters
        process.env.ENABLE_TICKET_CREATION = enableTicketCreation.toString();
        process.env.TICKET_TYPES = ticketTypes;
        process.env.SAST_SEVERITIES = sastSeverities.join(',');
        process.env.SAST_CONFIDENCES = sastConfidences.join(',');
        process.env.SCA_SEVERITIES = scaSeverities.join(',');
        process.env.SCA_REACHABILITIES = scaReachabilities.join(',');
        process.env.USE_DEFAULT_LICENSE_WHITELIST = useDefaultLicenseWhitelist.toString();
        process.env.LICENSE_WHITELIST_OVERRIDE = licenseWhitelistOverride;
        
        // Set summary & PR parameters
        process.env.GENERATE_SUMMARY = generateSummary.toString();
        process.env.SUMMARY_DISPLAY_MODE = summaryDisplayMode;
        process.env.CREATE_FIX_PR = createFixPR.toString();
        process.env.FIX_PR_BRANCH_PREFIX = fixPRBranchPrefix;
        process.env.GROUP_FIX_PRS_BY_TYPE = groupFixPRsByType.toString();
        
        // Set CSV URLs
        process.env.ITERATION_LIST_CSV_URL = iterationListCsvUrl;
        process.env.AZURE_DEV_PATH_CSV_URL = azureDevPathCsvUrl;
        process.env.DEFAULT_ITERATION_PATH = defaultIterationPath;
        
        // Get task directory and scripts path
        // In Azure DevOps tasks, the task directory is where task.js is located
        // Use process.cwd() as fallback, but typically __dirname works in Node.js
        let taskDir: string;
        try {
            // @ts-ignore - __dirname is available at runtime in Node.js
            taskDir = typeof __dirname !== 'undefined' ? __dirname : path.dirname(process.argv[1]);
        } catch {
            // Fallback to current working directory
            taskDir = process.cwd();
        }
        const scriptsDir = path.join(taskDir, 'scripts');
        const scanExecutorPath = path.join(scriptsDir, 'scan_executor.py');
        const ticketCreatorPath = path.join(scriptsDir, 'ticket_creator.py');
        const summaryGeneratorPath = path.join(scriptsDir, 'summary_generator.py');
        const prCreatorPath = path.join(scriptsDir, 'pr_creator.py');
        
        // Log script paths for debugging
        tl.debug(`Task directory: ${taskDir}`);
        tl.debug(`Scripts directory: ${scriptsDir}`);
        tl.debug(`Scan executor path: ${scanExecutorPath}`);
        tl.debug(`Ticket creator path: ${ticketCreatorPath}`);
        tl.debug(`Summary generator path: ${summaryGeneratorPath}`);
        
        // Verify Python is available
        const python3 = tl.which('python3', false);
        const pythonCmd = python3 || tl.which('python', true);
        if (!pythonCmd) {
            throw new Error('Python 3 is required but not found. Please install Python 3.');
        }
        
        const sourcesDir = tl.getVariable('Build.SourcesDirectory') || process.cwd();
        const agentWorkFolder = tl.getVariable('Agent.WorkFolder') || '';
        const artifactStagingDir = tl.getVariable('Build.ArtifactStagingDirectory') || sourcesDir;

        // Log configuration
        tl.debug(`Using python: ${pythonCmd}`);
        tl.debug(`Sources directory: ${sourcesDir}`);
        tl.debug(`Agent work folder: ${agentWorkFolder}`);
        tl.debug(`Artifact staging directory: ${artifactStagingDir}`);
        tl.debug(`Scan type: ${scanType}`);
        tl.debug(`Deployment ID: ${deploymentId}`);
        tl.debug(`Ticket creation: ${enableTicketCreation ? 'enabled' : 'disabled'}`);
        tl.debug(`Summary generation: ${generateSummary ? 'enabled' : 'disabled'}`);

        // Validate required environment variables
        if (!systemAccessToken && enableTicketCreation) {
            tl.warning('SYSTEM_ACCESSTOKEN not found. Ticket creation may fail. Enable "Allow scripts to access OAuth token" in pipeline options.');
        }

        // Step 1: Execute scan
        tl.setProgress(10, 'Starting Semgrep scan...');
        if (!tl.exist(scanExecutorPath)) {
            throw new Error(`scan_executor.py not found at ${scanExecutorPath}. Ensure the extension is properly packaged.`);
        }
        
        tl.debug(`Running scan executor: ${scanExecutorPath}`);
        try {
            const scanResult = await tl.tool(pythonCmd)
                .arg(scanExecutorPath)
                .exec({ 
                    cwd: sourcesDir,
                    failOnStdErr: false,
                    ignoreReturnCode: false
                });
            
            tl.setProgress(30, 'Semgrep scan completed successfully');
            console.log('✅ Semgrep scan completed successfully');
            
            // Verify scan output file exists (optional check)
            const findingsPath = path.join(sourcesDir, 'findings.json');
            const agentFindingsPath = agentWorkFolder ? 
                path.join(agentWorkFolder, '1', 'a', 'findings.json') : null;
            
            const actualFindingsPath = fs.existsSync(findingsPath) ? findingsPath :
                (agentFindingsPath && fs.existsSync(agentFindingsPath) ? agentFindingsPath : null);
            
            if (actualFindingsPath) {
                tl.debug(`Findings file found at: ${actualFindingsPath}`);
                try {
                    const findingsData = JSON.parse(fs.readFileSync(actualFindingsPath, 'utf-8'));
                    const findingsCount = findingsData?.results?.length || 0;
                    console.log(`📊 Scan found ${findingsCount} potential issues`);
                } catch (parseError) {
                    tl.debug(`Could not parse findings.json: ${parseError}`);
                }
            } else {
                tl.debug('Findings.json not found in expected locations (this may be normal for some scan types)');
            }
            
        } catch (error: any) {
            const errorMsg = `Semgrep scan failed: ${error.message || error}`;
            tl.error(errorMsg);
            throw new Error(errorMsg);
        }

        // Step 2: Create tickets (optional)
        if (enableTicketCreation) {
            tl.setProgress(40, 'Creating work items for findings...');
            
            if (!tl.exist(ticketCreatorPath)) {
                tl.warning(`ticket_creator.py not found at ${ticketCreatorPath}. Skipping ticket creation.`);
            } else {
                tl.debug(`Running ticket creator: ${ticketCreatorPath}`);
                try {
                    await tl.tool(pythonCmd)
                        .arg(ticketCreatorPath)
                        .exec({ 
                            cwd: sourcesDir,
                            failOnStdErr: false,
                            ignoreReturnCode: false
                        });
                    
                    tl.setProgress(60, 'Ticket creation completed');
                    console.log('✅ Work items created successfully');
                    
                } catch (error: any) {
                    // Ticket creation failures are non-critical - log but continue
                    const errorMsg = `Ticket creation failed: ${error.message || error}`;
                    tl.warning(errorMsg);
                    console.log(`⚠️  Warning: ${errorMsg}`);
                    // Continue execution even if ticket creation fails
                }
            }
        } else {
            tl.debug('Ticket creation disabled, skipping ticket_creator.py');
        }

        // Step 3: Generate summary (optional)
        if (generateSummary) {
            tl.setProgress(70, 'Generating summary report...');
            
            if (!tl.exist(summaryGeneratorPath)) {
                tl.warning(`summary_generator.py not found at ${summaryGeneratorPath}. Skipping summary generation.`);
            } else {
                tl.debug(`Running summary generator: ${summaryGeneratorPath}`);
                try {
                    await tl.tool(pythonCmd)
                        .arg(summaryGeneratorPath)
                        .exec({ 
                            cwd: sourcesDir,
                            failOnStdErr: false,
                            ignoreReturnCode: false
                        });
                    
                    tl.setProgress(85, 'Summary generation completed');
                    
                    // Read and display markdown summary if available
                    const summaryMarkdownPath = path.join(sourcesDir, 'semgrep_summary.md');
                    if (fs.existsSync(summaryMarkdownPath)) {
                        const summaryContent = fs.readFileSync(summaryMarkdownPath, 'utf-8');
                        
                        // Display in logs if configured
                        if (summaryDisplayMode === 'Logs Only' || summaryDisplayMode === 'Both') {
                            console.log('\n' + '='.repeat(80));
                            console.log('SEMGREP SECURITY SCAN SUMMARY');
                            console.log('='.repeat(80) + '\n');
                            console.log(summaryContent);
                            console.log('\n' + '='.repeat(80) + '\n');
                        }
                        
                        // Publish as artifact
                        try {
                            const artifactPath = path.join(artifactStagingDir, 'semgrep-summary');
                            if (!fs.existsSync(artifactPath)) {
                                fs.mkdirSync(artifactPath, { recursive: true });
                            }
                            fs.copyFileSync(summaryMarkdownPath, path.join(artifactPath, 'summary.md'));
                            tl.debug('Summary markdown published as artifact');
                            console.log('📄 Summary report saved as build artifact');
                        } catch (artifactError: any) {
                            tl.warning(`Failed to publish summary artifact: ${artifactError.message}`);
                        }
                    }
                    
                    // Handle test results format
                    const testResultsPath = path.join(sourcesDir, 'semgrep_test_results.json');
                    if (fs.existsSync(testResultsPath) && summaryDisplayMode !== 'Logs Only') {
                        try {
                            const artifactPath = path.join(artifactStagingDir, 'semgrep-summary');
                            if (!fs.existsSync(artifactPath)) {
                                fs.mkdirSync(artifactPath, { recursive: true });
                            }
                            fs.copyFileSync(testResultsPath, path.join(artifactPath, 'test_results.json'));
                            tl.debug('Test results JSON published as artifact');
                            console.log('📊 Test results format saved as build artifact');
                        } catch (artifactError: any) {
                            tl.warning(`Failed to publish test results artifact: ${artifactError.message}`);
                        }
                    }
                    
                    console.log('✅ Summary report generated successfully');
                    
                } catch (error: any) {
                    // Summary generation failures are non-critical - log but continue
                    const errorMsg = `Summary generation failed: ${error.message || error}`;
                    tl.warning(errorMsg);
                    console.log(`⚠️  Warning: ${errorMsg}`);
                    // Continue execution even if summary generation fails
                }
            }
        } else {
            tl.debug('Summary generation disabled, skipping summary_generator.py');
        }

        // Step 4: Create fix PRs (optional)
        if (createFixPR) {
            tl.setProgress(90, 'Creating fix pull requests...');
            
            if (!tl.exist(prCreatorPath)) {
                tl.warning(`pr_creator.py not found at ${prCreatorPath}. Skipping PR creation.`);
            } else {
                tl.debug(`Running PR creator: ${prCreatorPath}`);
                try {
                    await tl.tool(pythonCmd)
                        .arg(prCreatorPath)
                        .exec({ 
                            cwd: sourcesDir,
                            failOnStdErr: false,
                            ignoreReturnCode: false
                        });
                    
                    tl.setProgress(95, 'PR creation completed');
                    console.log('✅ Fix PRs created successfully (if any findings had autofix code)');
                    
                } catch (error: any) {
                    // PR creation failures are non-critical - log but continue
                    const errorMsg = `PR creation failed: ${error.message || error}`;
                    tl.warning(errorMsg);
                    console.log(`⚠️  Warning: ${errorMsg}`);
                    // Continue execution even if PR creation fails
                }
            }
        } else {
            tl.debug('PR creation disabled, skipping pr_creator.py');
        }

        tl.setProgress(100, 'Task completed successfully');
        tl.setResult(tl.TaskResult.Succeeded, 'Semgrep scan task completed successfully');
        
    } catch (err: any) {
        const errorMessage = err?.message || String(err) || 'Unknown error occurred';
        tl.error(`Task failed: ${errorMessage}`);
        tl.setResult(tl.TaskResult.Failed, errorMessage);
        
        // Log stack trace in debug mode
        if (err?.stack) {
            tl.debug(`Stack trace: ${err.stack}`);
        }
    }
}

run();
