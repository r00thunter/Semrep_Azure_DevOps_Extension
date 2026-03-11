/**
 * Copy task folder to root level for Azure DevOps extension packaging
 * Azure DevOps expects task folders at the root level, not nested
 */
const fs = require('fs');
const path = require('path');

const sourceTaskDir = path.join(__dirname, '..', 'extension', 'tasks', 'semgrepScan');
const targetTaskDir = path.join(__dirname, '..', 'semgrepScan');

// Remove existing target directory if it exists
if (fs.existsSync(targetTaskDir)) {
    fs.rmSync(targetTaskDir, { recursive: true, force: true });
    console.log('Removed existing task directory at root level');
}

// Create target directory
const targetParentDir = path.dirname(targetTaskDir);
if (!fs.existsSync(targetParentDir)) {
    fs.mkdirSync(targetParentDir, { recursive: true });
}

// Copy entire task directory
console.log('Copying task folder to root level...');
console.log(`  From: ${sourceTaskDir}`);
console.log(`  To: ${targetTaskDir}`);

function copyRecursiveSync(src, dest) {
    const exists = fs.existsSync(src);
    const stats = exists && fs.statSync(src);
    const isDirectory = exists && stats.isDirectory();
    
    if (isDirectory) {
        if (!fs.existsSync(dest)) {
            fs.mkdirSync(dest, { recursive: true });
        }
        fs.readdirSync(src).forEach(childItemName => {
            copyRecursiveSync(
                path.join(src, childItemName),
                path.join(dest, childItemName)
            );
        });
    } else {
        fs.copyFileSync(src, dest);
    }
}

try {
    copyRecursiveSync(sourceTaskDir, targetTaskDir);
    console.log('✓ Task folder copied successfully to root level');
} catch (error) {
    console.error('Error copying task folder:', error.message);
    process.exit(1);
}
