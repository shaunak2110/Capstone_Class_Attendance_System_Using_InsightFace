import bcrypt

password = "Super@admin123"
hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt())
print(hashed.decode())