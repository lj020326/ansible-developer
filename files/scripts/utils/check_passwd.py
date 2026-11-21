#!/usr/bin/env python3

import bcrypt

# --- For storing a new password ---
password = b"mysecretpassword" # Passwords should be bytes
hashed_password = bcrypt.hashpw(password, bcrypt.gensalt())
print(f"Hashed password to store: {hashed_password.decode('utf-8')}")

# --- For verifying a password later ---
user_input_password = b"mysecretpassword"
stored_hashed_password = b"$2b$12$EXAMPLEHASHFROMSTORAGE..." # This would come from your database

if bcrypt.checkpw(user_input_password, stored_hashed_password):
    print("Password matches!")
else:
    print("Password doesn't match!")
