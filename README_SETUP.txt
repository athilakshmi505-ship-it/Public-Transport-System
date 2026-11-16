PUBLIC TRANSPORT MANAGEMENT SYSTEM - SETUP

1. Extract this ZIP into D:\PublicTransportSystem (or your existing project folder).
2. Keep a backup of your current app.py and templates folder first.
3. Replace app.py and the templates folder with the files in this package. Do not delete your PostgreSQL database.
4. Open app.py and replace YOUR_POSTGRES_PASSWORD with the PostgreSQL password you already use. Do not share it.
5. Open VS Code terminal in this folder and run:
   python -m pip install flask psycopg2-binary pandas
   python app.py
6. Open http://127.0.0.1:5000

ADMIN LOGIN (local college-project demo):
Username: admin
Password: ChangeMe123!

Change the demo admin password before using the app beyond local demonstration.
The app creates an admins table if it does not exist and adds owner_name to buses if missing.
It does not drop or recreate your existing tables or records.

Features:
Dashboard, Bus Management, Route Management, Schedule Management,
Passenger Management, Booking Management, Travel Analysis, Admin Login.

IMPORTANT:
- Public pages can view records.
- Only logged-in admin can add/delete records or cancel bookings.
- This is a local development/academic demo, not a production-hardened deployment.
- Flask debug mode is for local testing only.
