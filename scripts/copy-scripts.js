/**
 * Copy Python scripts to the task directory for packaging
 */
const fs = require('fs');
const path = require('path');

const sourceDir = path.join(__dirname, '..', 'extension', 'scripts');
const targetDir = path.join(__dirname, '..', 'extension', 'tasks', 'semgrepScan', 'scripts');

// Create target directory if it doesn't exist
if (!fs.existsSync(targetDir)) {
    fs.mkdirSync(targetDir, { recursive: true });
}

// Copy all Python scripts
const filesToCopy = [
    'scan_executor.py',
    'ticket_creator.py',
    'summary_generator.py',
    'pr_creator.py',
    'api_utils.py',
    'metrics.py',
    'requirements.txt'
];

filesToCopy.forEach(file => {
    const sourcePath = path.join(sourceDir, file);
    const targetPath = path.join(targetDir, file);
    
    if (fs.existsSync(sourcePath)) {
        fs.copyFileSync(sourcePath, targetPath);
        console.log(`Copied ${file} to task directory`);
    } else {
        console.warn(`Warning: ${file} not found in source directory`);
    }
});

console.log('Scripts copied successfully');
