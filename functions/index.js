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

function buildSingleJobEmailHTML(jobData, formattedJobLocations) {
    const jobCategory = jobData.jobCategory
    const jobLocation = jobData.jobLocation

    return `
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Job Alert</title>
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
                @media only screen and (max-width: 600px) {
                    .job-footer-desktop {
                        display: none !important;
                    }
                    .job-footer-mobile {
                        display: block !important;
                    }
                }
                @media only screen and (min-width: 601px) {
                    .job-footer-desktop {
                        display: block !important;
                    }
                    .job-footer-mobile {
                        display: none !important;
                    }
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
                                                <p style="font-size: 15px; color: #555555; line-height: 1.6; margin-bottom: 20px;">
                                                    Dear user, <br> <br> We are excited to let you know that we have a new job opportunity that matches your job preferences.
                                                </p>
                                                <table cellpadding="0" cellspacing="0" border="0" width="100%" style="background-color: #ffffff; border-radius: 12px; box-shadow: 0 5px 35px rgba(0, 0, 0, .07); margin-bottom: 30px; border: 1px solid #e0e0e0;">
                                                    <tr>
                                                        <td style="padding: 20px; text-align: center;">
                                                            <a href="${jobData.jobLink || "#"}" style="display: block; text-decoration: none;">
                                                                <img src="${jobData.imageUrl || DEFAULT_IMAGE}" alt="Job Image" style="width: 100%; max-width: 100%; height: auto; object-fit: contain; border-radius: 12px; display: block; cursor: pointer;">
                                                            </a>
                                                        </td>
                                                    </tr>
                                                    <tr>
                                                        <td style="padding: 20px; padding-top: 5px;">
                                                            <div class="job-footer-mobile" style="display: none; text-align: left; margin-bottom: 15px;">
                                                                <span style="font-size: 13px; color: #666666; font-weight: bold;">
                                                                    In ${formattedJobLocations}
                                                                </span>
                                                            </div>
                                                            <h2 style="font-size: 20px; font-weight: bold; margin: 0 0 10px 0; color: #005effff;">${escapeHtml(jobData.title)}</h2>
                                                            <p class="text-base-mobile text-base-pc" style="font-size: 14px; line-height: 1.6; margin: 0 0 20px 0; color: #666666;">${escapeHtml(jobData.description)}</p>
                                                            <div class="job-footer-desktop" style="display: block;">
                                                                <table cellpadding="0" cellspacing="0" border="0" width="100%">
                                                                    <tr>
                                                                        <td style="vertical-align: middle;">
                                                                            <span style="font-size: 15px; color: #005effff; font-weight: bold;">
                                                                               📍 ${formattedJobLocations}
                                                                            </span>
                                                                        </td>
                                                                        <td style="text-align: right; vertical-align: middle;">
                                                                            <a href="${jobData.jobLink || "#"}" style="background-color: #e82c2f; color: #ffffff; padding: 10px 25px; border-radius: 6px; text-decoration: none; font-weight: bold; display: inline-block;">Apply Now</a>
                                                                        </td>
                                                                    </tr>
                                                                </table>
                                                            </div>
                                                            <div class="job-footer-mobile" style="display: none; text-align: center; margin-top: 20px;">
                                                                <a href="${jobData.jobLink || "#"}" style="background-color: #e82c2f; color: #ffffff; padding: 12px 0; border-radius: 6px; text-decoration: none; font-weight: bold; display: block; width: 100%; text-align: center;">Apply Now</a>
                                                            </div>
                                                        </td>
                                                    </tr>
                                                </table>
                                                <p class="text-base-mobile text-base-pc" style="font-size: 15px; color: #555555; line-height: 1.6; margin-bottom: 20px;">
                                                    We believe this opportunity will align perfectly with your interests and professional goals. Given the nature of the role, we are confident it could be a great fit for you.<br> <br> We look forward to sharing further details with you soon and are excited about the possibility of you applying for it. Please stay tuned for more information
                                                </p>
                                                <div style="text-align: left; margin: 30px 0;">
                                                    <h3 style="font-size: 20px; font-weight: bold; margin: 0 0 15px 0; color: #005effff;">Want to browse more options?</h3>
                                                    <p class="text-base-mobile text-base-pc" style="font-size: 15px; color: #555555; line-height: 1.6; margin: 0 0 20px 0;">
                                                        We offer a diverse range of job openings tailored to your skills and experience. <br> <br> You may explore our other listings to find the position that best suits your professional aspirations.
                                                    </p>
                                                    <a href="${SITE_URL}/jobs?category=${Array.isArray(jobCategory) ? jobCategory[0] || "" : jobCategory || ""}&location=${Array.isArray(jobLocation) ? jobLocation[0] || "" : jobLocation || ""}" style="background-color: #696969ff; color: #ffffff; padding: 12px 0; border-radius: 6px; text-decoration: none; font-weight: bold; display: block; width: 100%; text-align: center;">View Similar Job Listings</a>
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
        </body>
        </html>`
}

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
        </body>
        </html>
    `
}

async function sendDigestAlerts(frequency) {
    const db = getFirestore()
    const usersSnapshot = await db.collection("users").where("jobAlertFrequency", "==", frequency).get()

    let usersProcessed = 0
    let totalEmailsSent = 0
    let totalPushNotificationsSent = 0
    let totalQueuedJobsSent = 0
    let totalExpiredQueuedJobsRemoved = 0

    for (const userDoc of usersSnapshot.docs) {
        const user = userDoc.data()
        const userId = userDoc.id

        const jobSubscription = user.jobSubscription || {}
        const emailNotificationEnabled = jobSubscription.emailNotification ?? true
        const pushNotificationEnabled = jobSubscription.pushNotification ?? true
        const fcmTokens = Array.isArray(user.fcmTokens) ? user.fcmTokens : []

        const alertsSnapshot = await db
            .collection("users")
            .doc(userId)
            .collection("pendingAlerts")
            .where("frequency", "==", frequency)
            .get()

        if (alertsSnapshot.empty) {
            continue
        }

        const validAlertDocs = []
        const expiredAlertDocs = []

        for (const alertDoc of alertsSnapshot.docs) {
            const alertData = alertDoc.data()

            if (isExpiredTimestamp(alertData.expiresAt)) {
                expiredAlertDocs.push(alertDoc)
            } else {
                validAlertDocs.push(alertDoc)
            }
        }

        // Remove expired queued jobs so they are never sent later
        if (expiredAlertDocs.length > 0) {
            let cleanupBatch = db.batch()
            let cleanupCount = 0
            const BATCH_LIMIT = 400

            for (const expiredDoc of expiredAlertDocs) {
                cleanupBatch.delete(expiredDoc.ref)
                cleanupCount++
                totalExpiredQueuedJobsRemoved++

                if (cleanupCount === BATCH_LIMIT) {
                    await cleanupBatch.commit()
                    cleanupBatch = db.batch()
                    cleanupCount = 0
                }
            }

            if (cleanupCount > 0) {
                await cleanupBatch.commit()
            }
        }

        if (validAlertDocs.length === 0) {
            continue
        }

        const jobs = validAlertDocs.map((doc) => doc.data())
        usersProcessed++
        totalQueuedJobsSent += jobs.length

        let emailSuccess = false
        let pushSuccessCountForUser = 0

        if (emailNotificationEnabled && user.email) {
            try {
                await sendEmail({
                    to: user.email,
                    subject: `${frequency.charAt(0).toUpperCase() + frequency.slice(1)} Job Alerts (${jobs.length})`,
                    html: buildDigestEmailHTML(frequency, jobs),
                })
                emailSuccess = true
                totalEmailsSent++
            } catch (error) {
                console.error(`Error sending ${frequency} email to ${user.email}:`, error.message)
            }
        }

        if (pushNotificationEnabled && fcmTokens.length > 0) {
            // Snapshot the token list so that cleanup of invalid tokens during
            // iteration doesn't affect the loop (fixes stale-array bug)
            const tokenSnapshot = [...fcmTokens]
            for (const token of tokenSnapshot) {
                if (!token) continue

                const periodLabel = { daily: "today's", weekly: "this week's", monthly: "this month's" }[frequency] ?? frequency

                const success = await sendPushToTokenAndCleanup({
                    token,
                    db,
                    userDocId: userId,
                    fcmTokens,
                    message: {
                        token,
                        notification: {
                            title: "🔔 New Job Alerts",
                            body: `Here are your ${periodLabel} job alerts — ${jobs.length} new ${jobs.length === 1 ? "job" : "jobs"} waiting!`,
                        },
                        data: {
                            type: `${frequency}_digest`,
                            jobsCount: String(jobs.length),
                            url: `${SITE_URL}/newjobs?period=${frequency}`,
                        },
                    },
                })

                if (success) {
                    pushSuccessCountForUser++
                    totalPushNotificationsSent++
                }
            }
        }

        // Delete queued alerts only if delivery succeeded
        const hadAnyDeliveryChannelEnabled =
            (emailNotificationEnabled && !!user.email) ||
            (pushNotificationEnabled && fcmTokens.length > 0)

        const shouldDeleteSentAlerts =
            (emailNotificationEnabled && !!user.email && emailSuccess) ||
            (pushNotificationEnabled && fcmTokens.length > 0 && pushSuccessCountForUser > 0) ||
            !hadAnyDeliveryChannelEnabled

        if (shouldDeleteSentAlerts) {
            let batch = db.batch()
            let opCount = 0
            const BATCH_LIMIT = 400

            for (const alertDoc of validAlertDocs) {
                batch.delete(alertDoc.ref)
                opCount++

                if (opCount === BATCH_LIMIT) {
                    await batch.commit()
                    batch = db.batch()
                    opCount = 0
                }
            }

            if (opCount > 0) {
                await batch.commit()
            }
        } else {
            console.log(`Keeping ${validAlertDocs.length} queued ${frequency} alerts for user ${userId} because delivery failed.`)
        }
    }

    try {
        await db.collection("adminReports").add({
            type: "digest_alert",
            frequency,
            usersProcessed,
            totalQueuedJobsSent,
            totalExpiredQueuedJobsRemoved,
            totalEmailsSent,
            totalPushNotificationsSent,
            status: "pending",
            createdAt: Timestamp.now()
        })
    } catch (error) {
        console.error(`Failed to save ${frequency} admin report to Firestore:`, error.message)
    }

    console.log(
        `${frequency} alerts sent. Users processed: ${usersProcessed}, Valid jobs sent: ${totalQueuedJobsSent}, Expired queued removed: ${totalExpiredQueuedJobsRemoved}, Emails: ${totalEmailsSent}, Push: ${totalPushNotificationsSent}`,
    )
}

exports.sendJobAlertEmails = onDocumentCreated(
    {
        document: "jobs/{jobId}",
        secrets: [GMAIL_USER, GMAIL_APP_PASSWORD],
    },
    async (event) => {
    const jobData = event.data.data()
    const jobCategory = jobData.jobCategory
    const jobLocation = jobData.jobLocation
    const db = getFirestore()
    const messaging = getMessaging()

    // Safety check: skip only if explicitly set AND already expired
    if (jobData.expiresAt && isExpiredTimestamp(jobData.expiresAt)) {
        console.log(`Skipping expired job alert for ${event.params.jobId}`)
        return
    }

    const formattedJobLocations = getFormattedLocationsString(jobLocation)

    const usersSnapshot = await db.collection("users").get()
    const matchedEmails = []
    // pushPromises removed — instant push now goes through notifQueue
    let queuedUsersCount = 0
    let instantMatchedUsersCount = 0
    let instantPushQueuedCount = 0  // tracks how many push entries were queued

    // Make sure jobData values are always arrays and lowercased for case-insensitive matching
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

        // Per-channel frequencies with legacy fallback
        const legacyFreq = isValidFrequency(user.jobAlertFrequency) ? user.jobAlertFrequency : "instantly"
        const emailAlertFrequency = isValidEmailFrequency(user.emailAlertFrequency)
            ? user.emailAlertFrequency
            : isValidEmailFrequency(legacyFreq) ? legacyFreq : "daily"
        const pushAlertFrequency = isValidFrequency(user.pushAlertFrequency)
            ? user.pushAlertFrequency
            : legacyFreq

        // Match logic
        const hasCategory =
            userCategories.length === 0 || jobCategories.length === 0 || jobCategories.some((cat) => userCategories.includes(cat))

        const hasLocation =
            userLocations.length === 0 || jobLocations.length === 0 || jobLocations.some((loc) => userLocations.includes(loc))

        const hasLanguage =
            userLanguages.length === 0 || jobLanguages.length === 0 || jobLanguages.some((lang) => userLanguages.includes(lang))

        const hasTime =
            userTimes.length === 0 || jobTimes.length === 0 || jobTimes.some((time) => userTimes.includes(time))

        const hasType =
            userTypes.length === 0 || jobTypes.length === 0 || jobTypes.some((type) => userTypes.includes(type))

        const isMatched = hasCategory && hasLocation && hasLanguage && hasTime && hasType

        if (!isMatched) {
            continue
        }

        if (pushAlertFrequency === "instantly") {
            instantMatchedUsersCount++

            // Email is still sent immediately
            if (emailNotificationEnabled && user.email) {
                matchedEmails.push(user.email)
            }

            // Push is now staggered via notifQueue (5 min × position index)
            if (pushNotificationEnabled && fcmTokens.length > 0) {
                for (const token of fcmTokens) {
                    if (!token) continue

                    // Each additional user in this batch gets +5 min on top of the previous
                    const delayMs = instantPushQueuedCount * 5 * 60 * 1000
                    const scheduledAt = new Date(Date.now() + delayMs)

                    await db.collection("notifQueue").add({
                        userId: doc.id,
                        token: token,
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
            }
        } else if (["daily", "weekly", "monthly"].includes(pushAlertFrequency) || ["daily", "weekly", "monthly"].includes(emailAlertFrequency)) {
            queuedUsersCount++

            // Queue for email digest if email channel is non-instant
            if (emailNotificationEnabled && user.email && ["daily", "weekly", "monthly"].includes(emailAlertFrequency)) {
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
                        frequency: emailAlertFrequency,
                        channel: "email",
                        createdAt: Timestamp.now(),
                    }, { merge: true })
            }

            // Queue for push digest if push channel is non-instant
            if (pushNotificationEnabled && fcmTokens.length > 0 && ["daily", "weekly", "monthly"].includes(pushAlertFrequency)) {
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
            }
        }
    }

    const emailHTML = buildSingleJobEmailHTML(jobData, formattedJobLocations)

    if (matchedEmails.length > 0) {
        const emailPromises = matchedEmails.map((email) => {
            return sendEmail({
                to: email,
                subject: jobData.title || "New Job Alert",
                html: emailHTML,
            })
        })

        try {
            await Promise.all(emailPromises)
        } catch (error) {
            console.error("Error sending one or more instant emails:", error.message)
        }
    }

    try {
        await db.collection("adminReports").add({
            type: "job_alert",
            jobTitle: jobData.title || event.params.jobId,
            instantMatchedUsersCount,
            queuedUsersCount,
            emailsSentCount: matchedEmails.length,
            pushQueuedCount: instantPushQueuedCount,
            recipients: matchedEmails,
            status: "pending",
            createdAt: Timestamp.now()
        })
    } catch (error) {
        console.error("Failed to save admin report to Firestore:", error.message)
    }

    console.log(`Instant emails sent to: ${matchedEmails.length} users: ${matchedEmails.join(", ")}`)
    console.log(`Instant push notifications queued (staggered): ${instantPushQueuedCount}`)
    console.log(`Queued users for digest alerts: ${queuedUsersCount}`)
})

exports.sendDailyAlerts = onSchedule(
    {
        schedule: "0 8 * * *",
        timeZone: "Europe/Helsinki",
        region: "europe-west1",
        secrets: [GMAIL_USER, GMAIL_APP_PASSWORD],
    },
    async () => {
        await sendDigestAlerts("daily")
    },
)

exports.sendWeeklyAlerts = onSchedule(
    {
        schedule: "0 8 * * 1",
        timeZone: "Europe/Helsinki",
        region: "europe-west1",
        secrets: [GMAIL_USER, GMAIL_APP_PASSWORD],
    },
    async () => {
        await sendDigestAlerts("weekly")
    },
)

exports.sendMonthlyAlerts = onSchedule(
    {
        schedule: "0 8 1 * *",
        timeZone: "Europe/Helsinki",
        region: "europe-west1",
        secrets: [GMAIL_USER, GMAIL_APP_PASSWORD],
    },
    async () => {
        await sendDigestAlerts("monthly")
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

/**
 * Send the consolidated Daily Admin Report at 10 PM.
 * Sweeps 'adminReports' collection, formats a master email, and clears the pending logs.
 */
exports.sendDailyAdminReport = onSchedule(
    {
        schedule: "0 22 * * *", // 22:00 (10 PM) Europe/Helsinki time
        timeZone: "Europe/Helsinki",
        region: "europe-west1",
        secrets: [GMAIL_USER, GMAIL_APP_PASSWORD],
    },
    async () => {
        const db = getFirestore()
        const ADMIN_TARGET_EMAIL = "acharyaprasiddha6@gmail.com"

        const snapshot = await db.collection("adminReports").where("status", "==", "pending").get()

        if (snapshot.empty) {
            console.log("sendDailyAdminReport: No pending admin logs to report today.")
            return
        }

        const jobAlerts = []
        const digestAlerts = []
        const docsToDelete = []

        for (const doc of snapshot.docs) {
            const data = doc.data()
            if (data.type === "job_alert") {
                jobAlerts.push(data)
            } else if (data.type === "digest_alert") {
                digestAlerts.push(data)
            }
            docsToDelete.push(doc.ref)
        }

        let htmlContent = `<h2>Daily Job Alerts Report</h2><hr/>`

        if (jobAlerts.length > 0) {
            jobAlerts.forEach((job) => {
                const recipientsList = (job.recipients || []).length > 0 
                  ? job.recipients.join("<br/>") 
                  : "None"

                htmlContent += `
                    <div style="margin-bottom: 25px; border: 1px solid #ddd; padding: 15px; border-radius: 8px;">
                        <h3 style="margin-top: 0;">Job: ${escapeHtml(job.jobTitle)}</h3>
                        <p><strong>Instant matched users:</strong> ${job.instantMatchedUsersCount}</p>
                        <p><strong>Queued users (daily/weekly/monthly):</strong> ${job.queuedUsersCount}</p>
                        <p><strong>Total instant emails sent:</strong> ${job.emailsSentCount}</p>
                        <p><strong>Instant push notifications queued (staggered):</strong> ${job.pushQueuedCount}</p>
                        <p><strong>Instant email recipients:</strong></p>
                        <div style="background-color: #f9f9f9; padding: 10px; border-radius: 4px; font-family: monospace; font-size: 12px;">
                            ${recipientsList}
                        </div>
                    </div>
                `
            })
        } else {
            htmlContent += `<p>No job alerts triggered today.</p>`
        }

        if (digestAlerts.length > 0) {
            htmlContent += `<h2>Digest Batch Summaries</h2><hr/>`
            digestAlerts.forEach((digest) => {
                htmlContent += `
                    <div style="margin-bottom: 20px; border: 1px solid #ddd; padding: 15px; border-radius: 8px;">
                        <p><strong>Frequency:</strong> ${escapeHtml(digest.frequency)}</p>
                        <p><strong>Users processed:</strong> ${digest.usersProcessed}</p>
                        <p><strong>Total valid queued jobs sent:</strong> ${digest.totalQueuedJobsSent}</p>
                        <p><strong>Total expired queued jobs removed:</strong> ${digest.totalExpiredQueuedJobsRemoved}</p>
                        <p><strong>Total emails sent:</strong> ${digest.totalEmailsSent}</p>
                        <p><strong>Total push notifications sent:</strong> ${digest.totalPushNotificationsSent}</p>
                    </div>
                `
            })
        }

        htmlContent += `<p style="color: #888; font-size: 12px; margin-top: 30px;">Report automatically generated by findjobsinfinland.fi 🇫🇮</p>`

        let emailSentSuccessfully = false
        try {
            await sendEmail({
                to: ADMIN_TARGET_EMAIL,
                subject: `Daily System Report — findjobsinfinland.fi`,
                html: htmlContent,
            })
            emailSentSuccessfully = true
            console.log(`Successfully sent daily admin report to ${ADMIN_TARGET_EMAIL}.`)
        } catch (error) {
            console.error("Failed to send daily admin email:", error.message)
        }

        if (emailSentSuccessfully) {
            let batch = db.batch()
            let opCount = 0
            let passCount = 0
            const BATCH_LIMIT = 400

            for (const ref of docsToDelete) {
                batch.delete(ref)
                opCount++

                if (opCount === BATCH_LIMIT) {
                    await batch.commit()
                    batch = db.batch()
                    opCount = 0
                    passCount++
                }
            }

            if (opCount > 0) {
                await batch.commit()
            }
            console.log("Successfully wiped pending admin logs.")
        }
    }
)