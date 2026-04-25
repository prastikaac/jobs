// firebase deploy --only functions

const { onDocumentCreated } = require("firebase-functions/v2/firestore")
const { onSchedule } = require("firebase-functions/v2/scheduler")
const { setGlobalOptions } = require("firebase-functions/v2")
const { defineSecret } = require("firebase-functions/params")
const { initializeApp } = require("firebase-admin/app")
const { getFirestore, Timestamp } = require("firebase-admin/firestore")
const { getMessaging } = require("firebase-admin/messaging")
const nodemailer = require("nodemailer")

setGlobalOptions({ region: "europe-north1" })
initializeApp()

const GMAIL_USER = defineSecret("GMAIL_USER")
const GMAIL_APP_PASSWORD = defineSecret("GMAIL_APP_PASSWORD")

function createTransporter() {
    return nodemailer.createTransport({
        service: "gmail",
        auth: {
            user: process.env.GMAIL_USER,
            pass: process.env.GMAIL_APP_PASSWORD,
        },
    })
}

function sendEmail({ to, subject, html }) {
    const transporter = createTransporter()
    return transporter.sendMail({
        from: `findjobsinfinland <${process.env.GMAIL_USER}>`,
        to,
        subject,
        html,
    })
}

const OWNER_EMAIL = "acharyaprasiddha6@gmail.com"
const DEFAULT_IMAGE = "https://findjobsinfinland.fi/images/jobs/it-and-tech-jobs.png"
const SITE_URL = "https://findjobsinfinland.fi"

// Build locationMap dynamically from all_jobs_loc.json
// JSON shape: { "Region": ["City1", "City2", ...], ... }
const allJobsLoc = require("./all_jobs_loc.json")
const locationMap = {}
for (const [region, cities] of Object.entries(allJobsLoc)) {
    for (const city of cities) {
        locationMap[city] = `${city}, ${region}, Finland`
    }
}

function normalizeToArray(value) {
    if (Array.isArray(value)) return value.filter(Boolean)
    if (value === undefined || value === null || value === "") return []
    return [value]
}

function getJobLanguages(jobData) {
    if (Array.isArray(jobData.jobLanguages)) return jobData.jobLanguages.filter(Boolean)
    if (Array.isArray(jobData.jobLanguage)) return jobData.jobLanguage.filter(Boolean)
    if (jobData.jobLanguages) return [jobData.jobLanguages]
    if (jobData.jobLanguage) return [jobData.jobLanguage]
    return []
}

function getFormattedLocation(location) {
    if (!location) return "Finland"

    const strLocation = String(location).trim()
    if (!strLocation) return "Finland"

    const normalizedLocation =
        strLocation.charAt(0).toUpperCase() + strLocation.slice(1).toLowerCase()

    return locationMap[normalizedLocation] || `${normalizedLocation}, Finland`
}

function getFormattedLocationsString(jobLocation) {
    return normalizeToArray(jobLocation)
        .map((loc) => getFormattedLocation(loc))
        .join(", ") || "Finland"
}

function escapeHtml(text) {
    return String(text || "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;")
}

function isExpiredTimestamp(ts) {
    return !!(ts && typeof ts.toMillis === "function" && ts.toMillis() <= Date.now())
}

function isValidFrequency(value) {
    return ["instantly", "daily", "weekly", "monthly"].includes(value)
}

// Email never sends instantly — only daily/weekly/monthly digests are supported

function isValidEmailFrequency(value) {
    return ["daily", "weekly", "monthly"].includes(value)
}

async function sendPushToTokenAndCleanup({ token, message, db, userDocId, fcmTokens }) {
    try {
        await getMessaging().send(message)
        return true
    } catch (error) {
        console.error(`Error sending to token ${token}:`, error.message)

        if (
            error.code === "messaging/registration-token-not-registered" ||
            String(error.message).includes("Requested entity was not found")
        ) {
            const newTokens = fcmTokens.filter((t) => t !== token)
            await db.collection("users").doc(userDocId).update({
                fcmTokens: newTokens,
            })
            console.log(`Removed invalid token for user ${userDocId}`)
        }

        return false
    }
}

// buildSingleJobEmailHTML removed — emails are never sent instantly.
// All job email alerts are now batched via pendingAlerts and sent as
// daily / weekly / monthly digests through buildDigestEmailHTML.

function buildDigestEmailHTML(frequency, jobs) {
    const capitalizedFrequency = frequency.charAt(0).toUpperCase() + frequency.slice(1)

    const jobCards = jobs.map((job) => {
        const formattedLocations = getFormattedLocationsString(job.jobLocation)

        return `
            <table cellpadding="0" cellspacing="0" border="0" width="100%" style="background-color: #ffffff; border-radius: 12px; box-shadow: 0 5px 35px rgba(0, 0, 0, .07); margin-bottom: 25px; border: 1px solid #e0e0e0;">
                <tr>
                    <td style="padding: 20px; text-align: center;">
                        <a href="${job.jobLink || "#"}" style="display: block; text-decoration: none;">
                            <img src="${job.imageUrl || DEFAULT_IMAGE}" alt="Job Image" style="width: 100%; max-width: 100%; height: auto; object-fit: contain; border-radius: 12px; display: block;">
                        </a>
                    </td>
                </tr>
                <tr>
                    <td style="padding: 20px; padding-top: 5px;">
                        <div style="font-size: 13px; color: #666666; font-weight: bold; margin-bottom: 12px;">
                            📍 ${formattedLocations}
                        </div>
                        <h2 style="font-size: 20px; font-weight: bold; margin: 0 0 10px 0; color: #005effff;">${escapeHtml(job.title)}</h2>
                        <p style="font-size: 14px; line-height: 1.6; margin: 0 0 20px 0; color: #666666;">${escapeHtml(job.description)}</p>
                        <a href="${job.jobLink || "#"}" style="background-color: #e82c2f; color: #ffffff; padding: 10px 25px; border-radius: 6px; text-decoration: none; font-weight: bold; display: inline-block;">Apply Now</a>
                    </td>
                </tr>
            </table>
        `
    }).join("")

    return `
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>${capitalizedFrequency} Job Alerts</title>
            <style>
                @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@400;700&display=swap');
                body {
                    font-family: 'Poppins', sans-serif;
                    margin: 0;
                    margin-top: 20px;
                    margin-left: 5px;
                    background-color: #f4f4f4;
                }
                .main-content-wrapper {
                    background-color: #ffffff;
                    border-radius: 12px;
                    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
                }
                .text-base-mobile { font-size: 14px; }
                .text-sm-mobile { font-size: 13px; }
                .text-xs-mobile { font-size: 12px; }
                @media only screen and (min-width: 601px) {
                    .text-base-pc { font-size: 16px !important; }
                    .text-sm-pc { font-size: 14px !important; }
                    .text-xs-pc { font-size: 13px !important; }
                }
            </style>
        </head>
        <body style="font-family: 'Poppins', sans-serif; margin: 0; margin-top: 20px; margin-left: 5px; background-color: #f4f4f4; border-radius: 12px;">
            <table cellpadding="0" cellspacing="0" border="0" width="100%">
                <tr>
                    <td align="center">
                        <table cellpadding="0" cellspacing="0" border="0" width="100%" class="email-container" style="max-width: 100%;">
                            <tr>
                                <td>
                                    <table cellpadding="0" cellspacing="0" border="0" width="100%" class="main-content-wrapper">
                                        <tr>
                                            <td style="background-color: #242424ff; padding: 20px; text-align: center; border-radius: 12px 12px 0 0;">
                                                <table cellpadding="0" cellspacing="0" border="0" style="margin: 0 auto;">
                                                    <tr>
                                                        <td style="vertical-align: middle;">
                                                            <img src="${SITE_URL}/images/icon.png" alt="findjobsinfinland Logo" style="width: 40px; height: 40px; margin-right: 10px; vertical-align: middle;">
                                                        </td>
                                                        <td style="vertical-align: middle;">
                                                            <h1 style="font-size: 23px; color: #ffffff; margin: 0; font-weight: bold;">findjobsinfinland.fi</h1>
                                                        </td>
                                                    </tr>
                                                </table>
                                            </td>
                                        </tr>
                                        <tr>
                                            <td style="padding: 25px 30px;">
                                                <h2 style="font-size: 24px; color: #005effff; margin: 0 0 15px 0;">Your ${capitalizedFrequency} Job Alerts</h2>
                                                <p class="text-base-mobile text-base-pc" style="font-size: 15px; color: #555555; line-height: 1.6; margin-bottom: 20px;">
                                                    Dear user, <br><br>
                                                    Here ${jobs.length === 1 ? "is" : "are"} <strong>${jobs.length}</strong> new ${jobs.length === 1 ? "job" : "jobs"} matching your preferences.
                                                </p>
                                                ${jobCards}
                                                <div style="text-align: left; margin: 30px 0;">
                                                    <h3 style="font-size: 20px; font-weight: bold; margin: 0 0 15px 0; color: #005effff;">Want to browse more options?</h3>
                                                    <p class="text-base-mobile text-base-pc" style="font-size: 15px; color: #555555; line-height: 1.6; margin: 0 0 20px 0;">
                                                        Explore more opportunities tailored to your skills and preferences on findjobsinfinland.fi.
                                                    </p>
                                                    <a href="${SITE_URL}/jobs" style="background-color: #696969ff; color: #ffffff; padding: 12px 0; border-radius: 6px; text-decoration: none; font-weight: bold; display: block; width: 100%; text-align: center;">Browse More Jobs</a>
                                                </div>
                                            </td>
                                        </tr>
                                        <tr>
                                            <td style="background-color: #f5f0eb; padding: 20px; text-align: center; border-radius: 0 0 12px 12px; border-top: 1px solid #e9ecef;">
                                                <p class="text-sm-mobile text-sm-pc" style="font-size: 13px; color: #005effff; margin: 0 0 15px 0; line-height: 1.5;">
                                                    <a href="${SITE_URL}/disclaimer" style="color: #005effff; text-decoration: none; margin: 0 5px;">Disclaimer</a>
                                                    <span style="color: #666666; margin: 0 5px;">|</span>
                                                    <a href="${SITE_URL}/privacy-policy" style="color: #005effff; text-decoration: none; margin: 0 5px;">Privacy Policy</a>
                                                </p>
                                                <p class="text-xs-mobile text-xs-pc" style="font-size: 12px; color: #888888; line-height: 1.6; margin-top: 10px; margin-bottom: 10px; text-align: center;">
                                                    If you would prefer not to receive any further job updates or notifications via email, you can easily opt out at any time by clicking on <a href="${SITE_URL}/edit-profile#unsubscribe" style="color: #e82c2f; text-decoration: underline;">unsubscribe</a>.
                                                </p>
                                                <p class="text-xs-mobile text-xs-pc" style="font-size: 12px; color: #888888; margin: 0; line-height: 1.4;">
                                                    © 2026 · <span style="color: #28a745; font-weight: 500;">findjobsinfinland.fi</span> · All rights reserved.
                                                </p>
                                            </td>
                                        </tr>
                                    </table>
                                </td>
                            </tr>
                        </table>
                    </td>
                </tr>
            </table>
         <script src="/js/main.js"></script>
</body>
        </html>
    `
}

async function processUserDigests() {
    const db = getFirestore()
    const usersSnapshot = await db.collection("users").get()

    const now = new Date(new Date().toLocaleString("en-US", { timeZone: "Europe/Helsinki" }))
    const cHour = now.getHours()
    const cMin = now.getMinutes()
    const cDay = now.getDay() // 0=Sunday, 1=Monday (matches UI)
    const cDate = now.getDate()

    // We'll track stats per frequency just for the admin report
    const stats = {
        daily: { usersProcessed: 0, emailsSent: 0, pushSent: 0, jobsSent: 0, expiredRemoved: 0 },
        weekly: { usersProcessed: 0, emailsSent: 0, pushSent: 0, jobsSent: 0, expiredRemoved: 0 },
        monthly: { usersProcessed: 0, emailsSent: 0, pushSent: 0, jobsSent: 0, expiredRemoved: 0 }
    }

    for (const userDoc of usersSnapshot.docs) {
        const user = userDoc.data()
        const userId = userDoc.id

        const jobSubscription = user.jobSubscription || {}
        const emailNotificationEnabled = jobSubscription.emailNotification ?? true
        const pushNotificationEnabled = jobSubscription.pushNotification ?? true
        const fcmTokens = Array.isArray(user.fcmTokens) ? user.fcmTokens : []

        const legacyFreq = isValidFrequency(user.jobAlertFrequency) ? user.jobAlertFrequency : "instantly"
        const emailFreq = isValidEmailFrequency(user.emailAlertFrequency) ? user.emailAlertFrequency : (isValidEmailFrequency(legacyFreq) ? legacyFreq : "daily")
        const pushFreq = isValidFrequency(user.pushAlertFrequency) ? user.pushAlertFrequency : legacyFreq

        const emailSched = user.emailScheduleTime || {}
        const eHour = isNaN(emailSched.hour) ? 9 : Number(emailSched.hour)
        const eMin = isNaN(emailSched.minute) ? 0 : Number(emailSched.minute)

        const pushSched = user.pushScheduleTime || {}
        const pHour = isNaN(pushSched.hour) ? 9 : Number(pushSched.hour)
        const pMin = isNaN(pushSched.minute) ? 0 : Number(pushSched.minute)

        // Matching bucket: our cron runs at roughly 0, 5, 10, 15, 20...
        const emailTimeMatch = eHour === cHour && Math.floor(cMin / 5) === Math.floor(eMin / 5)
        const pushTimeMatch = pHour === cHour && Math.floor(cMin / 5) === Math.floor(pMin / 5)

        let processEmail = false
        if (emailNotificationEnabled && user.email && emailTimeMatch) {
            if (emailFreq === "daily") processEmail = true
            else if (emailFreq === "weekly" && cDay === Number(emailSched.dayOfWeek ?? 1)) processEmail = true
            else if (emailFreq === "monthly" && cDate === Number(emailSched.dayOfMonth ?? 1)) processEmail = true
        }

        let processPush = false
        if (pushNotificationEnabled && fcmTokens.length > 0 && pushTimeMatch && ["daily", "weekly", "monthly"].includes(pushFreq)) {
            if (pushFreq === "daily") processPush = true
            else if (pushFreq === "weekly" && cDay === Number(pushSched.dayOfWeek ?? 1)) processPush = true
            else if (pushFreq === "monthly" && cDate === Number(pushSched.dayOfMonth ?? 1)) processPush = true
        }

        if (!processEmail && !processPush) continue

        const alertsSnapshot = await db.collection("users").doc(userId).collection("pendingAlerts").get()
        if (alertsSnapshot.empty) continue

        const emailAlertDocs = []
        const pushAlertDocs = []
        let expiredBatch = db.batch()
        let expiredCount = 0

        for (const alertDoc of alertsSnapshot.docs) {
            const data = alertDoc.data()
            if (isExpiredTimestamp(data.expiresAt)) {
                expiredBatch.delete(alertDoc.ref)
                expiredCount++
                if (data.frequency && stats[data.frequency]) stats[data.frequency].expiredRemoved++
                continue
            }
            if (processEmail && data.channel === "email" && data.frequency === emailFreq) emailAlertDocs.push({ ref: alertDoc.ref, data })
            if (processPush && data.channel === "push" && data.frequency === pushFreq) pushAlertDocs.push({ ref: alertDoc.ref, data })
        }

        if (expiredCount > 0) await expiredBatch.commit()

        let emailSuccess = false
        if (emailAlertDocs.length > 0) {
            const jobs = emailAlertDocs.map(d => d.data)
            try {
                await sendEmail({
                    to: user.email,
                    subject: `${emailFreq.charAt(0).toUpperCase() + emailFreq.slice(1)} Job Alerts (${jobs.length})`,
                    html: buildDigestEmailHTML(emailFreq, jobs),
                })
                emailSuccess = true
                stats[emailFreq].emailsSent++
                stats[emailFreq].jobsSent += jobs.length
                stats[emailFreq].usersProcessed++
            } catch (e) { console.error(`Error sending ${emailFreq} email to ${user.email}:`, e.message) }
        }

        let pushSuccessCountForUser = 0
        if (pushAlertDocs.length > 0) {
            const jobs = pushAlertDocs.map(d => d.data)
            const periodLabel = { daily: "today's", weekly: "this week's", monthly: "this month's" }[pushFreq] ?? pushFreq
            const tokenSnapshot = [...fcmTokens]
            for (const token of tokenSnapshot) {
                if (!token) continue
                const success = await sendPushToTokenAndCleanup({
                    token, db, userDocId: userId, fcmTokens,
                    message: {
                        token,
                        notification: {
                            title: "🔔 New Job Alerts",
                            body: `Here are your ${periodLabel} job alerts — ${jobs.length} new ${jobs.length === 1 ? "job" : "jobs"} waiting!`,
                        },
                        data: {
                            type: `${pushFreq}_digest`,
                            jobsCount: String(jobs.length),
                            url: `${SITE_URL}/newjobs?period=${pushFreq}`,
                        },
                    }
                })
                if (success) {
                    pushSuccessCountForUser++
                    stats[pushFreq].pushSent++
                }
            }
            if (pushSuccessCountForUser > 0) {
                stats[pushFreq].jobsSent += jobs.length
                stats[pushFreq].usersProcessed++ // Might double count if email processed too, but separated by channel logically
            }
        }

        // Cleanup pending alerts
        let cleanupBatch = db.batch()
        let cleanupCount = 0

        for (const doc of emailAlertDocs) {
            if (emailSuccess || (!emailNotificationEnabled || !user.email)) {
                cleanupBatch.delete(doc.ref)
                cleanupCount++
            }
        }
        for (const doc of pushAlertDocs) {
            if (pushSuccessCountForUser > 0 || (!pushNotificationEnabled || fcmTokens.length === 0)) {
                cleanupBatch.delete(doc.ref)
                cleanupCount++
            }
        }
        if (cleanupCount > 0) await cleanupBatch.commit()
    }

    // Save admin reports for any frequency that had action
    for (const freq of ["daily", "weekly", "monthly"]) {
        const s = stats[freq]
        if (s.usersProcessed > 0 || s.expiredRemoved > 0) {
            try {
                await db.collection("adminReports").add({
                    type: "digest_alert",
                    reportPeriod: freq,
                    frequency: freq,
                    usersProcessed: s.usersProcessed,
                    totalQueuedJobsSent: s.jobsSent,
                    totalExpiredQueuedJobsRemoved: s.expiredRemoved,
                    totalEmailsSent: s.emailsSent,
                    totalPushNotificationsSent: s.pushSent,
                    status: "pending",
                    createdAt: Timestamp.now()
                })
                console.log(`Saved ${freq} digest admin report.`)
            } catch (e) { console.error(`Failed to save ${freq} admin report:`, e.message) }
        }
    }
}

exports.sendJobAlertEmails = onDocumentCreated(
    {
        document: "jobs/{jobId}",
        secrets: [GMAIL_USER, GMAIL_APP_PASSWORD],
    },
    async (event) => {
        const jobData = event.data.data()
        const db = getFirestore()

        // Safety check: skip only if explicitly set AND already expired
        if (jobData.expiresAt && isExpiredTimestamp(jobData.expiresAt)) {
            console.log(`Skipping expired job alert for ${event.params.jobId}`)
            return
        }

        const usersSnapshot = await db.collection("users").get()

        // Email is ALWAYS queued — never sent instantly.
        // Push can be instant (via notifQueue) or queued (via pendingAlerts).
        let queuedEmailUsersCount = 0
        let instantPushQueuedCount = 0  // tracks push entries queued in notifQueue
        let queuedPushUsersCount = 0

        // Normalise job fields to lowercase arrays for case-insensitive matching
        const jobCategories = normalizeToArray(jobData.jobCategory).map(v => String(v).toLowerCase())
        const jobLocations = normalizeToArray(jobData.jobLocation).map(v => String(v).toLowerCase())
        const jobLanguages = getJobLanguages(jobData).map(v => String(v).toLowerCase())
        const jobTimes = normalizeToArray(jobData.jobTimes).map(v => String(v).toLowerCase())
        const jobTypes = normalizeToArray(jobData.jobType).map(v => String(v).toLowerCase())

        for (const doc of usersSnapshot.docs) {
            const user = doc.data()

            const userCategories = (Array.isArray(user.jobCategory) ? user.jobCategory : []).map(v => String(v).toLowerCase())
            const userLocations = (Array.isArray(user.jobLocation) ? user.jobLocation : []).map(v => String(v).toLowerCase())
            const userLanguages = (Array.isArray(user.jobLanguages) ? user.jobLanguages : []).map(v => String(v).toLowerCase())
            const userTimes = (Array.isArray(user.jobTimes) ? user.jobTimes : []).map(v => String(v).toLowerCase())
            const userTypes = (Array.isArray(user.jobType) ? user.jobType : []).map(v => String(v).toLowerCase())

            const fcmTokens = Array.isArray(user.fcmTokens) ? user.fcmTokens : []
            const jobSubscription = user.jobSubscription || {}
            const emailNotificationEnabled = jobSubscription.emailNotification ?? true
            const pushNotificationEnabled = jobSubscription.pushNotification ?? true

            // Resolve per-channel frequencies (email is always daily/weekly/monthly)
            const legacyFreq = isValidFrequency(user.jobAlertFrequency) ? user.jobAlertFrequency : "instantly"
            const emailAlertFrequency = isValidEmailFrequency(user.emailAlertFrequency)
                ? user.emailAlertFrequency
                : isValidEmailFrequency(legacyFreq) ? legacyFreq : "daily"
            const pushAlertFrequency = isValidFrequency(user.pushAlertFrequency)
                ? user.pushAlertFrequency
                : legacyFreq

            // Match logic — all criteria must pass (empty array = wildcard)
            const hasCategory = userCategories.length === 0 || jobCategories.length === 0 || jobCategories.some(c => userCategories.includes(c))
            const hasLocation = userLocations.length === 0 || jobLocations.length === 0 || jobLocations.some(l => userLocations.includes(l))
            const hasLanguage = userLanguages.length === 0 || jobLanguages.length === 0 || jobLanguages.some(l => userLanguages.includes(l))
            const hasTime = userTimes.length === 0 || jobTimes.length === 0 || jobTimes.some(t => userTimes.includes(t))
            const hasType = userTypes.length === 0 || jobTypes.length === 0 || jobTypes.some(t => userTypes.includes(t))

            if (!(hasCategory && hasLocation && hasLanguage && hasTime && hasType)) continue

            // ── Email: always queued, never instant ──────────────────────────
            if (emailNotificationEnabled && user.email) {
                await db
                    .collection("users")
                    .doc(doc.id)
                    .collection("pendingAlerts")
                    .doc(`email_${event.params.jobId}`)
                    .set({
                        jobId: event.params.jobId,
                        title: jobData.title || "",
                        description: jobData.description || "",
                        jobCategory: jobCategories,
                        jobLocation: jobLocations,
                        jobLanguages: jobLanguages,
                        jobTimes: jobTimes,
                        jobType: jobTypes,
                        jobLink: jobData.jobLink || "",
                        imageUrl: jobData.imageUrl || "",
                        date_posted: jobData.date_posted || "",
                        date_expires: jobData.date_expires || "",
                        expiresAt: jobData.expiresAt || null,
                        frequency: emailAlertFrequency,   // "daily" | "weekly" | "monthly"
                        channel: "email",
                        createdAt: Timestamp.now(),
                    }, { merge: true })
                queuedEmailUsersCount++
            }

            // ── Push: instant (notifQueue) OR queued (pendingAlerts) ─────────
            if (pushNotificationEnabled && fcmTokens.length > 0) {
                if (pushAlertFrequency === "instantly") {
                    // Stagger each push by 5 min per queued entry to avoid rate-limit spikes
                    for (const token of fcmTokens) {
                        if (!token) continue
                        const delayMs = instantPushQueuedCount * 5 * 60 * 1000
                        const scheduledAt = new Date(Date.now() + delayMs)
                        await db.collection("notifQueue").add({
                            userId: doc.id,
                            token,
                            jobId: event.params.jobId,
                            scheduledAt: Timestamp.fromDate(scheduledAt),
                            status: "pending",
                            createdAt: Timestamp.now(),
                            message: {
                                title: jobData.title || "New Job Alert",
                                body: jobData.description || "",
                                imageUrl: jobData.imageUrl || "",
                                jobLink: jobData.jobLink || "",
                            },
                        })
                        instantPushQueuedCount++
                    }
                } else if (["daily", "weekly", "monthly"].includes(pushAlertFrequency)) {
                    await db
                        .collection("users")
                        .doc(doc.id)
                        .collection("pendingAlerts")
                        .doc(`push_${event.params.jobId}`)
                        .set({
                            jobId: event.params.jobId,
                            title: jobData.title || "",
                            description: jobData.description || "",
                            jobCategory: jobCategories,
                            jobLocation: jobLocations,
                            jobLanguages: jobLanguages,
                            jobTimes: jobTimes,
                            jobType: jobTypes,
                            jobLink: jobData.jobLink || "",
                            imageUrl: jobData.imageUrl || "",
                            date_posted: jobData.date_posted || "",
                            date_expires: jobData.date_expires || "",
                            expiresAt: jobData.expiresAt || null,
                            frequency: pushAlertFrequency,
                            channel: "push",
                            createdAt: Timestamp.now(),
                        }, { merge: true })
                    queuedPushUsersCount++
                }
            }
        }

        try {
            await db.collection("adminReports").add({
                type: "job_alert",
                reportPeriod: "daily",
                jobTitle: jobData.title || event.params.jobId,
                queuedEmailUsersCount,
                instantPushQueuedCount,
                queuedPushUsersCount,
                status: "pending",
                createdAt: Timestamp.now(),
            })
        } catch (error) {
            console.error("Failed to save admin report to Firestore:", error.message)
        }

        console.log(`Job "${jobData.title || event.params.jobId}" indexed.`)
        console.log(`  Emails queued for digest: ${queuedEmailUsersCount}`)
        console.log(`  Instant push queued (staggered): ${instantPushQueuedCount}`)
        console.log(`  Push queued for digest: ${queuedPushUsersCount}`)
    })
exports.processScheduledDigests = onSchedule(
    {
        schedule: "*/5 * * * *",
        timeZone: "Europe/Helsinki",
        region: "europe-west1",
        secrets: [GMAIL_USER, GMAIL_APP_PASSWORD],
    },
    async () => {
        await processUserDigests()
    },
)

/**
 * Drain the notifQueue collection every minute.
 * Sends push notifications that are due (scheduledAt <= now) and marks them as sent.
 */
exports.processNotifQueue = onSchedule(
    {
        schedule: "* * * * *",
        timeZone: "Europe/Helsinki",
        region: "europe-west1",
    },
    async () => {
        const db = getFirestore()
        const now = Timestamp.now()

        const snapshot = await db
            .collection("notifQueue")
            .where("status", "==", "pending")
            .where("scheduledAt", "<=", now)
            .limit(100)
            .get()

        if (snapshot.empty) {
            console.log("notifQueue: nothing due right now.")
            return
        }

        let sent = 0
        let failed = 0

        for (const queueDoc of snapshot.docs) {
            const entry = queueDoc.data()
            const { token, userId, message } = entry

            if (!token || !message) {
                await queueDoc.ref.update({ status: "invalid" })
                continue
            }

            const fcmMessage = {
                token,
                notification: {
                    title: message.title || "New Job Alert",
                    body: message.body || "",
                    image: message.imageUrl || undefined,
                },
                data: {
                    jobId: entry.jobId || "",
                    jobLink: message.jobLink || "",
                    imageUrl: message.imageUrl || "",
                },
            }

            try {
                await getMessaging().send(fcmMessage)
                await queueDoc.ref.update({ status: "sent", sentAt: Timestamp.now() })
                sent++
            } catch (error) {
                console.error(`notifQueue: failed to send to token ${token}:`, error.message)

                // Remove invalid/expired FCM tokens from the user's document
                if (
                    error.code === "messaging/registration-token-not-registered" ||
                    String(error.message).includes("Requested entity was not found")
                ) {
                    try {
                        const userRef = db.collection("users").doc(userId)
                        const userSnap = await userRef.get()
                        if (userSnap.exists) {
                            const currentTokens = Array.isArray(userSnap.data().fcmTokens)
                                ? userSnap.data().fcmTokens
                                : []
                            await userRef.update({
                                fcmTokens: currentTokens.filter((t) => t !== token),
                            })
                            console.log(`notifQueue: removed stale token for user ${userId}`)
                        }
                    } catch (cleanupErr) {
                        console.error("notifQueue: failed to clean up stale token:", cleanupErr.message)
                    }
                }

                await queueDoc.ref.update({ status: "failed" })
                failed++
            }
        }

        console.log(`notifQueue: sent=${sent}, failed=${failed}`)
    },
)

/**
 * Automatically delete expired jobs from Firestore.
 * Runs every day at 00:10 Finland time.
 * It deletes jobs where expiresAt <= now.
 */
exports.deleteExpiredJobs = onSchedule(
    {
        schedule: "10 0 * * *",
        timeZone: "Europe/Helsinki",
        region: "europe-west1", // Cloud Scheduler doesn't support europe-north1
    },
    async () => {
        const db = getFirestore()
        const now = Timestamp.now()

        const snapshot = await db
            .collection("jobs")
            .where("expiresAt", "<=", now)
            .get()

        if (snapshot.empty) {
            console.log("No expired jobs found.")
            return
        }

        let batch = db.batch()
        let opCount = 0
        let totalDeleted = 0
        const BATCH_LIMIT = 400

        for (const doc of snapshot.docs) {
            const data = doc.data()
            console.log(`Deleting expired job: ${doc.id} | ${data.title || "Untitled Job"}`)

            batch.delete(doc.ref)
            opCount++
            totalDeleted++

            if (opCount === BATCH_LIMIT) {
                await batch.commit()
                batch = db.batch()
                opCount = 0
            }
        }

        if (opCount > 0) {
            await batch.commit()
        }

        console.log(`Deleted ${totalDeleted} expired job(s).`)
    },
)

// Always do firebase deploy --only functions after editing this file.

// ─── Shared helper ───────────────────────────────────────────────────────────

/**
 * Build the HTML body for an admin report email.
 * @param {string}   periodLabel  e.g. "Daily", "Weekly", "Monthly"
 * @param {object[]} jobAlerts    rows of type "job_alert"
 * @param {object[]} digestAlerts rows of type "digest_alert"
 */
function buildAdminReportHTML(periodLabel, jobAlerts, digestAlerts) {
    let html = `<h2>${periodLabel} Job Alerts Report</h2><hr/>`

    if (jobAlerts.length > 0) {
        jobAlerts.forEach((job) => {
            html += `
                <div style="margin-bottom:25px;border:1px solid #ddd;padding:15px;border-radius:8px;">
                    <h3 style="margin-top:0;">Job: ${escapeHtml(job.jobTitle)}</h3>
                    <p><strong>Emails queued for digest:</strong> ${job.queuedEmailUsersCount ?? 0}</p>
                    <p><strong>Instant push notifications queued (staggered):</strong> ${job.instantPushQueuedCount ?? 0}</p>
                    <p><strong>Push notifications queued for digest:</strong> ${job.queuedPushUsersCount ?? 0}</p>
                </div>`
        })
    } else {
        html += `<p>No new jobs were indexed during this period.</p>`
    }

    if (digestAlerts.length > 0) {
        html += `<h2>Digest Batch Summaries</h2><hr/>`
        digestAlerts.forEach((digest) => {
            html += `
                <div style="margin-bottom:20px;border:1px solid #ddd;padding:15px;border-radius:8px;">
                    <p><strong>Frequency:</strong> ${escapeHtml(digest.frequency)}</p>
                    <p><strong>Users processed:</strong> ${digest.usersProcessed ?? 0}</p>
                    <p><strong>Total valid queued jobs sent:</strong> ${digest.totalQueuedJobsSent ?? 0}</p>
                    <p><strong>Total expired queued jobs removed:</strong> ${digest.totalExpiredQueuedJobsRemoved ?? 0}</p>
                    <p><strong>Total emails sent:</strong> ${digest.totalEmailsSent ?? 0}</p>
                    <p><strong>Total push notifications sent:</strong> ${digest.totalPushNotificationsSent ?? 0}</p>
                </div>`
        })
    }

    html += `<p style="color:#888;font-size:12px;margin-top:30px;">Report automatically generated by findjobsinfinland.fi 🇫🇮</p>`
    return html
}

/**
 * Core logic for sending a scheduled admin report.
 * @param {object} db              Firestore instance
 * @param {string} periodLabel     Human-readable label, e.g. "Daily"
 * @param {string[]} reportPeriods Which reportPeriod values to sweep, e.g. ["daily"]
 * @param {string} emailSubject    Subject line for the outgoing email
 */
async function sendAdminReport(db, periodLabel, reportPeriods, emailSubject) {
    const ADMIN_TARGET_EMAIL = "acharyaprasiddha6@gmail.com"

    // Fetch all pending entries belonging to the requested period(s)
    let pendingDocs = []
    for (const period of reportPeriods) {
        const snap = await db
            .collection("adminReports")
            .where("status", "==", "pending")
            .where("reportPeriod", "==", period)
            .get()
        for (const doc of snap.docs) pendingDocs.push(doc)
    }

    if (pendingDocs.length === 0) {
        console.log(`sendAdminReport(${periodLabel}): No pending logs to report.`)
        return
    }

    const jobAlerts = []
    const digestAlerts = []
    const docsToDelete = []

    for (const doc of pendingDocs) {
        const data = doc.data()
        if (data.type === "job_alert") jobAlerts.push(data)
        if (data.type === "digest_alert") digestAlerts.push(data)
        docsToDelete.push(doc.ref)
    }

    const htmlContent = buildAdminReportHTML(periodLabel, jobAlerts, digestAlerts)

    let emailSentSuccessfully = false
    try {
        await sendEmail({ to: ADMIN_TARGET_EMAIL, subject: emailSubject, html: htmlContent })
        emailSentSuccessfully = true
        console.log(`Successfully sent ${periodLabel} admin report to ${ADMIN_TARGET_EMAIL}.`)
    } catch (error) {
        console.error(`Failed to send ${periodLabel} admin email:`, error.message)
    }

    if (emailSentSuccessfully) {
        let batch = db.batch()
        let opCount = 0
        const BATCH_LIMIT = 400

        for (const ref of docsToDelete) {
            batch.delete(ref)
            opCount++
            if (opCount === BATCH_LIMIT) {
                await batch.commit()
                batch = db.batch()
                opCount = 0
            }
        }
        if (opCount > 0) await batch.commit()
        console.log(`${periodLabel} admin report: wiped ${docsToDelete.length} pending log(s).`)
    }
}

// ─── Scheduled exports ────────────────────────────────────────────────────────

/**
 * Daily Admin Report — every day at 22:00 Helsinki time.
 * Covers: all job_alert entries (reportPeriod="daily") + daily digest summaries.
 */
exports.sendDailyAdminReport = onSchedule(
    {
        schedule: "0 22 * * *",
        timeZone: "Europe/Helsinki",
        region: "europe-west1",
        secrets: [GMAIL_USER, GMAIL_APP_PASSWORD],
    },
    async () => {
        const db = getFirestore()
        await sendAdminReport(
            db,
            "Daily",
            ["daily"],
            "Daily System Report — findjobsinfinland.fi"
        )
    }
)

/**
 * Weekly Admin Report — every Sunday at 22:00 Helsinki time.
 * Covers: weekly digest summaries (reportPeriod="weekly").
 */
exports.sendWeeklyAdminReport = onSchedule(
    {
        schedule: "0 22 * * 0",   // Sunday = 0
        timeZone: "Europe/Helsinki",
        region: "europe-west1",
        secrets: [GMAIL_USER, GMAIL_APP_PASSWORD],
    },
    async () => {
        const db = getFirestore()
        await sendAdminReport(
            db,
            "Weekly",
            ["weekly"],
            "Weekly System Report — findjobsinfinland.fi"
        )
    }
)

/**
 * Monthly Admin Report — last day of every month at 22:00 Helsinki time.
 * Cron "0 22 28-31 * *" fires on the 28th–31st; we check inside whether
 * tomorrow is the 1st (= today is the last day of the month).
 * Covers: monthly digest summaries (reportPeriod="monthly").
 */
exports.sendMonthlyAdminReport = onSchedule(
    {
        schedule: "0 22 28-31 * *",
        timeZone: "Europe/Helsinki",
        region: "europe-west1",
        secrets: [GMAIL_USER, GMAIL_APP_PASSWORD],
    },
    async () => {
        // Only run on the actual last day of the current month
        const now = new Date()
        const tomorrow = new Date(now.getFullYear(), now.getMonth(), now.getDate() + 1)
        const isLastDay = tomorrow.getDate() === 1

        if (!isLastDay) {
            console.log("sendMonthlyAdminReport: Not the last day of the month — skipping.")
            return
        }

        const db = getFirestore()
        await sendAdminReport(
            db,
            "Monthly",
            ["monthly"],
            "Monthly System Report — findjobsinfinland.fi"
        )
    }
)