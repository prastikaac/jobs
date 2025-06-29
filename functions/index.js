
// Every time do : firebase deploy --only functions after editing this file

const {onDocumentCreated} = require('firebase-functions/v2/firestore');
const {setGlobalOptions} = require('firebase-functions/v2');
const {initializeApp} = require('firebase-admin/app');
const {getFirestore} = require('firebase-admin/firestore');
const { Resend } = require('resend');

// Set region to match Firestore (Europe North)
setGlobalOptions({region: 'europe-north1'});

initializeApp();

const resend = new Resend('re_PWnJNjtv_AuZB3YUcLbRgAqDShh4iCej4');

exports.sendJobAlertEmails = onDocumentCreated('jobs/{jobId}', async (event) => {
  const jobData = event.data.data();

  const jobCategory = jobData.jobCategory;
  const jobLocation = jobData.jobLocation;

  const db = getFirestore();
  const usersSnapshot = await db.collection('users').get();

  const matchedEmails = [];

  usersSnapshot.forEach((doc) => {
    const user = doc.data();

    const hasCategory = user.jobCategory?.includes(jobCategory);
    const hasLocation = user.jobLocation?.includes(jobLocation);

    if (hasCategory && hasLocation) {
      matchedEmails.push(user.email);
    }
  });

  if (matchedEmails.length === 0) {
    console.log("No matching users for this job.");
    return;
  }

  // Send job alert email to matched users
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

  // Send summary to owner (you)
  await resend.emails.send({
    from: 'Find Jobs In Finland <jobs@findjobsinfinland.fi>',
    to: 'acharyaprasiddha6@gmail.com',
    subject: `✅ Job Alert Sent for ${jobData.title}`,
    html: `
      <p>Job alert for <strong>${jobData.title}</strong> has been sent to:</p>
      <ul>
        ${matchedEmails.map((email) => `<li>${email}</li>`).join('')}
      </ul>
      <p><strong>Total:</strong> ${matchedEmails.length} users.</p>
    `,
  });

  console.log(`Emails sent to: ${matchedEmails.join(", ")}`);
});


// Every time do : firebase deploy --only functions after editing this file
