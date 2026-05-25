const admin = require('firebase-admin');
const path = require('path');

// Initialize Firebase Admin
const serviceAccountPath = process.env.FIREBASE_SERVICE_ACCOUNT_PATH || './serviceAccountKey.json';

if (!require('fs').existsSync(serviceAccountPath)) {
    console.error(`❌ Service account file not found: ${serviceAccountPath}`);
    console.error(`Set FIREBASE_SERVICE_ACCOUNT_PATH environment variable or place serviceAccountKey.json in current directory`);
    process.exit(1);
}

const serviceAccount = require(path.resolve(serviceAccountPath));

admin.initializeApp({
    credential: admin.credential.cert(serviceAccount),
});

const db = admin.firestore();

// 10 sample jobs to send to Firebase
const sampleJobs = [
    {
        title: "Senior Software Engineer - Python",
        description: "We are looking for an experienced Senior Software Engineer with strong Python expertise to join our growing team.",
        jobCategory: ["information-technology"],
        jobLocation: ["Helsinki"],
        jobLanguages: ["English", "Finnish"],
        jobTimes: ["full-time"],
        jobType: ["permanent"],
        jobLink: "https://findjobsinfinland.fi/jobs/information-technology/senior-software-engineer-python-helsinki",
        imageUrl: "https://findjobsinfinland.fi/images/jobs/it-and-tech-jobs.png",
        date_posted: new Date().toISOString().split('T')[0],
        date_expires: new Date(Date.now() + 30 * 24 * 60 * 60 * 1000).toISOString().split('T')[0],
        expiresAt: admin.firestore.Timestamp.fromDate(new Date(Date.now() + 30 * 24 * 60 * 60 * 1000)),
    },
    {
        title: "Data Analyst - Analytics",
        description: "Analyze business data and create insights to drive decision making in our analytics team.",
        jobCategory: ["information-technology"],
        jobLocation: ["Tampere"],
        jobLanguages: ["English"],
        jobTimes: ["full-time"],
        jobType: ["permanent"],
        jobLink: "https://findjobsinfinland.fi/jobs/information-technology/data-analyst-tampere",
        imageUrl: "https://findjobsinfinland.fi/images/jobs/it-and-tech-jobs.png",
        date_posted: new Date().toISOString().split('T')[0],
        date_expires: new Date(Date.now() + 30 * 24 * 60 * 60 * 1000).toISOString().split('T')[0],
        expiresAt: admin.firestore.Timestamp.fromDate(new Date(Date.now() + 30 * 24 * 60 * 60 * 1000)),
    },
    {
        title: "Frontend Developer - React",
        description: "Build modern web applications using React and TypeScript with a focus on performance.",
        jobCategory: ["information-technology"],
        jobLocation: ["Espoo"],
        jobLanguages: ["English", "Finnish"],
        jobTimes: ["full-time"],
        jobType: ["permanent"],
        jobLink: "https://findjobsinfinland.fi/jobs/information-technology/frontend-developer-react-espoo",
        imageUrl: "https://findjobsinfinland.fi/images/jobs/it-and-tech-jobs.png",
        date_posted: new Date().toISOString().split('T')[0],
        date_expires: new Date(Date.now() + 30 * 24 * 60 * 60 * 1000).toISOString().split('T')[0],
        expiresAt: admin.firestore.Timestamp.fromDate(new Date(Date.now() + 30 * 24 * 60 * 60 * 1000)),
    },
    {
        title: "DevOps Engineer",
        description: "Manage cloud infrastructure, CI/CD pipelines, and ensure system reliability.",
        jobCategory: ["information-technology"],
        jobLocation: ["Vantaa"],
        jobLanguages: ["English"],
        jobTimes: ["full-time"],
        jobType: ["permanent"],
        jobLink: "https://findjobsinfinland.fi/jobs/information-technology/devops-engineer-vantaa",
        imageUrl: "https://findjobsinfinland.fi/images/jobs/it-and-tech-jobs.png",
        date_posted: new Date().toISOString().split('T')[0],
        date_expires: new Date(Date.now() + 30 * 24 * 60 * 60 * 1000).toISOString().split('T')[0],
        expiresAt: admin.firestore.Timestamp.fromDate(new Date(Date.now() + 30 * 24 * 60 * 60 * 1000)),
    },
    {
        title: "UX/UI Designer",
        description: "Design beautiful and intuitive user interfaces for web and mobile applications.",
        jobCategory: ["engineering-and-design"],
        jobLocation: ["Helsinki"],
        jobLanguages: ["English", "Finnish"],
        jobTimes: ["full-time"],
        jobType: ["permanent"],
        jobLink: "https://findjobsinfinland.fi/jobs/engineering-and-design/uxui-designer-helsinki",
        imageUrl: "https://findjobsinfinland.fi/images/jobs/design-jobs.png",
        date_posted: new Date().toISOString().split('T')[0],
        date_expires: new Date(Date.now() + 30 * 24 * 60 * 60 * 1000).toISOString().split('T')[0],
        expiresAt: admin.firestore.Timestamp.fromDate(new Date(Date.now() + 30 * 24 * 60 * 60 * 1000)),
    },
    {
        title: "Cloud Architect",
        description: "Design and implement scalable cloud solutions using AWS, Azure, or Google Cloud.",
        jobCategory: ["information-technology"],
        jobLocation: ["Turku"],
        jobLanguages: ["English"],
        jobTimes: ["full-time"],
        jobType: ["permanent"],
        jobLink: "https://findjobsinfinland.fi/jobs/information-technology/cloud-architect-turku",
        imageUrl: "https://findjobsinfinland.fi/images/jobs/it-and-tech-jobs.png",
        date_posted: new Date().toISOString().split('T')[0],
        date_expires: new Date(Date.now() + 30 * 24 * 60 * 60 * 1000).toISOString().split('T')[0],
        expiresAt: admin.firestore.Timestamp.fromDate(new Date(Date.now() + 30 * 24 * 60 * 60 * 1000)),
    },
    {
        title: "Mobile App Developer - iOS",
        description: "Develop high-quality iOS applications using Swift and modern development practices.",
        jobCategory: ["information-technology"],
        jobLocation: ["Oulu"],
        jobLanguages: ["English", "Finnish"],
        jobTimes: ["full-time"],
        jobType: ["permanent"],
        jobLink: "https://findjobsinfinland.fi/jobs/information-technology/ios-developer-oulu",
        imageUrl: "https://findjobsinfinland.fi/images/jobs/it-and-tech-jobs.png",
        date_posted: new Date().toISOString().split('T')[0],
        date_expires: new Date(Date.now() + 30 * 24 * 60 * 60 * 1000).toISOString().split('T')[0],
        expiresAt: admin.firestore.Timestamp.fromDate(new Date(Date.now() + 30 * 24 * 60 * 60 * 1000)),
    },
    {
        title: "QA Engineer - Automation",
        description: "Create and maintain automated test suites for web and mobile applications.",
        jobCategory: ["quality-assurance-and-inspection"],
        jobLocation: ["Tampere"],
        jobLanguages: ["English"],
        jobTimes: ["full-time"],
        jobType: ["permanent"],
        jobLink: "https://findjobsinfinland.fi/jobs/quality-assurance/qa-engineer-tampere",
        imageUrl: "https://findjobsinfinland.fi/images/jobs/qa-jobs.png",
        date_posted: new Date().toISOString().split('T')[0],
        date_expires: new Date(Date.now() + 30 * 24 * 60 * 60 * 1000).toISOString().split('T')[0],
        expiresAt: admin.firestore.Timestamp.fromDate(new Date(Date.now() + 30 * 24 * 60 * 60 * 1000)),
    },
    {
        title: "Business Analyst",
        description: "Analyze business requirements and translate them into technical specifications.",
        jobCategory: ["business-and-administration"],
        jobLocation: ["Helsinki"],
        jobLanguages: ["English", "Finnish"],
        jobTimes: ["full-time"],
        jobType: ["permanent"],
        jobLink: "https://findjobsinfinland.fi/jobs/business-and-administration/business-analyst-helsinki",
        imageUrl: "https://findjobsinfinland.fi/images/jobs/business-jobs.png",
        date_posted: new Date().toISOString().split('T')[0],
        date_expires: new Date(Date.now() + 30 * 24 * 60 * 60 * 1000).toISOString().split('T')[0],
        expiresAt: admin.firestore.Timestamp.fromDate(new Date(Date.now() + 30 * 24 * 60 * 60 * 1000)),
    },
    {
        title: "Security Engineer",
        description: "Implement and maintain security systems to protect our infrastructure and data.",
        jobCategory: ["information-technology"],
        jobLocation: ["Espoo"],
        jobLanguages: ["English"],
        jobTimes: ["full-time"],
        jobType: ["permanent"],
        jobLink: "https://findjobsinfinland.fi/jobs/information-technology/security-engineer-espoo",
        imageUrl: "https://findjobsinfinland.fi/images/jobs/it-and-tech-jobs.png",
        date_posted: new Date().toISOString().split('T')[0],
        date_expires: new Date(Date.now() + 30 * 24 * 60 * 60 * 1000).toISOString().split('T')[0],
        expiresAt: admin.firestore.Timestamp.fromDate(new Date(Date.now() + 30 * 24 * 60 * 60 * 1000)),
    },
];

async function sendJobsToFirebase() {
    try {
        console.log('📤 Starting to send 10 jobs to Firebase Firestore...\n');

        let successCount = 0;
        let errorCount = 0;

        for (let i = 0; i < sampleJobs.length; i++) {
            const job = sampleJobs[i];
            const jobId = `test-job-${Date.now()}-${i}`;

            try {
                await db.collection('jobs').doc(jobId).set(job);
                console.log(`✅ Job ${i + 1}/10 added: "${job.title}" (ID: ${jobId})`);
                successCount++;
            } catch (error) {
                console.error(`❌ Job ${i + 1}/10 failed: "${job.title}" - ${error.message}`);
                errorCount++;
            }

            // Add a small delay to avoid rate limiting
            await new Promise(resolve => setTimeout(resolve, 100));
        }

        console.log(`\n${'='.repeat(60)}`);
        console.log(`📊 Summary:`);
        console.log(`   ✅ Successfully added: ${successCount} jobs`);
        console.log(`   ❌ Failed: ${errorCount} jobs`);
        console.log(`${'='.repeat(60)}\n`);

        if (successCount > 0) {
            console.log('🔔 Jobs added! The Firebase functions will automatically:');
            console.log('   • Match jobs with user preferences');
            console.log('   • Queue email notifications (daily/weekly/monthly digests)');
            console.log('   • Send push notifications (instantly or batched)');
            console.log('\n⏱️  To check the results:');
            console.log('   1. Go to Firebase Console > Firestore > jobs collection');
            console.log('   2. Check users > {userId} > emailAlerts / pushAlerts');
            console.log('   3. Monitor notifQueue for instant push notifications\n');
        }

        process.exit(errorCount > 0 ? 1 : 0);
    } catch (error) {
        console.error('❌ Fatal error:', error.message);
        process.exit(1);
    }
}

// Run the function
sendJobsToFirebase();
