/**
 * Zip the task directory for Azure DevOps extension packaging
 */
const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

const taskDir = path.join(__dirname, '..', 'extension', 'tasks', 'semgrepScan');
const zipFile = path.join(__dirname, '..', 'extension', 'tasks', 'semgrepScan.zip');

// Remove existing zip if it exists
if (fs.existsSync(zipFile)) {
    fs.unlinkSync(zipFile);
    console.log('Removed existing zip file');
}

// Check if task directory exists
if (!fs.existsSync(taskDir)) {
    console.error(`Error: Task directory not found at ${taskDir}`);
    process.exit(1);
}

// Check if task.json exists
const taskJsonPath = path.join(taskDir, 'task.json');
if (!fs.existsSync(taskJsonPath)) {
    console.error(`Error: task.json not found at ${taskJsonPath}`);
    process.exit(1);
}

console.log('Zipping task directory...');

try {
    // Use PowerShell Compress-Archive on Windows
    // Zip all contents of the task directory (not the directory itself)
    // Azure DevOps expects files at the root of the zip
    const taskDirParent = path.dirname(taskDir);
    const zipFileName = 'semgrepScan.zip';
    const zipPath = path.join(taskDirParent, zipFileName);
    
    // Change to task directory and zip all contents
    // This ensures files are at the root of the zip, not in a subdirectory
    const command = `cd "${taskDir}" && powershell -Command "Get-ChildItem -Recurse | Compress-Archive -DestinationPath '${zipPath.replace(/\\/g, '/')}' -Force"`;
    
    execSync(command, { 
        stdio: 'inherit',
        shell: true
    });
    
    console.log(`✓ Task directory zipped successfully: ${zipPath}`);
} catch (error) {
    console.error('Error zipping task directory:', error.message);
    process.exit(1);
}
