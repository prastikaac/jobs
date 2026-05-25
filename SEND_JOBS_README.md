# Send Jobs to Firebase for Alerts

This script adds 10 sample jobs to Firebase Firestore, which automatically triggers the notification system to send alerts to matching users.

## Prerequisites

1. **Firebase Admin SDK** - Already installed in `functions/package.json`
2. **Service Account Key** - You need a Firebase service account key JSON file

## Setup Instructions

### Step 1: Get Your Firebase Service Account Key

1. Go to [Firebase Console](https://console.firebase.google.com/)
2. Select your project: `findjobsinfinland-3c061`
3. Navigate to **Settings** (gear icon) → **Service Accounts**
4. Click **Generate New Private Key**
5. Save the downloaded JSON file as `serviceAccountKey.json` in the root directory

### Step 2: Install Dependencies

```bash
npm install firebase-admin
```

### Step 3: Run the Script

#### Option A: With Service Account File in Root
```bash
node send-jobs-to-firebase.js
```

#### Option B: Using Environment Variable
```bash
FIREBASE_SERVICE_ACCOUNT_PATH="/path/to/serviceAccountKey.json" node send-jobs-to-firebase.js
```

#### Option C: From Functions Directory
```bash
cd functions
node ../send-jobs-to-firebase.js
```

## What This Script Does

The script creates 10 sample jobs in the `jobs` collection with these fields:
- `title` - Job title
- `description` - Job description
- `jobCategory` - Job categories (e.g., "information-technology")
- `jobLocation` - Locations (e.g., "Helsinki", "Tampere")
- `jobLanguages` - Required languages
- `jobTimes` - Employment type (full-time, part-time, etc.)
- `jobType` - Contract type (permanent, temporary, etc.)
- `jobLink` - URL to apply
- `imageUrl` - Job category image
- `date_posted` - Posted date
- `date_expires` - Expiration date
- `expiresAt` - Expiration timestamp

## Automatic Notification Processing

Once jobs are added, the Firebase Cloud Functions automatically:

1. **Trigger `sendJobAlertEmails` function** - When a job is created:
   - Matches job criteria with user preferences (category, location, language, etc.)
   - Queues email alerts for matching users (stored in `users/{userId}/emailAlerts`)
   - Creates push alerts for matching users (stored in `users/{userId}/pushAlerts`)
   - Queues instant push notifications if users have "instantly" frequency enabled

2. **Process Scheduled Digests** - Daily at scheduled times:
   - Batches email alerts and sends daily/weekly/monthly digests
   - Batches push notifications and sends digests
   - Cleans up expired alerts

3. **Process Notification Queue** - Every 5 minutes:
   - Sends instant push notifications via FCM
   - Removes stale/invalid FCM tokens

## Monitoring Results

### Check in Firebase Console:

1. **View jobs created:**
   - Firestore → `jobs` collection
   - You should see 10 new documents with IDs like `test-job-{timestamp}-{index}`

2. **Check email alerts:**
   - Firestore → `users/{userId}/emailAlerts`
   - You'll see alerts for jobs that match user preferences

3. **Check push alerts:**
   - Firestore → `users/{userId}/pushAlerts`
   - Shows in-app notification data

4. **Monitor notification queue:**
   - Firestore → `notifQueue`
   - Shows pending FCM push notifications

## Testing Tips

1. **Create a test user** first with job preferences matching the test jobs
2. **Set notification preferences** to enable both email and push
3. **Set alert frequency** to "instantly" to see immediate notifications
4. **Check email** - emails are only sent in digests (daily/weekly/monthly)
5. **Check push notifications** - delivered to devices with registered FCM tokens

## Sample Job Details

The script creates jobs in these categories:
- Information Technology (6 jobs)
- Engineering & Design (1 job)
- Quality Assurance (1 job)
- Business & Administration (1 job)
- Healthcare (0 jobs - can be customized)

## Customization

To add different test jobs, edit the `sampleJobs` array in the script:

```javascript
const sampleJobs = [
    {
        title: "Your Job Title",
        description: "Your job description",
        jobCategory: ["your-category"],
        jobLocation: ["Your City"],
        // ... other fields
    },
    // Add more jobs
];
```

## Troubleshooting

**Error: "Service account file not found"**
- Make sure `serviceAccountKey.json` is in the same directory as the script
- Or set the `FIREBASE_SERVICE_ACCOUNT_PATH` environment variable

**Error: "Permission denied"**
- Check that your service account has Firestore write permissions
- Verify the project ID in the service account matches `findjobsinfinland-3c061`

**No emails received**
- Email alerts are only sent in digests (daily/weekly/monthly)
- Check user's `emailAlertFrequency` setting
- Verify user's email is set

**No push notifications received**
- Requires FCM token registered for the device
- User must have "Push Notifications" enabled in their profile
- Device must have the app installed with push notifications permission

## For Production Use

- Don't commit `serviceAccountKey.json` to git (add to `.gitignore`)
- Use environment variables for sensitive configuration
- Monitor quota usage in Firebase Console
- Consider batch operations for large numbers of jobs
- Set up proper expiration dates for jobs

## Related Functions

- `sendJobAlertEmails` - Triggered when a job is created
- `processScheduledDigests` - Runs daily at 0:00, 6:00, 12:00, 18:00 UTC
- `processNotifQueue` - Runs every 5 minutes
- `deleteExpiredJobs` - Runs daily
- `deleteStalePushAlerts` - Runs daily
