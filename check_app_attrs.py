import reflex as rx
app = rx.App()
print(f"Type of app._api: {type(app._api)}")
try:
    print(f"app.api: {app.api}")
except AttributeError:
    print("app.api does not exist")
