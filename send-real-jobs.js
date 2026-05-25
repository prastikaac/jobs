const admin = require('firebase-admin');
const path = require('path');
const fs = require('fs');

const serviceAccountPath = process.env.FIREBASE_SERVICE_ACCOUNT_PATH || './serviceAccountKey.json';

if (!fs.existsSync(serviceAccountPath)) {
    const altPath = './scraper/serviceAccountKey.json';
    if (fs.existsSync(altPath)) {
        process.env.FIREBASE_SERVICE_ACCOUNT_PATH = altPath;
    } else {
        console.error('Service account file not found');
        process.exit(1);
    }
}

const serviceAccount = require(path.resolve(process.env.FIREBASE_SERVICE_ACCOUNT_PATH || serviceAccountPath));

admin.initializeApp({
    credential: admin.credential.cert(serviceAccount),
});

const db = admin.firestore();

async function sendJobsToFirebase() {
    try {
        console.log('Reading jobs from scraper/data/ai_proccessed_jobs.json...');
        const jobsData = JSON.parse(fs.readFileSync('c:/Users/Ac/Documents/Programming/HTML CSS JS/JobsInFinland/scraper/data/ai_proccessed_jobs.json', 'utf8'));
        
        const jobs = Array.isArray(jobsData) ? jobsData : Object.values(jobsData);
        const sampleJobs = jobs.slice(0, 10);
        
        console.log(Starting to send \ jobs to Firebase Firestore...);

        let successCount = 0;
        let errorCount = 0;

        for (let i = 0; i < sampleJobs.length; i++) {
            const job = sampleJobs[i];
            const jobId = job.id || \	est-job-\-\\;
            
            if (!job.expiresAt) {
                const expiresDate = new Date(job.date_expires || (Date.now() + 30 * 24 * 60 * 60 * 1000));
                job.expiresAt = admin.firestore.Timestamp.fromDate(expiresDate);
            }

            try {
                await db.collection('jobs').doc(jobId).set(job);
                console.log(✅ Job \/\ added: "\");
                successCount++;
            } catch (error) {
                console.error(❌ Job \/\ failed: "\" - \);
                errorCount++;
            }

            await new Promise(resolve => setTimeout(resolve, 100));
        }

        console.log(\nSummary:);
        console.log(Successfully added: \ jobs);
        console.log(Failed: \ jobs);

        process.exit(errorCount > 0 ? 1 : 0);
    } catch (error) {
        console.error('Fatal error:', error.message);
        process.exit(1);
    }
}

sendJobsToFirebase();