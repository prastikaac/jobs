
// Every time do : firebase deploy --only functions : after editing this file

const { onDocumentCreated } = require('firebase-functions/v2/firestore');
const { setGlobalOptions } = require('firebase-functions/v2');
const { initializeApp } = require('firebase-admin/app');
const { getFirestore } = require('firebase-admin/firestore');
const { getMessaging } = require('firebase-admin/messaging');
const { Resend } = require('resend');

setGlobalOptions({ region: 'europe-north1' });

initializeApp();

const resend = new Resend('re_PWnJNjtv_AuZB3YUcLbRgAqDShh4iCej4');

exports.sendJobAlertEmails = onDocumentCreated('jobs/{jobId}', async (event) => {
  const jobData = event.data.data();

  const jobCategory = jobData.jobCategory;
  const jobLocation = jobData.jobLocation;

  const db = getFirestore();
  const messaging = getMessaging();

  const usersSnapshot = await db.collection('users').get();

  const matchedEmails = [];
  const pushPromises = [];

  usersSnapshot.forEach((doc) => {
    const user = doc.data();
    const hasCategory = user.jobCategory?.includes(jobCategory);
    const hasLocation = user.jobLocation?.includes(jobLocation);
    const fcmToken = user.fcmToken;

    if (hasCategory && hasLocation) {
      if (user.email) matchedEmails.push(user.email);

      // push notification
      if (fcmToken) {
        const message = {
          token: fcmToken,
          notification: {
            title: `🚀 New ${jobCategory} Job!`,
            body: `${jobData.title} in ${jobLocation}`,
            imageUrl: jobData.imageUrl || undefined
          },
          data: {
            jobId: event.params.jobId,
          },
        };
        pushPromises.push(messaging.send(message));
      }
    }
  });

  if (matchedEmails.length === 0) {
    console.log("No matching users for this job.");
    return;
  }

  // Send job alert email
  const emailPromises = matchedEmails.map((email) => {
    return resend.emails.send({
      from: 'Find Jobs In Finland <jobs@findjobsinfinland.fi>',
      to: email,
      subject: `🚀 New Job Alert: ${jobData.title}`,
      html: `
        <h2>${jobData.title}</h2>
        <p>${jobData.description}</p>
        <p><strong>Category:</strong> ${jobCategory}</p>
        <p><strong>Location:</strong> ${jobLocation}</p>
        <img src="${jobData.imageUrl}" alt="Job Image" width="400"/>
        <p><a href="https://findjobsinfinland.fi">Apply Now →</a></p>
      `,
    });
  });

  await Promise.all(emailPromises);
  await Promise.all(pushPromises);

  // Send summary to owner
  await resend.emails.send({
    from: 'Find Jobs In Finland <jobs@findjobsinfinland.fi>',
    to: 'acharyaprasiddha6@gmail.com',
    subject: `✅ Job Alert Sent for ${jobData.title}`,
    html: `
      <p>Job alert for <strong>${jobData.title}</strong> has been sent to:</p>
      <ul>
        ${matchedEmails.map((email) => `<li>${email}</li>`).join('')}
      </ul>
      <p><strong>Total emails:</strong> ${matchedEmails.length}</p>
      <p><strong>Total push notifications:</strong> ${pushPromises.length}</p>
    `,
  });

  console.log(`Emails sent to: ${matchedEmails.join(", ")}`);
  console.log(`Push notifications sent: ${pushPromises.length}`);
});



// Every time do : firebase deploy --only functions : after editing this file
