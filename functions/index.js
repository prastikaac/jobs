const { onDocumentCreated } = require("firebase-functions/v2/firestore")
const { setGlobalOptions } = require("firebase-functions/v2")
const { initializeApp } = require("firebase-admin/app")
const { getFirestore } = require("firebase-admin/firestore")
const { getMessaging } = require("firebase-admin/messaging")
const { Resend } = require("resend")

setGlobalOptions({ region: "europe-north1" })
initializeApp()
const resend = new Resend("re_PWnJNjtv_AuZB3YUcLbRgAqDShh4iCej4")

exports.sendJobAlertEmails = onDocumentCreated("jobs/{jobId}", async (event) => {
    const jobData = event.data.data()
    const jobCategory = jobData.jobCategory
    const jobLocation = jobData.jobLocation
    const db = getFirestore()
    const messaging = getMessaging()

    // Define the location mapping for full display names
    const locationMap = {
        Helsinki: "Helsinki, Uusimaa, Finland",
        Espoo: "Espoo, Uusimaa, Finland",
        Vantaa: "Vantaa, Uusimaa, Finland",
        Kauniainen: "Kauniainen, Uusimaa, Finland",
        Järvenpää: "Järvenpää, Uusimaa, Finland",
        Kerava: "Kerava, Uusimaa, Finland",
        Tuusula: "Tuusula, Uusimaa, Finland",
        Sipoo: "Sipoo, Uusimaa, Finland",
        Kirkkonummi: "Kirkkonummi, Uusimaa, Finland",
        Lohja: "Lohja, Uusimaa, Finland",
        Nurmijärvi: "Nurmijärvi, Uusimaa, Finland",
        Hyvinkää: "Hyvinkää, Uusimaa, Finland",
        Inkoo: "Inkoo, Uusimaa, Finland",
        Pasila: "Pasila, Uusimaa, Finland",
        Malmi: "Malmi, Uusimaa, Finland",
        Tikkurila: "Tikkurila, Uusimaa, Finland",
        Leppävaara: "Leppävaara, Uusimaa, Finland",
        Matinkylä: "Matinkylä, Uusimaa, Finland",
        Myyrmäki: "Myyrmäki, Uusimaa, Finland",
        Kamppi: "Kamppi, Uusimaa, Finland",
        Kallio: "Kallio, Uusimaa, Finland",
        Tapiola: "Tapiola, Uusimaa, Finland",
        Itäkeskus: "Itäkeskus, Uusimaa, Finland",
        Lauttasaari: "Lauttasaari, Uusimaa, Finland",
        Tampere: "Tampere, Pirkanmaa, Finland",
        Turku: "Turku, Southwest Finland",
        Oulu: "Oulu, North Ostrobothnia, Finland",
        Jyväskylä: "Jyväskylä, Central Finland",
        Kuopio: "Kuopio, Northern Savonia, Finland",
        Lahti: "Lahti, Päijänne Tavastia, Finland",
        Vaasa: "Vaasa, Ostrobothnia, Finland",
        Seinäjoki: "Seinäjoki, South Ostrobothnia, Finland",
        Rovaniemi: "Rovaniemi, Lapland, Finland",
        Kotka: "Kotka, Kymenlaakso, Finland",
        Lappeenranta: "Lappeenranta, South Karelia, Finland",
        Pori: "Pori, Satakunta, Finland",
        Kokkola: "Kokkola, Central Ostrobothnia, Finland",
        Joensuu: "Joensuu, North Karelia, Finland",
    }

    // Helper function to get the formatted location string
    const getFormattedLocation = (location) => {
        if (!location) return "Finland"
        // Normalize the input location (e.g., "vaasa" -> "Vaasa") to match map keys
        const normalizedLocation = location.charAt(0).toUpperCase() + location.slice(1).toLowerCase()
        return locationMap[normalizedLocation] || `${normalizedLocation}, Finland` // Fallback if not found in map
    }

    const formattedJobLocation = getFormattedLocation(jobLocation)

    const usersSnapshot = await db.collection("users").get()
    const matchedEmails = []
    const pushPromises = []

    usersSnapshot.forEach((doc) => {
        const user = doc.data()
        const hasCategory = user.jobCategory?.includes(jobCategory)
        // Keep jobLocation as is for matching user preferences, as it might be just the city name
        const hasLocation = user.jobLocation?.includes(jobLocation)
        const fcmTokens = user.fcmTokens || []
        const jobSubscription = user.jobSubscription || {}
        const emailNotificationEnabled = jobSubscription.emailNotification ?? true
        const pushNotificationEnabled = jobSubscription.pushNotification ?? true

        if (hasCategory && hasLocation) {
            if (emailNotificationEnabled && user.email) {
                matchedEmails.push(user.email)
            }
            if (pushNotificationEnabled) {
                fcmTokens.forEach((token) => {
                    if (!token) return
                    const message = {
                        token: token,
                        notification: {
                            title: `New ${jobData.title} Job!`,
                            body: `${jobData.description}`,
                            image: jobData.imageUrl || undefined,
                        },
                        data: {
                            jobId: event.params.jobId,
                            jobLink: jobData.jobLink || "",
                            imageUrl: jobData.imageUrl || "",
                        },
                    }
                    pushPromises.push(
                        messaging.send(message).catch(async (error) => {
                            console.error(`Error sending to token ${token}:`, error.message)
                            if (
                                error.code === "messaging/registration-token-not-registered" ||
                                error.message.includes("Requested entity was not found")
                            ) {
                                const newTokens = fcmTokens.filter((t) => t !== token)
                                await db.collection("users").doc(doc.id).update({
                                    fcmTokens: newTokens,
                                })
                                console.log(`Removed invalid token for user ${doc.id}`)
                            }
                        }),
                    )
                })
            }
        }
    })

    if (matchedEmails.length === 0 && pushPromises.length === 0) {
        console.log("No matching users for this job with notifications enabled.")
        return
    }

   const emailHTML = `
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Job Alert</title>
            <style>
                @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@400;700&display=swap');
                /* Mobile-first styles */
                body {
                    font-family: 'Poppins', sans-serif;
                    margin: 0;
                    margin-top: 20px;
                    margin-left: 5px;
                    background-color: #f4f4f4; /* Added a subtle background for the whole email */
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
                    /* Max width for email body on PC */
                    .email-container {
                    }
                    /* Font size adjustments for PC */
                    .text-base-pc { font-size: 16px !important; }
                    .text-sm-pc { font-size: 14px !important; }
                    .text-xs-pc { font-size: 13px !important; }
                }
            </style>
        </head>
        <body style="font-family: 'Poppins', sans-serif; margin: 0; margin-top: 20px; margin-left: 5px; background-color: #f4f4f4; border-radius: 12px;">
            <!-- Outer table for max-width and centering on PC -->
            <table cellpadding="0" cellspacing="0" border="0" width="100%">
                <tr>
                    <td align="center">
                        <table cellpadding="0" cellspacing="0" border="0" width="100%" class="email-container" style="max-width: 100%;">
                            <tr>
                                <td>
                                    <table cellpadding="0" cellspacing="0" border="0" width="100%" class="main-content-wrapper">
                                        <!-- Header -->
                                        <tr>
                                            <td style="background-color: #242424ff; padding: 20px; text-align: center; border-radius: 12px 12px 0 0;">
                                                <table cellpadding="0" cellspacing="0" border="0" style="margin: 0 auto;">
                                                    <tr>
                                                        <td style="vertical-align: middle;">
                                                            <img src="https://findjobsinfinland.fi/images/icon.png" alt="Findjobsinfinland Logo" style="width: 40px; height: 40px; margin-right: 10px; vertical-align: middle;">
                                                        </td>
                                                        <td style="vertical-align: middle;">
                                                            <h1 style="font-size: 23px; color: #ffffff; margin: 0; font-weight: bold;">Findjobsinfinland.fi</h1>
                                                        </td>
                                                    </tr>
                                                </table>
                                            </td>
                                        </tr>
                                        <!-- Body Content -->
                                        <tr>
                                            <td style="padding: 25px 30px;">
                                                <p style="font-size: 15px; color: #555555; line-height: 1.6; margin-bottom: 20px;">
                                                    Dear Prasiddha, <br> <br> We are excited to let you know that we have a new job opportunity that matches your job preferences.
                                                </p>
                                                <!-- Job Card -->
                                                <table cellpadding="0" cellspacing="0" border="0" width="100%" style="background-color: #ffffff; border-radius: 12px; box-shadow: 0 5px 35px rgba(0, 0, 0, .07); margin-bottom: 30px; border: 1px solid #e0e0e0;">
                                                    <!-- Job Image - FIXED & CLICKABLE -->
                                                    <tr>
                                                        <td style="padding: 20px; text-align: center; ">
                                                            <a href="${jobData.jobLink || "#"}" style="display: block; text-decoration: none;">
                                                                <img src="${jobData.imageUrl || "https://findjobsinfinland.fi/images/jobs/it-and-tech-jobs.png"}" alt="Job Image" style="width: 100%; max-width: 100%; height: auto; object-fit: contain; border-radius: 12px; display: block; cursor: pointer;">
                                                            </a>
                                                        </td>
                                                    </tr>
                                                    <!-- Job Details -->
                                                    <tr>
                                                        <td style="padding: 20px; padding-top: 5px;">
                                                            <!-- Mobile Location (Right after image, before title) -->
                                                            <div class="job-footer-mobile" style="display: none; text-align: left; margin-bottom: 15px;">
                                                                <span style="font-size: 13px; color: #666666; font-weight: bold;">
                                                                    In ${formattedJobLocation}
                                                                </span>
                                                            </div>
                                                            <h2 style="font-size: 20px; font-weight: bold; margin: 0 0 10px 0; color: #005effff;">${jobData.title}</h2>
                                                            <p class="text-base-mobile text-base-pc" style="font-size: 14px; line-height: 1.6; margin: 0 0 20px 0; color: #666666;">${jobData.description}</p>
                                                            <!-- Desktop Job Footer (Original Layout) -->
                                                            <div class="job-footer-desktop" style="display: block;">
                                                                <table cellpadding="0" cellspacing="0" border="0" width="100%">
                                                                    <tr>
                                                                        <td style="vertical-align: middle;">
                                                                            <span style="font-size: 15px; color: #005effff; font-weight: bold;">
                                                                                📍 ${formattedJobLocation}
                                                                            </span>
                                                                        </td>
                                                                        <td style="text-align: right; vertical-align: middle;">
                                                                            <a href="${jobData.jobLink || "#"}" style="background-color: #e82c2f; color: #ffffff; padding: 10px 25px; border-radius: 6px; text-decoration: none; font-weight: bold; display: inline-block;">Apply Now</a>
                                                                        </td>
                                                                    </tr>
                                                                </table>
                                                            </div>
                                                            <!-- Mobile Apply Button (Bottom of card) -->
                                                            <div class="job-footer-mobile" style="display: none; text-align: center; margin-top: 20px;">
                                                                <a href="${jobData.jobLink || "#"}" style="background-color: #e82c2f; color: #ffffff; padding: 12px 0; border-radius: 6px; text-decoration: none; font-weight: bold; display: block; width: 100%; text-align: center;">Apply Now</a>
                                                            </div>
                                                        </td>
                                                    </tr>
                                                </table>
                                                <p class="text-base-mobile text-base-pc" style="font-size: 15px; color: #555555; line-height: 1.6; margin-bottom: 20px;">
                                                    We believe this opportunity will align perfectly with your interests and professional goals. Given the nature of the role, we are confident it could be a great fit for you.<br> <br> We look forward to sharing further details with you soon and are excited about the possibility of you applying for it. Please stay tuned for more information
                                                </p>
                                                <!-- Browse More Options Section -->
                                                <div style="text-align: left; margin: 30px 0;">
                                                    <h3 style="font-size: 20px; font-weight: bold; margin: 0 0 15px 0; color: #005effff;">Want to browse more options?</h3>
                                                    <p class="text-base-mobile text-base-pc" style="font-size: 15px; color: #555555; line-height: 1.6; margin: 0 0 20px 0;">
                                                        We offer a diverse range of job openings tailored to your skills and experience. <br> <br> You may explore our other listings to find the position that best suits your professional aspirations.
                                                    </p>
                                                    <a href="https://findjobsinfinland.fi/jobs?category=${jobCategory || ""}&location=${jobLocation || ""}" style="background-color: #696969ff; color: #ffffff; padding: 12px 0; border-radius: 6px; text-decoration: none; font-weight: bold; display: block; width: 100%; text-align: center;">View Similar Job Listings</a>
                                                </div>
                                            </td>
                                        </tr>
                                        <!-- Footer -->
                                        <tr>
                                            <td style="background-color: #f5f0eb; padding: 20px; text-align: center; border-radius: 0 0 12px 12px; border-top: 1px solid #e9ecef;">
                                                <p class="text-sm-mobile text-sm-pc" style="font-size: 13px; color: #005effff; margin: 0 0 15px 0; line-height: 1.5;">
                                                    <a href="https://findjobsinfinland.fi/disclaimer" style="color: #005effff; text-decoration: none; margin: 0 5px;">Disclaimer</a>
                                                    <span style="color: #666666; margin: 0 5px;">|</span>
                                                    <a href="https://findjobsinfinland.fi/privacy-policy" style="color: #005effff; text-decoration: none; margin: 0 5px;">Privacy Policy</a>
                                                </p>
                                                <!-- Unsubscribe Text -->
                                                <p class="text-xs-mobile text-xs-pc" style="font-size: 12px; color: #888888; line-height: 1.6; margin-top: 10px; margin-bottom: 10px; text-align: center;">
                                                    If you would prefer not to receive any further job updates or notifications via email, you can easily opt out at any time by clicking on <a href="https://findjobsinfinland.fi/edit-profile#unsubscribe" style="color: #e82c2f; text-decoration: underline;">unsubscribe</a>.
                                                </p>
                                                <p class="text-xs-mobile text-xs-pc" style="font-size: 12px; color: #888888; margin: 0; line-height: 1.4;">
                                                    © 2025 · <span style="color: #28a745; font-weight: 500;">findjobsinfinland.fi</span> · All rights reserved.
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
    const emailPromises = matchedEmails.map((email) => {
        return resend.emails.send({
            from: "Find Jobs In Finland <jobs@findjobsinfinland.fi>",
            to: email,
            subject: `New Job Alert: ${jobData.title}`,
            html: emailHTML,
        })
    })

    await Promise.all(emailPromises)
    await Promise.all(pushPromises)

    // Send summary to owner
    await resend.emails.send({
        from: "Find Jobs In Finland <jobs@findjobsinfinland.fi>",
        to: "acharyaprasiddha6@gmail.com",
        subject: `✅ Job Alert Sent for ${jobData.title}`,
        html: `
            <p>Job alert for <strong>${jobData.title}</strong> has been sent to:</p>
            <ul>
                ${matchedEmails.map((email) => `<li>${email}</li>`).join("")}
            </ul>
            <p><strong>Total emails:</strong> ${matchedEmails.length}</p>
            <p><strong>Total push notifications:</strong> ${pushPromises.length}</p>
        `,
    })
    console.log(`Emails sent to: ${matchedEmails.length} users: ${matchedEmails.join(", ")}`)
    console.log(`Push notifications sent to: ${pushPromises.length} users.`)
})
