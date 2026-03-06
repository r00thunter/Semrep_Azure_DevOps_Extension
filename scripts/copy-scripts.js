/**
 * Copy Python scripts and UI files to the task directory for packaging
 */
const fs = require('fs');
const path = require('path');

const sourceScriptsDir = path.join(__dirname, '..', 'extension', 'scripts');
const targetScriptsDir = path.join(__dirname, '..', 'extension', 'tasks', 'semgrepScan', 'scripts');

const sourceUIDir = path.join(__dirname, '..', 'extension', 'tasks', 'semgrepScan', 'ui');
const targetUIDir = path.join(__dirname, '..', 'extension', 'tasks', 'semgrepScan', 'ui');

// Create target directories if they don't exist
if (!fs.existsSync(targetScriptsDir)) {
    fs.mkdirSync(targetScriptsDir, { recursive: true });
}

if (!fs.existsSync(targetUIDir)) {
    fs.mkdirSync(targetUIDir, { recursive: true });
}

// Copy all Python scripts
const scriptsToCopy = [
    'scan_executor.py',
    'ticket_creator.py',
    'summary_generator.py',
    'pr_creator.py',
    'api_utils.py',
    'metrics.py',
    'requirements.txt'
];

console.log('Copying Python scripts...');
scriptsToCopy.forEach(file => {
    const sourcePath = path.join(sourceScriptsDir, file);
    const targetPath = path.join(targetScriptsDir, file);
    
    if (fs.existsSync(sourcePath)) {
        fs.copyFileSync(sourcePath, targetPath);
        console.log(`  ✓ Copied ${file}`);
    } else {
        console.warn(`  ⚠ Warning: ${file} not found in source directory`);
    }
});

// Verify UI files exist
console.log('\nVerifying UI files...');
const uiFiles = [
    'task-inputs.html',
    'task-inputs.css',
    'task-inputs.js'
];

let allUIFilesExist = true;
uiFiles.forEach(file => {
    const filePath = path.join(sourceUIDir, file);
    if (fs.existsSync(filePath)) {
        console.log(`  ✓ Found ${file}`);
    } else {
        console.warn(`  ⚠ Warning: ${file} not found`);
        allUIFilesExist = false;
    }
});

if (allUIFilesExist) {
    console.log('\n✓ All files copied/verified successfully');
} else {
    console.log('\n⚠ Some UI files are missing');
}
