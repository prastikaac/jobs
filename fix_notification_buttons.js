const fs = require('fs');
const path = require('path');

function processDirectory(dir) {
    const files = fs.readdirSync(dir);
    for (const file of files) {
        const fullPath = path.join(dir, file);
        const stat = fs.statSync(fullPath);

        if (stat.isDirectory()) {
            // skip node_modules or .git if they exist
            if (file === 'node_modules' || file === '.git') continue;
            processDirectory(fullPath);
        } else if (fullPath.endsWith('.html')) {
            const content = fs.readFileSync(fullPath, 'utf8');
            let newContent = content;

            // Replace back button
            newContent = newContent.replace(
                /<button\s+aria-label="Back to notifications"\s+id="nd-back-btn">.*?<\/button>/g,
                '<button aria-label="Back to notifications" id="nd-back-btn">&larr;</button>'
            );

            // Replace close button
            newContent = newContent.replace(
                /<button\s+aria-label="Close"\s+id="nd-close-btn">.*?<\/button>/g,
                '<button aria-label="Close" id="nd-close-btn">&times;</button>'
            );

            if (content !== newContent) {
                fs.writeFileSync(fullPath, newContent, 'utf8');
                console.log(`Updated: ${fullPath}`);
            }
        }
    }
}

const targetDir = process.cwd();
console.log(`Starting in ${targetDir}`);
processDirectory(targetDir);
console.log('Done.');
