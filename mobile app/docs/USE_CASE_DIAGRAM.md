# Early Warning System (EWS) – Use Case Diagram

## Actors

| Actor    | Description |
|----------|-------------|
| **Guest**  | Not logged in; can only reach login/register. |
| **Viewer** | Logged-in user with role `viewer`. Can view dashboard, alerts, forecasts, and edit account. |
| **Admin**  | Logged-in user with role `admin`. Same as Viewer plus: view metrics, manage SMS recipients. |

## Use cases (system boundary: EWS app)

- **Login** – Sign in with email and password.  
- **Register** – Create account (email/password); default role is viewer.  
- **Logout** – Sign out.  
- **View Dashboard** – See latest sensor data (temperature, pH, DO, salinity, TDS, aeration) and warnings.  
- **View Alerts** – See forecast status and early warnings from forecasts.  
- **View Forecasts** – See forecast status and 24h forecast charts per parameter.  
- **View Metrics** – *(Admin only)* See MAE/RMSE for latest forecast run.  
- **Manage SMS Recipients** – *(Admin only)* Create, read, update, delete SMS alert recipients.  
- **Edit Account** – Change email (with current password) or change password.  

---

## Diagram (Mermaid)

```mermaid
flowchart TB
    subgraph System["Early Warning System"]
        direction TB
        subgraph Auth["Authentication"]
            UC_Login[Login]
            UC_Register[Register]
            UC_Logout[Logout]
        end
        subgraph ViewerUCs["Viewer use cases"]
            UC_Dash[View Dashboard]
            UC_Alerts[View Alerts]
            UC_Forecasts[View Forecasts]
            UC_Account[Edit Account]
        end
        subgraph AdminUCs["Admin-only use cases"]
            UC_Metrics[View Metrics]
            UC_Admin[Manage SMS Recipients]
        end
    end

    Guest((Guest))
    Viewer((Viewer))
    Admin((Admin))

    Guest --> UC_Login
    Guest --> UC_Register

    Viewer --> UC_Login
    Viewer --> UC_Register
    Viewer --> UC_Logout
    Viewer --> UC_Dash
    Viewer --> UC_Alerts
    Viewer --> UC_Forecasts
    Viewer --> UC_Account

    Admin --> UC_Login
    Admin --> UC_Register
    Admin --> UC_Logout
    Admin --> UC_Dash
    Admin --> UC_Alerts
    Admin --> UC_Forecasts
    Admin --> UC_Account
    Admin --> UC_Metrics
    Admin --> UC_Admin
```

---

## Diagram (PlantUML) – classic use case style

Paste the block below into [PlantUML](https://www.plantuml.com/plantuml/uml/) or a PlantUML-supported IDE to render a standard use case diagram.

```plantuml
@startuml EWS Use Case Diagram
left to right direction
skinparam packageStyle rectangle

actor Guest
actor Viewer
actor Admin

rectangle "Early Warning System" {
  usecase "Login" as UC_Login
  usecase "Register" as UC_Register
  usecase "Logout" as UC_Logout
  usecase "View Dashboard" as UC_Dash
  usecase "View Alerts" as UC_Alerts
  usecase "View Forecasts" as UC_Forecasts
  usecase "View Metrics" as UC_Metrics
  usecase "Manage SMS Recipients" as UC_Admin
  usecase "Edit Account" as UC_Account
}

Guest --> UC_Login
Guest --> UC_Register

Viewer --> UC_Login
Viewer --> UC_Register
Viewer --> UC_Logout
Viewer --> UC_Dash
Viewer --> UC_Alerts
Viewer --> UC_Forecasts
Viewer --> UC_Account

Admin --> UC_Login
Admin --> UC_Register
Admin --> UC_Logout
Admin --> UC_Dash
Admin --> UC_Alerts
Admin --> UC_Forecasts
Admin --> UC_Account
Admin --> UC_Metrics
Admin --> UC_Admin
@enduml
```

---

## Summary

| Use case                 | Guest | Viewer | Admin |
|--------------------------|:----:|:------:|:-----:|
| Login                    | ✓    | ✓      | ✓     |
| Register                 | ✓    | ✓      | ✓     |
| Logout                   | —    | ✓      | ✓     |
| View Dashboard           | —    | ✓      | ✓     |
| View Alerts              | —    | ✓      | ✓     |
| View Forecasts            | —    | ✓      | ✓     |
| View Metrics             | —    | —      | ✓     |
| Manage SMS Recipients    | —    | —      | ✓     |
| Edit Account             | —    | ✓      | ✓     |
