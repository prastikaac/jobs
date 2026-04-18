/**
 * Test: Staggered Notification Queue
 * 
 * Creates a fake job in Firestore → triggers sendJobAlertEmails →
 * polls notifQueue to confirm staggered entries are created.
 *
 * Run from the /functions directory:
 *   node ../../../.gemini/antigravity/brain/d684559e-6315-4231-919e-5bf2c9033bfb/scratch/test_notif_queue.js
 */

const { initializeApp, cert } = require("firebase-admin/app");
const { getFirestore, Timestamp } = require("firebase-admin/firestore");

// Uses Application Default Credentials (already set up via firebase login)
initializeApp({ projectId: "findjobsinfinland-3c061" });

const db = getFirestore();

const TEST_JOB_ID = `test-job-${Date.now()}`;

async function main() {
    console.log("=== notifQueue Test ===\n");

    // Step 1: Write a test job to Firestore
    console.log(`[1] Creating test job: jobs/${TEST_JOB_ID}`);
    await db.collection("jobs").doc(TEST_JOB_ID).set({
        title: "Test Job — Stagger Queue Check",
        description: "This is a test job to verify the staggered notification queue.",
        jobCategory: ["information-technology"],
        jobLocation: ["helsinki"],
        jobLanguages: ["english"],
        jobTimes: ["full-time"],
        jobType: ["permanent"],
        jobLink: "https://findjobsinfinland.fi",
        imageUrl: "https://findjobsinfinland.fi/images/jobs/it-and-tech-jobs.png",
        date_posted: new Date().toISOString().split("T")[0],
        expiresAt: Timestamp.fromDate(new Date(Date.now() + 30 * 24 * 60 * 60 * 1000)), // 30 days
        createdAt: Timestamp.now(),
    });
    console.log("  ✅ Job created. Waiting 15 seconds for Cloud Function to fire...\n");

    await sleep(15000);

    // Step 2: Check notifQueue for entries related to this job
    console.log(`[2] Checking notifQueue for jobId = "${TEST_JOB_ID}"...`);
    const queueSnap = await db.collection("notifQueue")
        .where("jobId", "==", TEST_JOB_ID)
        .get();

    if (queueSnap.empty) {
        console.log("  ❌ No entries found in notifQueue for this job.");
        console.log("     Possible reasons:");
        console.log("     - No users match the test job's categories/locations");
        console.log("     - The Cloud Function hasn't fired yet (may take up to 30s)");
        console.log("     - The function threw an error (check Firebase Console logs)");
    } else {
        console.log(`  ✅ Found ${queueSnap.size} entry/entries in notifQueue:\n`);
        const entries = [];
        queueSnap.forEach(doc => {
            const d = doc.data();
            entries.push({
                docId: doc.id,
                userId: d.userId,
                status: d.status,
                scheduledAt: d.scheduledAt?.toDate?.().toISOString() ?? "n/a",
                createdAt: d.createdAt?.toDate?.().toISOString() ?? "n/a",
            });
        });

        // Sort by scheduledAt to show stagger
        entries.sort((a, b) => a.scheduledAt.localeCompare(b.scheduledAt));

        entries.forEach((e, i) => {
            console.log(`  Entry ${i + 1}: docId=${e.docId}`);
            console.log(`    userId:      ${e.userId}`);
            console.log(`    status:      ${e.status}`);
            console.log(`    scheduledAt: ${e.scheduledAt}`);
            console.log(`    createdAt:   ${e.createdAt}`);
            if (i > 0) {
                const prev = new Date(entries[i - 1].scheduledAt);
                const curr = new Date(e.scheduledAt);
                const diffMin = ((curr - prev) / 60000).toFixed(1);
                console.log(`    ⏱  Gap from previous: ${diffMin} min`);
            }
            console.log();
        });
    }

    // Step 3: Clean up test job
    console.log(`[3] Cleaning up: deleting test job jobs/${TEST_JOB_ID}`);
    await db.collection("jobs").doc(TEST_JOB_ID).delete();
    console.log("  ✅ Test job deleted.\n");

    console.log("=== Test Complete ===");
    process.exit(0);
}

function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

main().catch(err => {
    console.error("Test failed:", err);
    process.exit(1);
});
