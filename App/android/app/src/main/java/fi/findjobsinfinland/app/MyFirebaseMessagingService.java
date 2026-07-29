package fi.findjobsinfinland.app;

import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.content.Context;
import android.content.Intent;
import android.os.Build;
import android.util.Log;

import androidx.core.app.NotificationCompat;

import com.google.firebase.Timestamp;
import com.google.firebase.firestore.FirebaseFirestore;
import com.google.firebase.firestore.SetOptions;
import com.google.firebase.messaging.FirebaseMessagingService;
import com.google.firebase.messaging.RemoteMessage;

import java.util.HashMap;
import java.util.Map;

/**
 * Handles two FCM events:
 *
 *  1. onNewToken -- called when the device gets a fresh FCM registration token.
 *     Saves the token to Firestore "appDevices/{token}" so the Cloud Function
 *     can reach this device for the daily morning notification.
 *
 *  2. onMessageReceived -- called when a notification arrives while the app is
 *     in the FOREGROUND (FCM delivers to system tray automatically when app is
 *     in background / killed). We manually build and show the notification here
 *     so it always appears regardless of app state.
 */
public class MyFirebaseMessagingService extends FirebaseMessagingService {

    private static final String TAG             = "FCMService";
    private static final String CHANNEL_ID      = "daily_morning";
    private static final String CHANNEL_NAME    = "Daily Morning Alerts";
    private static final String CHANNEL_DESC    = "Sends a daily reminder to open and test the app.";
    private static final int    NOTIFICATION_ID = 1001;

    // -------------------------------------------------------------------------
    //  Token refresh
    // -------------------------------------------------------------------------

    /**
     * Called by FCM whenever a new registration token is generated
     * (first install, app data cleared, token rotated, etc.).
     * Stores it in Firestore so the Cloud Function can send to this device.
     * Document ID = the token itself -> natural deduplication.
     */
    @Override
    public void onNewToken(String token) {
        super.onNewToken(token);
        Log.d(TAG, "New FCM token: " + token);
        saveTokenToFirestore(token);
    }

    private void saveTokenToFirestore(String token) {
        Map<String, Object> data = new HashMap<>();
        data.put("fcmToken",     token);
        data.put("platform",     "android");
        data.put("registeredAt", Timestamp.now());
        data.put("lastSeen",     Timestamp.now());

        FirebaseFirestore.getInstance()
            .collection("appDevices")
            .document(token)
            .set(data, SetOptions.merge())
            .addOnSuccessListener(aVoid -> Log.d(TAG, "Token saved to Firestore."))
            .addOnFailureListener(e    -> Log.e(TAG, "Failed to save token: " + e.getMessage()));
    }

    // -------------------------------------------------------------------------
    //  Foreground message handling
    // -------------------------------------------------------------------------

    /**
     * Called when the app is in the FOREGROUND and a notification arrives.
     * FCM handles background/killed cases automatically via the system tray.
     * Tapping opens MainActivity.
     */
    @Override
    public void onMessageReceived(RemoteMessage remoteMessage) {
        super.onMessageReceived(remoteMessage);
        Log.d(TAG, "Message received from: " + remoteMessage.getFrom());

        String title = "Good Morning! Open the App for Testing! \u2600\uFE0F";
        String body  = "Tap here to open the JobsInFinland app. Your daily check-in helps us improve the experience for everyone!";

        if (remoteMessage.getNotification() != null) {
            if (remoteMessage.getNotification().getTitle() != null) {
                title = remoteMessage.getNotification().getTitle();
            }
            if (remoteMessage.getNotification().getBody() != null) {
                body = remoteMessage.getNotification().getBody();
            }
        }

        showNotification(title, body);
    }

    // -------------------------------------------------------------------------
    //  Helpers
    // -------------------------------------------------------------------------

    private void showNotification(String title, String body) {
        Intent intent = new Intent(this, MainActivity.class);
        intent.addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP | Intent.FLAG_ACTIVITY_SINGLE_TOP);

        int flags = PendingIntent.FLAG_ONE_SHOT | PendingIntent.FLAG_IMMUTABLE;
        PendingIntent pendingIntent = PendingIntent.getActivity(this, 0, intent, flags);

        createNotificationChannel();

        NotificationCompat.Builder builder = new NotificationCompat.Builder(this, CHANNEL_ID)
            .setSmallIcon(R.mipmap.ic_launcher)
            .setContentTitle(title)
            .setContentText(body)
            .setStyle(new NotificationCompat.BigTextStyle().bigText(body))
            .setAutoCancel(true)
            .setPriority(NotificationCompat.PRIORITY_HIGH)
            .setContentIntent(pendingIntent);

        NotificationManager nm =
            (NotificationManager) getSystemService(Context.NOTIFICATION_SERVICE);
        if (nm != null) {
            nm.notify(NOTIFICATION_ID, builder.build());
        }
    }

    /** Creates the notification channel (Android 8+ / API 26+). Safe to call repeatedly. */
    private void createNotificationChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            NotificationChannel channel = new NotificationChannel(
                CHANNEL_ID, CHANNEL_NAME, NotificationManager.IMPORTANCE_HIGH
            );
            channel.setDescription(CHANNEL_DESC);
            channel.enableLights(true);
            channel.enableVibration(true);
            // Use the default system notification sound
            channel.setSound(
                android.provider.Settings.System.DEFAULT_NOTIFICATION_URI,
                new android.media.AudioAttributes.Builder()
                    .setUsage(android.media.AudioAttributes.USAGE_NOTIFICATION)
                    .setContentType(android.media.AudioAttributes.CONTENT_TYPE_SONIFICATION)
                    .build()
            );

            NotificationManager nm =
                (NotificationManager) getSystemService(Context.NOTIFICATION_SERVICE);
            if (nm != null) {
                nm.createNotificationChannel(channel);
            }
        }
    }
}