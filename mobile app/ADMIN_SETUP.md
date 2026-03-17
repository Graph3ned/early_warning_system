# How to make an account an admin

The app reads the user role from **Firebase Realtime Database** at:

```
users/<user-uid>/role
```

- Value **`"viewer"`** (or missing) → Viewer (Dashboard, Alerts, Forecasts only).
- Value **`"admin"`** → Admin (Dashboard, Alerts, Forecasts, **Metrics**, **Admin**).

## Steps to make your account admin

1. **Get your user UID**
   - Open [Firebase Console](https://console.firebase.google.com/) → your project.
   - Go to **Authentication** → **Users**.
   - Find your email and copy the **User UID** (long string like `a1b2c3d4e5...`).

2. **Set the role in the database**
   - In Firebase Console go to **Realtime Database** → **Data**.
   - Find or create the **`users`** node.
   - Under **`users`**, add or edit a child whose **key** is your **User UID** (from step 1).
   - Under that UID, add or edit a child:
     - **Key:** `role`
     - **Value:** `admin` (type: string, without quotes in the UI).

3. **Result**
   - Structure should look like:
     ```
     users
       └── <your-uid>
             └── role: "admin"
     ```
   - Sign out and sign back in (or restart the app). The **Metrics** and **Admin** tabs will appear.

## Security note

In **Realtime Database → Rules**, restrict who can read/write `users/<uid>` so only that user (or admins) can read their own `role`, and only trusted backends or admins can change it. Example (adjust to your auth):

```json
{
  "rules": {
    "users": {
      "$uid": {
        ".read": "auth != null && auth.uid == $uid",
        ".write": "auth != null"
      }
    }
  }
}
```
