# Firebase setup for Early Warning System

1. **Create a Firebase project** at [Firebase Console](https://console.firebase.google.com/).

2. **Add an Android app** with package name `com.example.earlywarningsystem`. Download `google-services.json` and replace the placeholder file at `app/google-services.json`.

3. **Enable Email/Password** sign-in: Authentication → Sign-in method → Enable Email/Password.

4. **Create Realtime Database** (if not already created). Use your project’s default URL (e.g. `https://<project-id>-default-rtdb.<region>.firebasedatabase.app/`). Set rules as needed for your app (e.g. auth-only read/write for `sensor_data`, `forecast_status`, `forecast`, `forecast_metrics`, `recipients`, and `users`).

5. **User roles**: Store each user’s role under `users/<uid>/role` with value `"viewer"` or `"admin"`. New users get `"viewer"` by default on registration.

6. **Data paths** (must match the app):
   - `sensor_data/<timestamp>` – latest sensor readings
   - `forecast_status` – system, reason, latest_run_id, last_forecast_at
   - `forecast/<run_id>/<parameter>/<date>/<time>` – predicted, lower, upper
   - `forecast_metrics/<run_id>/<parameter>` – MAE, RMSE
   - `recipients/<id>` – name, phone, active
